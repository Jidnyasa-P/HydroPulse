"""Blind benchmark: python evaluate.py -> results.json, results.md (about 15 s).
80 simulated homes, 10 localities, 1,100 days: tanker events, hard-water spells, dropouts, glitch readings, and a hidden
carbon-exhaustion cascade (a spent carbon filter lets chlorine through and speeds membrane wear 1.8x).
'harder' world: wear also accelerates as scale builds, a law the estimator never assumed."""
import json, math, os, random, statistics, sys, time
import engine
from engine import *
LOCS, PER, DAYS = 10, 8, 1100
REAL = json.load(open(os.path.join(os.path.dirname(__file__), "data", "real_noise.json")))["rel_resid"]   # measured on a real 540-day RO plant record

def make_env(seed, real=False):
    r = random.Random(seed); H = []
    for L in range(LOCS):
        tank, hard = [1.0] * DAYS, [1.0] * DAYS
        for _ in range(r.randint(2, 5)):
            s, f = r.randrange(DAYS - 30), r.uniform(1.4, 1.9)
            for d in range(s, s + r.randint(10, 25)): tank[d] = f
        for _ in range(r.randint(1, 3)):
            s = r.randrange(DAYS - 60)
            for d in range(s, s + r.randint(30, 60)): hard[d] = 2.0
        for _ in range(PER):
            h = dict(loc=L, k=r.uniform(.0007, .0015), lpd=r.uniform(12, 24), Lc=r.uniform(3500, 5500), rows=[]); t0 = r.uniform(150, 1400); gap = 0
            for d in range(DAYS):
                tds = t0 * tank[d] * (1 + r.gauss(0, .04)); ok = True
                if gap > 0: gap -= 1; ok = False
                elif r.random() < (.02 if real else .01): gap = r.randint(1, 10 if real else 4); ok = False
                rep = r.choice([0, 9999]) if ok and r.random() < .003 else tds
                h["rows"].append((25 + 8 * math.sin(2 * math.pi * d / 365) + r.gauss(0, 1), tds, rep, ok, hard[d], 1 + r.gauss(0, .1), (max(.3, min(1.7, 1 + r.choice(REAL))) if real else 1 + r.gauss(0, .04))))
            H.append(h)
    return H

def simulate(H, law, policy, WL=0, capture=False):
    n = len(H); f, l, lw, lc, pend = [0.] * n, [0.] * n, [0.] * n, [0.] * n, [-1] * n
    est = [Estimator() for _ in H]; S = dict(fail=0, plan=0, util=0., cdays=0, cres=0, days=[[] for _ in H]); info = [dict(alert=None, fail=None, rul=[], ex=None, flag=None, feat=[]) for _ in H]
    for d in range(DAYS):
        ev, rat = {}, [None] * n
        if policy in ("hydro", "none"):
            for L in range(LOCS):
                rs = [H[i]["rows"][d][2] / est[i].ema for i in range(L * PER, (L + 1) * PER) if H[i]["rows"][d][3] and est[i].ema and 5 <= H[i]["rows"][d][2] <= 3000]
                ev[L] = water_event(rs)
            rat = [e.k_ratio() for e in est]
        for i, h in enumerate(H):
            t, tds, rep, ok, hm, dn, on = h["rows"][d]; kc = 1.8 if lc[i] >= h["Lc"] else 1.0; S["cdays"] += kc > 1
            base = h["k"] * hm * kc * tds / 1000 * dn
            f[i] = min(.6, f[i] + (base * (1 + 4 * f[i]) if law == "harder" else base)); l[i] += h["lpd"]; lw[i] += h["lpd"] * tds / 1000; lc[i] += h["lpd"]
            cf = False
            if policy in ("hydro", "none"):
                norm = observe_norm((1 - f[i]) * tcf(t) * ndp(tds) * on, t, rep) if ok else None
                res = est[i].update(norm, rep if ok else None, ev[h["loc"]]); st = res["status"]
                peers = [rat[j] for j in range(h["loc"] * PER, (h["loc"] + 1) * PER) if j != i and rat[j] is not None]
                cf = (res['pcar'] > .7) if res.get('pcar') is not None else (rat[i] is not None and carbon_flag(rat[i], peers))
                if policy == "none":
                    inf = info[i]; inf["rul"].append(res["rul"])
                    if capture and d % 7 == 0 and d >= 60 and res["ok"]: inf["feat"].append((d, est[i].features(res["rul_phys"]), int(lc[i] >= h["Lc"])))
                    if st == "ORDER NOW" and inf["alert"] is None: inf["alert"] = d
                    if f[i] >= .15 and inf["fail"] is None: inf["fail"] = d
                    if lc[i] >= h["Lc"] and inf["ex"] is None: inf["ex"] = d
                    if cf and inf["flag"] is None: inf["flag"] = d
                    continue
                due = l[i] >= CL if st == "FALLBACK" else st == "ORDER NOW"
            if lc[i] >= CAR_L or cf: lc[i] = 0.; S["cres"] += 1
            fail = f[i] >= .15
            if policy == "counter": plan = l[i] >= CL
            elif policy == "weighted": plan = lw[i] >= WL
            else:
                if due and pend[i] < 0: pend[i] = 7
                if pend[i] > 0: pend[i] -= 1
                plan = pend[i] == 0
            if fail or plan:
                if fail: S["fail"] += 1
                else: S["plan"] += 1; S["util"] += f[i] / .15
                S["days"][i].append(d); f[i] = l[i] = lw[i] = 0.; pend[i] = -1
                if policy == "hydro": est[i] = Estimator()
    return S, info

