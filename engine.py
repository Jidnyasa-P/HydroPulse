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
        s.rec, s.pcar, s._o = [], None, None
    def k_ratio(s): return (s.ks / max(s.kl, 1e-6) if s.rc >= 20 else 1.0) if s.n >= 60 else None   # sustained recent speed-up vs long-run
    def features(s, rul_phys):
        """Fixed-order feature vector for the learned model (the last entry must stay rul_phys)."""
        r = s.rec or [s.h]; m = sum(r) / len(r); sd = math.sqrt(sum((v - m) ** 2 for v in r) / len(r)); half = len(r) // 2 or 1
        tr = (sum(r[half:]) / max(1, len(r) - half) - sum(r[:half]) / half) / max(1, half)
        return [s.h, s.hf, s.kl * 1e3, s.ks * 1e3, s.k * 1e3, s.ks / max(s.kl, 1e-6), s.E / 100, s.dex or 0., (s.ema or 0.) / 1e3, math.sqrt(s.var), s.n / 365, m - s.h, sd * 10, tr * 1e3, rul_phys / 100]
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
        if not ok: return dict(status="FALLBACK", rul=None, lo=None, hi=None, slope=s.slope, h=s.h, ok=False)
        s.k = max(s.kl, .5 * (s.kl + s.ks)); s.slope = -s.k * dex
        g = lambda f: min(365, max(0, (s.h - FAIL) / (max(s.k * f, 1e-5) * dex)))
        rul = g(1); rul_phys = rul; fl, fh = band(rul); lo, hi = rul * fl, min(365, rul * fh); s.pcar = None
        if MODEL and s.n >= 60:
            if rul_phys < 150 or s.n % 5 == 0 or s._o is None: s._o = _mlp(s.features(rul_phys))
            o = s._o; s.pcar = 1 / (1 + math.exp(-max(-30, min(30, o[3]))))
            if rul_phys < 150:
                q = sorted(min(365., math.expm1(max(0., v))) for v in (o[0] + MODEL["off"][0], o[1], o[2] + MODEL["off"][1])); lo, rul, hi = q
        return dict(status="ORDER NOW" if lo <= ALERT else "WATCH" if lo <= 45 else "HEALTHY", rul=rul, lo=lo, hi=hi, slope=s.slope, h=s.h, ok=True, rul_phys=rul_phys, pcar=s.pcar)
