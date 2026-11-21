"""Sends one purifier's daily telemetry to a running HydroPulse server, exactly as a connected Intellon would.
Usage: python device_emulator.py --id kitchen-01 --tds 900 [--days 400] [--glitch] [--host localhost:8000]"""
import argparse, json, math, random, time, urllib.request
from engine import tcf, ndp
a = argparse.ArgumentParser(); a.add_argument("--id", default="kitchen-01"); a.add_argument("--tds", type=float, default=900); a.add_argument("--days", type=int, default=400)
a.add_argument("--glitch", action="store_true"); a.add_argument("--host", default="localhost:8000"); a.add_argument("--delay", type=float, default=.05); o = a.parse_args()
r = random.Random(1); f = 0.; last = None
for d in range(o.days):
    temp = 25 + 8 * math.sin(2 * math.pi * d / 365) + r.gauss(0, 1); tds = o.tds * (1 + r.gauss(0, .04))
    f += .0011 * tds / 1000 * (1 + r.gauss(0, .1)); flow = (1 - f) * tcf(temp) * ndp(tds) * (1 + r.gauss(0, .04))
    msg = dict(device_id=o.id, tds_in=round(9999 if o.glitch and d % 97 == 50 else tds, 1), temp_c=round(temp, 1), fill_s_per_l=round(30 / flow, 2), locality="demo")
    req = urllib.request.Request(f"http://{o.host}/api/telemetry", json.dumps(msg).encode(), {"Content-Type": "application/json"})
    res = json.load(urllib.request.urlopen(req))
    if res["status"] != last: print(f"day {d}: {res['status']}  days left: {res.get('rul')}  {res['message']}"); last = res["status"]
    time.sleep(o.delay)
