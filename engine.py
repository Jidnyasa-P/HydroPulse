"""HydroPulse core engine. One source of truth for the demo, the API, the benchmark and the tests."""
import json, math, os, statistics
ALERT = 10                       # alert when the cautious days-left estimate drops to this
FAIL, CL = .85, 6000             # RO failure line (normalised flow -15%), plain-counter limit (litres)
SED_L, CAR_L, UV_H = 3000, 4500, 9000   # rated sediment litres, carbon litres, UV lamp hours
K0, TAU, LAM = .0011, 300., .995  # fleet-average fouling coefficient, prior weight, memory (about 100 days)
try: CAL = json.load(open(os.path.join(os.path.dirname(__file__), "calibration.json")))   # ranges calibrated on held-out runs
except Exception: CAL = None
def band(rul):
    """Multipliers (low, high) so that the stated range holds the true days-left about 80% of the time."""
    if not CAL: return .8, 1.33
    b = 0 if rul < 30 else 1 if rul < 90 else 2; return CAL["lo"][b], CAL["hi"][b]
try: MODEL = json.load(open(os.path.join(os.path.dirname(__file__), "model.json")))   # optional learned model, trained in the Colab notebook
except Exception: MODEL = None
def _mlp(f):
    x = [(a - m) / sd for a, m, sd in zip(f, MODEL["mean"], MODEL["std"])]
    for i, L in enumerate(MODEL["layers"]):
        x = [sum(w * v for w, v in zip(row, x)) + b for row, b in zip(L["W"], L["b"])]
        if i < len(MODEL["layers"]) - 1: x = [max(0., v) for v in x]
    return x
try: import numpy as np
except Exception: np = None
class GruRunner:
    """Streaming GRU + heads (same layout as torch.nn.GRU). One small state vector per purifier, one step per day."""
    def __init__(s, M):
        s.M, s.H = M, len(M["bhh"]) // 3
        c = (lambda a: np.array(a, dtype="float64")) if np else (lambda a: a)
        s.Wih, s.Whh, s.bih, s.bhh, s.mean, s.std = (c(M[k]) for k in ("Wih", "Whh", "bih", "bhh", "mean", "std"))
        s.heads = [(c(L["W"]), c(L["b"])) for L in M["head"]]
    def init(s): return np.zeros(s.H) if np else [0.] * s.H
    def step(s, h, x):
        H = s.H
        if np:
            x = np.clip((np.array(x) - s.mean) / s.std, -8, 8); gi = s.Wih @ x + s.bih; gh = s.Whh @ h + s.bhh
            r = 1 / (1 + np.exp(-(gi[:H] + gh[:H]))); z = 1 / (1 + np.exp(-(gi[H:2*H] + gh[H:2*H]))); n = np.tanh(gi[2*H:] + r * gh[2*H:])
            return (1 - z) * n + z * h
        x = [max(-8., min(8., (a - m) / d)) for a, m, d in zip(x, s.mean, s.std)]
        mv = lambda W, v, b: [sum(w * t for w, t in zip(row, v)) + bb for row, bb in zip(W, b)]
        gi, gh = mv(s.Wih, x, s.bih), mv(s.Whh, h, s.bhh); sg = lambda v: 1 / (1 + math.exp(-max(-30., min(30., v))))
        r = [sg(gi[i] + gh[i]) for i in range(H)]; z = [sg(gi[H+i] + gh[H+i]) for i in range(H)]
        n = [math.tanh(gi[2*H+i] + r[i] * gh[2*H+i]) for i in range(H)]
        return [(1 - z[i]) * n[i] + z[i] * h[i] for i in range(H)]
    def out(s, h):
        v = h
        for i, (W, b) in enumerate(s.heads):
            v = (W @ v + b) if np else [sum(w * t for w, t in zip(row, v)) + bb for row, bb in zip(W, b)]
            if i < len(s.heads) - 1: v = np.maximum(v, 0) if np else [max(0., t) for t in v]
        return [float(t) for t in v]
_R = [None, None]
def _runner():
    if MODEL is None or MODEL.get("type") != "gru": return None
    if _R[0] is not MODEL: _R[0], _R[1] = MODEL, GruRunner(MODEL)
    return _R[1]
tcf = lambda temp: 1 + .03 * (temp - 25)                    # permeate flow moves ~3% per degree C
ndp = lambda tds: (6 - .00075 * tds) / (6 - .00075 * 500)   # osmotic back-pressure from feed TDS
observe_norm = lambda raw, temp, tds: raw / (tcf(temp) * ndp(tds))
water_event = lambda ratios: len(ratios) > 0 and statistics.median(ratios) > 1.25   # a whole locality shifted together
carbon_flag = lambda mine, peers: mine > 1.5 and (not peers or statistics.median(peers) < 1.25)  # only THIS home wears faster

def plan_visit(days):
    """days: {stage: days left}. One technician visit at the earliest due date, bundling anything due within 45 days."""
    first = min(days.values()); return max(0, first), [k for k, v in days.items() if v <= first + 45]

