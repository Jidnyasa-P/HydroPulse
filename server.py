"""HydroPulse engine: AquaTwin fleet simulator + prognostics + web server. Python standard library only."""
import json, math, os, random, sqlite3, statistics, threading, time
import engine as E
from engine import Estimator, tcf, ndp, observe_norm, water_event, plan_visit, CL, FAIL, SED_L, CAR_L
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOC = ["Kothrud", "Hadapsar", "Wakad"]
LOCK = threading.Lock()
TYPES = [("Soft municipal", 220), ("Mixed supply", 400), ("Hard borewell", 1100),
         ("Hard borewell", 900), ("Mixed supply", 600), ("Soft municipal", 300)]

class Home:
    def __init__(s, i, rng):
        s.id, s.rng, s.loc, s.name = i, rng, LOC[i % 3], f"Home {i+1}"
        s.kind, s.tds0 = TYPES[i]; s.k = rng.uniform(.0007, .0015); s.lpd = rng.uniform(12, 24)
        s.fa, s.la = 0., 0.       # membrane under the old counter rule
        s.st = dict(an=0, au=0., af=0, bn=0, bu=0., bf=0); s.sensor = 0; s.ema = None; s.event = False; s.ls = s.lcar = s.uvh = 0.
        s.tds, s.temp, s.rate = s.tds0, 25, s.k; s.newb(s.fa, s.la)
    def newb(s, f=0., l=0.):                                      # membrane under HydroPulse
        s.f, s.l, s.pend, s.hist, s.est, s.h = f, l, -1, [], Estimator(s.tds0), 1.0
        s.status, s.rul, s.lo, s.hi, s.slope = "HEALTHY", 365, 365, 365, -.001
    def stages(s):
        d = {"Membrane (RO)": round(s.rul), "Sediment filter": round((SED_L - s.ls) / s.lpd), "Carbon filter": round((CAR_L - s.lcar) / s.lpd), "UV lamp": round((9000 - s.uvh) / 8)}
        when, bundle = plan_visit(d)
        return dict(list=[dict(name=k, days=max(0, v), basis="read from flow and salt" if k.startswith("Mem") else "estimated from usage") for k, v in d.items()], visit=when, bundle=bundle)
    def truth(s): return max(0, (.15 - s.f) / max(s.rate * s.tds / 1000, 1e-6))

class World:
    def __init__(s):
        s.rng = random.Random(7); s.day = 0; s.speed = 4.0; s.log = []
        s.homes = [Home(i, s.rng) for i in range(6)]
        s.tank = {l: 0 for l in LOC}; s.hard = {l: 0 for l in LOC}
        for _ in range(1500): s.tick()
        s.log = []
    def say(s, m): s.log.insert(0, m); s.log = s.log[:6]
    def tick(s):
        s.day += 1; r = s.rng
        mult = {l: 1.7 if s.tank[l] > 0 else 1. for l in LOC}
        for l in LOC: s.tank[l] = max(0, s.tank[l] - 1); s.hard[l] = max(0, s.hard[l] - 1)
        for h in s.homes:                                          # AquaTwin physics
            h.temp = 25 + 8 * math.sin(2 * math.pi * s.day / 365) + r.gauss(0, 1)
            h.tds = h.tds0 * mult[h.loc] * (1 + r.gauss(0, .04))
            h.rate = h.k * (2.2 if s.hard[h.loc] else 1.)
            d = h.rate * h.tds / 1000 * (1 + r.gauss(0, .1))
            h.f = min(.6, h.f + d); h.fa = min(.6, h.fa + d); h.l += h.lpd; h.la += h.lpd; h.sensor = max(0, h.sensor - 1); h.ls += h.lpd; h.lcar += h.lpd; h.uvh += 8
        for l in LOC:                                              # fleet "water weather"
            hs = [h for h in s.homes if h.loc == l and h.est.ema]
            ev = bool(hs) and water_event([h.tds / h.est.ema for h in hs])
            for h in s.homes:
                if h.loc == l:
                    if ev and not h.event: s.say(f"{l}: every home saw the water change together. HydroPulse does not blame the filters.")
                    h.event = ev
        for h in s.homes:
            ok = h.sensor == 0
            raw = (1 - h.f) * tcf(h.temp) * ndp(h.tds) * (1 + r.gauss(0, .04)); norm = observe_norm(raw, h.temp, h.tds)
            res = h.est.update(norm if ok else None, h.tds, h.event); h.h, h.slope = h.est.h, h.est.slope
            crul = max(0, (CL - h.l) / h.lpd)
            if res["status"] == "FALLBACK": h.status, h.rul, h.lo, h.hi = "FALLBACK", crul, crul, crul   # fail-safe: revert to counter
            else: h.status, h.rul, h.lo, h.hi = res["status"], res["rul"], res["lo"], res["hi"]
            h.hist.append([raw, h.h, 1 - h.f, h.event]); h.hist = h.hist[-150:]
            if h.ls >= SED_L: h.ls = 0.
            if h.lcar >= CAR_L: h.lcar = 0.
            if h.uvh >= 9000: h.uvh = 0.
            if h.fa >= .15 or h.la >= CL:                           # old rule: replace at 6,000 L or on failure
                if h.fa >= .15: h.st["af"] += 1
                else: h.st["an"] += 1; h.st["au"] += h.fa / .15
                h.fa = h.la = 0.
            due = (h.status == "ORDER NOW") if ok else h.l >= CL
            if due and h.pend < 0: h.pend = 7                       # customer needs about a week to act
            if h.pend > 0: h.pend -= 1
            if h.f >= .15 or h.pend == 0:
                if h.f >= .15: h.st["bf"] += 1
                else: h.st["bn"] += 1; h.st["bu"] += h.f / .15
                h.newb()
                if (SED_L - h.ls) / h.lpd <= 45: h.ls = 0.     # one visit: change what is nearly due too
                if (CAR_L - h.lcar) / h.lpd <= 45: h.lcar = 0.
    def snap(s):
        hs = [dict(id=h.id, name=h.name, kind=h.kind, loc=h.loc, tds=round(h.tds), rul=round(h.rul), lo=round(h.lo), hi=round(h.hi),
                   crul=round(max(0, (CL - h.l) / h.lpd)), truth=round(h.truth()), status=h.status, event=h.event,
                   sched=h.pend > 0, slope=h.slope, stages=h.stages(), hist=h.hist[-120:]) for h in s.homes]
        t = lambda k: sum(h.st[k] for h in s.homes)
        w = lambda u, n: round(100 * (1 - t(u) / t(n))) if t(n) else None
        return dict(alert=E.ALERT, homes=hs, af=t("af"), bf=t("bf"), aw=w("au", "an"), bw=w("bu", "bn"), log=s.log, speed=s.speed)