def visits(md, lpd, bundle):
    ps, pc = SED_L / lpd, CAR_L / lpd; ns, nc, v = ps, pc, 0
    for m in list(md) + [DAYS + 1]:
        while min(ns, nc) < m and min(ns, nc) <= DAYS:
            t = min(ns, nc); v += 1
            if bundle: ns, nc = (t + ps if ns <= t + 45 else ns), (t + pc if nc <= t + 45 else nc)
            else: ns, nc = (t + ps if ns <= t else ns), (t + pc if nc <= t else nc)
        if m <= DAYS:
            v += 1
            if bundle: ns, nc = (m + ps if ns <= m + 45 else ns), (m + pc if nc <= m + 45 else nc)
    return v

def prog(info):
    leads, e30, e14, false, alerts, hit, ex, bad = [], [], [], 0, 0, 0, 0, 0
    for inf in info:
        T, a = inf["fail"], inf["alert"]
        if inf["ex"] is not None:
            ex += 1; hit += inf["flag"] is not None and inf["ex"] <= inf["flag"] <= inf["ex"] + 90
        if inf["flag"] is not None and (inf["ex"] is None or inf["flag"] < inf["ex"]): bad += 1
        if T is None: continue
        if a is not None and a <= T: alerts += 1; leads.append(T - a); false += (T - a > 45)
        else: leads.append(0)
        for x, lst in ((30, e30), (14, e14)):
            if T - x >= 0 and inf["rul"][T - x] is not None: lst.append(abs(inf["rul"][T - x] - x) / x)
    pc = lambda v, c: round(100 * sum(1 for x in v if c(x)) / max(1, len(v)), 1)
    return dict(n=len(leads), lead14=pc(leads, lambda x: x >= 14), lead_med=statistics.median(leads), e14_in15=pc(e14, lambda x: x <= .15), e14_in25=pc(e14, lambda x: x <= .25),
                e14_med=round(100 * statistics.median(e14)), e30_in25=pc(e30, lambda x: x <= .25), false=round(100 * false / max(1, alerts), 1),
                carbon_hit=round(100 * hit / max(1, ex)), carbon_false=round(100 * bad / max(1, len(info))))

def coverage(info):
    n = inl = safe = 0
    for inf in info:
        T = inf["fail"]
        if T is None: continue
        for d, rul in enumerate(inf["rul"]):
            if rul and 0 < rul < 150 and d < T:
                fl, fh = engine.band(rul); t = T - d; n += 1; inl += fl * rul <= t <= fh * rul; safe += t >= fl * rul
    return round(100 * inl / max(1, n)), round(100 * safe / max(1, n))

