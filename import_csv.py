"""Run the engine on a real RO dataset exported as CSV (for example the open Zenodo SCADA data, doi 10.5281/zenodo.21906111).
python import_csv.py data.csv --flow FT-401 --ec AT-402 [--temp TT-401] [--flow-unit lpm]
Maps columns to the HydroPulse device message: fill_s_per_l = 60 / flow (L/min), TDS (ppm) = 0.64 x conductivity (uS/cm).
Use it to check normalisation (temperature and salt corrections) on real RO behaviour. It is NOT a purifier-lifetime test."""
import argparse, csv
from engine import Estimator, tcf, ndp, observe_norm
a = argparse.ArgumentParser(); a.add_argument("csv"); a.add_argument("--flow", required=True); a.add_argument("--ec", required=True); a.add_argument("--temp"); a.add_argument("--step", type=int, default=1)
o = a.parse_args(); e = Estimator(); base, n, last = [], 0, None
for i, row in enumerate(csv.DictReader(open(o.csv, newline=""))):
    if i % o.step: continue
    try: flow = float(row[o.flow]); tds = .64 * float(row[o.ec]); temp = float(row[o.temp]) if o.temp else 25.
    except (ValueError, KeyError): continue
    if flow <= 0: continue
    k = flow / (tcf(temp) * ndp(tds))
    if len(base) < 10: base.append(k)
    r = e.update(k / (sum(base) / len(base)), tds); n += 1
    if r["status"] != last: print(f"row {i}: {r['status']}  health {r['h']:.3f}"); last = r["status"]
print(f"{n} rows processed; final health {e.h:.3f}")
