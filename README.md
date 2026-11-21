# HydroPulse
A multi-screen web application: **Overview, Customer app, Fleet console, Devices, Warning policy, Evidence, Roadmap**. Screens live in `static/` (`index.html` shell, `app.css`, `app.js`, `roadmap.html`); the engine, API and storage are Python.
Software-only filter prognostics for connected RO water purifiers. It uses only signals a connected purifier already sends (input TDS, fill time per litre, optional temperature), predicts the days left on the RO membrane with a calibrated range, estimates the other filters, and plans one combined service visit.

## Run (Python 3.8+, nothing to install)
```
python server.py                  # dashboard + API at http://localhost:8000
python evaluate.py                # blind benchmark + calibration, writes results.json / results.md (about 25 s)
python tests/test_failsafe.py     # fail-safe tests
python device_emulator.py --id kitchen-01 --tds 900 --glitch     # a virtual device streaming to the API
python import_csv.py data.csv --flow COL --ec COL [--temp COL]   # run the engine on a real RO dataset
docker build -t hydropulse . && docker run -p 8000:8000 -v hp:/data hydropulse
```
**Warning policy:** the Warning policy screen sets how early customers are warned (Safety first 18 days, Balanced 10 days by default, Economy 6 days) and applies to the live demo and the device API immediately.

**Phone simulator:** the page has a phone on screen ("Meet your purifier"). It is a live virtual purifier sending real readings to the server every simulated day; the customer view on it is computed by the same engine. Change the saltiness, send tanker water, break the sensor, install a new filter. No Wi-Fi or second device needed. (`/device` is an optional page for a real phone on the same network.)

## Train the learned model (optional, free, Google Colab)
Open `colab/HydroPulse_Training.ipynb` in Google Colab. Put this zip into Google Drive under `atomquest/`, then run the cells top to bottom (about 30 minutes, CPU is enough, GPU optional). It downloads the public plant record, trains a small network on simulator data, calibrates its ranges, compares it honestly with the physics-only engine, and saves `model.json`. The engine loads `model.json` automatically if present; without it the physics engine runs alone. Extra evaluate options: `--no-model`, `--seed N`, `--out FILE`.

## What is real and what is simulated
- **Real:** the noise and outage pattern used in the stress test. It was measured from a public 540-day record of an operating MBR-RO plant (daily RO product volume, file `MBR_RO_AIOT_daily_flow_540d.xlsx` in the GitHub repo Asaeel/ro-fouling-early-warning). Steady-state daily noise is about 2.8%, but swings reach -23% to +35% at the 5th and 95th percentiles, and 60 of 540 days (11%) are outage-like. The extracted residuals are in `data/real_noise.json`. That record has flow only: no temperature, salinity or fouling labels, so it cannot test lifetime prediction.
- **Simulated:** all membrane wear, water events and failures, because no free purifier lifetime data exists. Results below are therefore simulation results, and say so.
- **Assumed until real device logs exist:** the telemetry fields (see the device message below).

## Method
Wear grows with cumulative salt exposure. The engine corrects each reading for temperature (about 3% flow per degree) and feed-salt back-pressure, tracks the filter level with a robust filter (outlier readings are clipped), and estimates the wear rate from both a long-memory physics fit and a fast local trend, trusting the cautious blend. **The stated range is calibrated** (split-conformal style) on separate training fleets, so "80% range" is measured, not guessed. A whole-locality shift is treated as a water event and not blamed on the filter. Sediment, carbon and UV have no direct signal: they are usage schedules shown as estimates, plus a flag when one home alone starts wearing faster (a spent carbon filter).

## Measured results (test fleet seed 7, never used for tuning; `python evaluate.py` reproduces)
See `results.md`. Headline: surprise failures are 98% / 92% / 95% fewer than a plain litre counter, and 84% / 79% / 68% fewer than a counter tuned on the same data (normal / harder / real-world noise). The true failure date was never earlier than our safe date in 92% / 84% / 90% of checks (target 90%), and the stated range held the truth 83% / 80% / 73% of the time (target 80%). The **safety dial** on the page shows the trade-off: warning about 6 days ahead uses 87% of filter life with 88% fewer failures than the old counter; about 10 days ahead cuts failures by 98% but uses 76%; about 18 days ahead leaves almost no failures but uses 61%. Misses: false alarms (22% / 6% / 44% against a target below 5%), filter life used before a planned change (76% / 77% / 68% against 85%), and spent-carbon detection (20 to 30% against 70%). The alert threshold (10 days) is tuned to favour avoiding failures over saving filter life.

## Device message (single integration point)
`POST /api/telemetry` with `{"device_id","tds_in","fill_s_per_l","temp_c"?,"locality"?,"ts"?}`. The first 10 readings set the unit's own clean baseline. Reply: `status` (HEALTHY, WATCH, ORDER NOW, FALLBACK), `rul`, `lo`, `hi`.

## Fail-safe (advisory only; never controls the purifier)
Missing, out-of-range or implausible readings fall back to the usage counter and say so. Water events are not blamed on the filter. A healthy filter raises no alerts over 700 days. Six automated tests.

## Limits
Lifetime results are simulated. No device authentication or encrypted transport yet (deploy behind TLS and a gateway). Next step: re-base on anonymised logs from real purifiers.