if __name__ == "__main__":
    if "--no-model" in sys.argv: engine.MODEL = None
    SEED = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "results.json"
    t0 = time.time(); W = [("linear", "standard", False), ("harder", "harder", False), ("linear", "stress", True)]
    trs = [(law, make_env(100 + j, real)) for j, (law, _, real) in enumerate(W)]         # training fleets: tuning only
    engine.CAL = None; ratios = [[], [], []]
    for law, H in trs:
        for inf in simulate(H, law, "none")[1]:
            T = inf["fail"]
            for d, rul in enumerate(inf["rul"]):
                if T is not None and rul and 0 < rul < 150 and d < T: ratios[0 if rul < 30 else 1 if rul < 90 else 2].append((T - d) / rul)
    q = lambda v, p: sorted(v)[int(p * (len(v) - 1))] if v else 1.0
    cal = dict(lo=[round(q(v, .10), 3) for v in ratios], hi=[round(q(v, .90), 3) for v in ratios]); json.dump(cal, open("calibration.json", "w")); engine.CAL = cal
    obj = lambda S: 5 * S[0]["fail"] + S[0]["plan"] - S[0]["util"]
    best = min(range(1500, 5001, 250), key=lambda w: sum(obj(simulate(H, law, "weighted", w)) for law, H in trs))
    def cost(T): engine.ALERT = T; return sum(obj(simulate(H, law, "hydro")) for law, H in trs)
    alert = min((7, 10, 14, 18, 22, 28), key=cost); engine.ALERT = alert
    out, Hs = {}, {}
    for law, name, real in W:
        H = make_env(SEED, real); R = {}; Hs[name] = (law, H)
        for p in ("counter", "weighted", "hydro"):
            S, _ = simulate(H, law, p, best)
            R[p] = dict(fail=S["fail"], plan=S["plan"], util=round(100 * S["util"] / max(1, S["plan"]), 1), cdays=S["cdays"], cres=S["cres"])
            if p == "hydro": R["visits"] = dict(separate=sum(visits(S["days"][i], H[i]["lpd"], False) for i in range(len(H))), bundled=sum(visits(S["days"][i], H[i]["lpd"], True) for i in range(len(H))))
        _, info = simulate(H, law, "none"); R["prog"] = prog(info); R["prog"]["cov_in"], R["prog"]["cov_safe"] = coverage(info); out[name] = R
    curve = {}
    for T in (6, 8, 10, 14, 18, 22, 28, 36):
        engine.ALERT = T; curve[T] = {}
        for nm, (law, H) in Hs.items():
            S, _ = simulate(H, law, "hydro"); curve[T][nm] = [S["fail"], round(100 * S["util"] / max(1, S["plan"]), 1), S["fail"] + S["plan"]]
    engine.ALERT = alert
    rows = []
    def row(nm, tg, fn, ok):
        v = [fn(out[k]) for k in ("standard", "harder", "stress")]; rows.append(dict(name=nm, target=tg, vals=v, ok=[ok(x) for x in v]))
    row("Surprise failures vs old counter: fewer by", "40% fewer", lambda o: round(100 * (1 - o["hydro"]["fail"] / max(1, o["counter"]["fail"]))), lambda x: x >= 40)
    row("Surprise failures vs tuned counter: fewer by", "40% fewer", lambda o: round(100 * (1 - o["hydro"]["fail"] / max(1, o["weighted"]["fail"]))), lambda x: x >= 40)
    row("Warned at least 14 days before failure", "90% of failures", lambda o: o["prog"]["lead14"], lambda x: x >= 90)
    row("True failure date is never earlier than our safe date", "90% of the time", lambda o: o["prog"]["cov_safe"], lambda x: x >= 90)
    row("Stated range holds the true days left", "80% of the time", lambda o: o["prog"]["cov_in"], lambda x: x >= 80)
    row("False alarms (warned over 45 days too early)", "Below 5%", lambda o: o["prog"]["false"], lambda x: x < 5)
    row("Filter life used before planned change", "85% or more", lambda o: o["hydro"]["util"], lambda x: x >= 85)
    row("Fewer technician visits (one-visit plan)", "20% fewer", lambda o: round(100 * (1 - o["visits"]["bundled"] / max(1, o["visits"]["separate"]))), lambda x: x >= 20)
    row("Spent carbon filter caught within 90 days", "70% of cases", lambda o: o["prog"]["carbon_hit"], lambda x: x >= 70)
    json.dump(dict(rows=rows, detail=out, weighted_limit=best, alert_days=alert, calibration=cal, curve=curve, seconds=round(time.time() - t0)), open(OUT, "w"), indent=1)
    md = "| Metric | Target | Standard | Harder | Real-noise stress |\n|---|---|---|---|---|\n" + "\n".join(f"| {r['name']} | {r['target']} | " + " | ".join(f"{r['vals'][i]} {'PASS' if r['ok'][i] else 'MISS'}" for i in range(3)) + " |" for r in rows)
    open(OUT.replace(".json", ".md"), "w").write(md); print(md); print("alert", alert, "cal", cal); print("seconds", round(time.time() - t0))