DB = sqlite3.connect(os.environ.get("HP_DB", "hydropulse.db"), check_same_thread=False)
DB.execute("create table if not exists telem(device text, ts text, tds real, temp real, fill real, norm real, status text, rul real)")
DEV = {}
def ingest(d):
    """Real-device path. Message: {device_id, tds_in, fill_s_per_l, temp_c?, locality?, ts?}"""
    try: did = str(d["device_id"]); fill = float(d["fill_s_per_l"]); tds = float(d["tds_in"]); temp = float(d.get("temp_c", 25))
    except Exception: return dict(status="REJECTED", message="bad message")
    dev = DEV.setdefault(did, dict(est=Estimator(), base=[], loc=d.get("locality", did), tds=None))
    ok = fill > 0 and 5 <= tds <= 3000
    k = (1 / fill) / (tcf(temp) * ndp(tds)) if ok else None
    if k and len(dev["base"]) < 10: dev["base"].append(k)      # commissioning baseline: this unit's own clean flow
    norm = k / statistics.mean(dev["base"]) if k else None
    dev["tds"] = tds if ok else None
    rs = [x["tds"] / x["est"].ema for x in DEV.values() if x["loc"] == dev["loc"] and x["est"].ema and x["tds"]]
    r = dev["est"].update(norm, tds if ok else None, len(rs) >= 3 and water_event(rs))
    DB.execute("insert into telem values(?,?,?,?,?,?,?,?)", (did, str(d.get("ts", time.time())), tds, temp, fill, norm, r["status"], r["rul"])); DB.commit()
    dev["last"] = {k: r[k] for k in ("status", "rul", "lo", "hi")}
    r["message"] = "Invalid reading: advisory falls back to the usage counter" if not r["ok"] else "ok"
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}

W = World()
def loop():
    while True:
        time.sleep(1 / W.speed)
        with LOCK: W.tick()
threading.Thread(target=loop, daemon=True).start()

class H(BaseHTTPRequestHandler):
    def log_message(s, *a): pass
    def out(s, body, ct="application/json"):
        s.send_response(200); s.send_header("Content-Type", ct); s.send_header("Cache-Control", "no-store"); s.end_headers(); s.wfile.write(body)
    def do_GET(s):
        if s.path.startswith("/api/results"):
            p = Path(__file__).parent / "results.json"; s.out(p.read_bytes() if p.exists() else b"{}")
        elif s.path.startswith("/static/"):
            base = (Path(__file__).parent / "static").resolve(); p = (Path(__file__).parent / s.path.split("?")[0].lstrip("/")).resolve()
            if base in p.parents and p.is_file(): s.out(p.read_bytes(), {".css": "text/css", ".js": "text/javascript", ".html": "text/html; charset=utf-8"}.get(p.suffix, "application/octet-stream"))
            else: s.send_error(404)
        elif s.path.startswith("/api/devices"):
            s.out(json.dumps({k: v["last"] for k, v in DEV.items() if v.get("last")}).encode())
        elif s.path.startswith("/device"):
            s.out((Path(__file__).parent / "static" / "device.html").read_bytes(), "text/html; charset=utf-8")
        elif s.path.startswith("/api/state"):
            with LOCK: s.out(json.dumps(W.snap()).encode())
        else: s.out((Path(__file__).parent / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
    def do_POST(s):
        global W
        d = json.loads(s.rfile.read(int(s.headers.get("Content-Length", 0))) or b"{}"); k = d.get("kind")
        if s.path.startswith("/api/telemetry"): return s.out(json.dumps(ingest(d)).encode())
        with LOCK:
            h = W.homes[int(d.get("id", 0)) % len(W.homes)]
            if k == "tanker": W.tank[h.loc] = 20; W.say(f"Tanker water arrives in {h.loc}.")
            elif k == "hard": W.hard[h.loc] = 60; W.say(f"{h.name}: hard-water spell. The filter is now wearing faster.")
            elif k == "sensor": h.sensor = 30; W.say(f"{h.name}: TDS sensor failed. Switched to the safe usage counter.")
            elif k == "policy": E.ALERT = float(d.get("v", 10)); W.say(f"Warning policy set: warn about {int(E.ALERT)} days ahead.")
            elif k == "speed": W.speed = float(d.get("v", 4))
            elif k == "reset": W = World()
        s.out(b"{}")

if __name__ == "__main__":
    print("HydroPulse is running. Open http://localhost:8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