class Estimator:
    """Level from a lag-free filter; wear rate from two views: a long-memory physics fit (norm = 1 - k*E, E = cumulative
    salt exposure; very precise, slow to notice a change) and a fast local trend (quick to notice, noisy). We trust the
    cautious blend: it reacts to a speed-up but is not shaken by noise. A fleet prior anchors new membranes."""
    def __init__(s, tds0=None):
        s.E, s.sxx, s.sxy, s.var, s.dex, s.n, s.kl, s.kf, s.ks = 0., 0., 0., 1e-3, None, 0, K0, K0, K0
        s.h, s.hf, s.r, s.tds0, s.ema, s.slope, s.k, s.rc = 1.0, 1.0, 0., tds0, None, -.001, K0, 0
        s.rec, s.pcar, s._o, s._hs, s._rp, s.want_x, s.last_x = [], None, None, None, 100., False, None
    def k_ratio(s): return (s.ks / max(s.kl, 1e-6) if s.rc >= 20 else 1.0) if s.n >= 60 else None   # sustained recent speed-up vs long-run
    def features(s, rul_phys):
        """Fixed-order feature vector for the learned model (the last entry must stay rul_phys)."""
        r = s.rec or [s.h]; m = sum(r) / len(r); sd = math.sqrt(sum((v - m) ** 2 for v in r) / len(r)); half = len(r) // 2 or 1
        tr = (sum(r[half:]) / max(1, len(r) - half) - sum(r[:half]) / half) / max(1, half)
        return [s.h, s.hf, s.kl * 1e3, s.ks * 1e3, s.k * 1e3, max(0., min(10., s.ks / max(s.kl, 1e-4))), s.E / 100, s.dex or 0., (s.ema or 0.) / 1e3, math.sqrt(s.var), s.n / 365, m - s.h, sd * 10, max(-20., min(20., tr * 1e3)), rul_phys / 100]
    def _step(s, norm, tds, event, ok, rp):
        """Build the 19-number daily input and advance the streaming GRU (if a GRU model is loaded)."""
        R = _runner()
        if R is None and not s.want_x: return None
        x = s.features(rp) + [norm if ok else 0., 0. if ok else 1., 1. if event else 0., min(3., max(.3, tds / s.ema)) if ok and s.ema else 1.]
        s.last_x = x
        if R is None: return None
        if s._hs is None: s._hs = R.init()
        s._hs = R.step(s._hs, x); return R.out(s._hs)
    def update(s, norm, tds, event=False):
        ok = norm is not None and tds is not None and 5 <= tds <= 3000 and .2 < norm < 2.5    # plausibility guard
        s.n += 1
        if tds is not None and 5 <= tds <= 3000:
            s.E += tds / 1000                                   # exposure always counts, even during a water event
            if not event:
                s.ema = tds if s.ema is None else s.ema + .05 * (tds - s.ema)
                s.dex = tds / 1000 if s.dex is None else s.dex + .02 * (tds / 1000 - s.dex)
        dex = max(.05, s.dex if s.dex else (s.tds0 or 500) / 1000)
        if ok and not event:                                    # learn only from clean days
            pred = s.hf + s.r; res = max(-.1, min(.1, norm - pred))      # robust to heavy-tailed readings
            s.hf = pred + .15 * res; s.r += .01 * res; s.var = .98 * s.var + .02 * res * res
            y = s.kl * s.E + max(-.1, min(.1, (1 - norm) - s.kl * s.E)); s.sxx = LAM * s.sxx + s.E ** 2; s.sxy = LAM * s.sxy + s.E * y
            s.kl = (s.sxy + TAU * K0) / (s.sxx + TAU)
            s.rec = (s.rec + [norm])[-30:]
            s.ks += .05 * (min(4 * s.kl, max(0., -s.r / dex)) - s.ks)
        elif ok: s.hf += s.r * .5                                # water event: hold, do not learn
        hp = 1 - s.kl * s.E; w = max(0., 1 - abs(s.hf - hp) / .03); s.h = min(1., max(.3, w * hp + (1 - w) * s.hf))   # precise physics level when it agrees with the filter
        s.rc = s.rc + 1 if s.ks > 1.4 * s.kl else 0
        if not ok:
            s._step(norm, tds, event, False, s._rp)
            return dict(status="FALLBACK", rul=None, lo=None, hi=None, slope=s.slope, h=s.h, ok=False)
        s.k = max(s.kl, .5 * (s.kl + s.ks)); s.slope = -s.k * dex
        g = lambda f: min(365, max(0, (s.h - FAIL) / (max(s.k * f, 1e-5) * dex)))
        rul = g(1); rul_phys = rul; fl, fh = band(rul); lo, hi = rul * fl, min(365, rul * fh); s.pcar = None
        s._rp = rul_phys; o = s._step(norm, tds, event, True, rul_phys)
        if o is not None:                                        # streaming GRU: calibrated range + carbon probability
            if s.n >= 60:
                s.pcar = 1 / (1 + math.exp(-max(-30, min(30, o[3]))))
                if rul_phys < 150:
                    off = MODEL["off"][0 if rul_phys < 30 else 1 if rul_phys < 90 else 2]; sp = lambda v: math.log1p(math.exp(-abs(v))) + max(v, 0)
                    lo, rul, hi = sorted(min(365., math.expm1(max(0., v))) for v in (o[0] - sp(o[1]) + off[0], o[0], o[0] + sp(o[2]) + off[1]))
        elif MODEL and "layers" in MODEL and s.n >= 60:          # older snapshot network
            if rul_phys < 150 or s.n % 5 == 0 or s._o is None: s._o = _mlp(s.features(rul_phys))
            o = s._o; s.pcar = 1 / (1 + math.exp(-max(-30, min(30, o[3]))))
            if rul_phys < 150:
                lo, rul, hi = sorted(min(365., math.expm1(max(0., v))) for v in (o[0] + MODEL["off"][0], o[1], o[2] + MODEL["off"][1]))
        return dict(status="ORDER NOW" if lo <= ALERT else "WATCH" if lo <= 45 else "HEALTHY", rul=rul, lo=lo, hi=hi, slope=s.slope, h=s.h, ok=True, rul_phys=rul_phys, pcar=s.pcar)
