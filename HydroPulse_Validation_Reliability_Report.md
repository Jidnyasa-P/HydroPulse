# HydroPulse –  Validation & Reliability Report
 
**Project:** Smart RO Filter Life Prediction & Monitoring System  
**Report scope:** Baseline validation, real-data suitability, 10-seed benchmark, stress testing, and soak test

---


## 1. Abstract

This report summarizes the validation and reliability testing performed for HydroPulse, a smart reverse-osmosis (RO) filter-life prediction and monitoring system. Testing covered fail-safe behavior, baseline model performance, the suitability of an external industrial dataset, repeated-seed benchmarking, robustness under increased sensor noise, reduced fleet size, multi-week sensor outages, and a long-duration emulator run.

The system showed strong reductions in simulated surprise failures compared with the old usage-counter baseline across the tested scenarios. However, performance was weaker against the tuned counter, and the stress tests consistently exposed high false-alarm rates, low filter-life utilization, and limited detection of spent carbon filters. The real SCADA dataset was useful for examining operational data quality but was not suitable for direct filter-life model validation. The soak test was stopped early after observing more than 819 simulated days; it did not complete the intended 5,000 days.

## 2. Objectives

- Verify baseline fail-safe tests and confirm expected fallback behavior.
- Examine a real industrial RO dataset for suitability, quality, and compatibility with HydroPulse.
- Benchmark the evaluation across ten random seeds to measure variability.
- Stress-test the evaluation with doubled noise, a smaller home fleet, and multi-week sensor outages.
- Observe long-running emulator behavior, status transitions, and fallback events.
- Identify reliability weaknesses and provide evidence-based conclusions.

## 3. Test environment and scope

- Operating system / execution environment: Windows PowerShell
- Python: 3.12.6
- Project directory: `HydroPulse`
- Evaluation program: `evaluate.py`; stress-test copies were used for isolated configuration changes.
- Fail-safe test program: `tests/test_failsafe.py`
- Emulator: `device_emulator.py`
- Server: `server.py`

### Testing approach

Ten seeds (1–10) were run for the benchmark and each of the three stress tests. Means and sample standard deviations (SD, `ddof=1`) are reported. Values in tables are percentages; SD is expressed in percentage points. Small differences in the last decimal may occur due to rounding.

## 4. Phase 1 – Baseline setup and fail-safe verification

### 4.1 Environment check

- Python version verified: **3.12.6**.
- Evaluation script baseline completed successfully.
- Baseline evaluation runtime was approximately **28 seconds**.

### 4.2 Fail-safe test results

Command: `python tests/test_failsafe.py`

**Result: 6 passed, 0 failed.**

| Test | Result |
|---|---|
| Bad sensor reading falls back | PASS |
| Degrading filter flagged before failure | PASS |
| Healthy filter never alerts | PASS |
| Implausible flow falls back | PASS |
| Missing flow falls back | PASS |
| Water event is not blamed on filter | PASS |

### 4.3 Original evaluation baseline

| Metric | Target | Standard | Harder | Real-noise stress |
|---|---|---:|---:|---:|
| Surprise failures reduced vs old counter | At least 40% | 98% PASS | 92% PASS | 95% PASS |
| Surprise failures reduced vs tuned counter | At least 40% | 84% PASS | 79% PASS | 68% PASS |
| Warned ≥14 days before failure | 90% | 88.8% MISS | 70.0% MISS | 92.5% PASS |
| Safe-date reliability | 90% | 92% PASS | 84% MISS | 90% PASS |
| Prediction-range coverage | 80% | 83% PASS | 80% PASS | 73% MISS |
| False alarms | Below 5% | 21.5% MISS | 6.3% MISS | 43.6% MISS |
| Filter life utilized | At least 85% | 75.6% MISS | 77.1% MISS | 67.8% MISS |
| Technician visit reduction | At least 20% | 20% PASS | 21% PASS | 18% MISS |
| Spent carbon detected within 90 days | 70% | 30% MISS | 20% MISS | 21% MISS |

**Baseline interpretation:** The system substantially reduced surprise failures against the old counter, but false alarms were above target in all three scenarios. Filter-life utilization and spent-carbon detection were also below their targets.

## 5. Phase 2 – Real dataset suitability validation

### 5.1 Dataset

**Dataset:** *An Open SCADA Architecture for an Experimental Reverse Osmosis System: Development and Functional Validation*  
**Source:** Zenodo record 21906111  
**Link:** https://zenodo.org/records/21906111  
**License:** CC-BY 4.0

Two dataset files were examined:
- `historian_measurements.csv`
- `alarm_history.csv`

### 5.2 Dataset overview

| Property | Observed value |
|---|---|
| Historian rows | 190,840 |
| Historian columns | 5 |
| Historian tags | 11 |
| Historian date coverage | 2026-05-28 to 2026-06-23 |
| Alarm-history records | 11,142 |
| Historian columns | timestamp, tag, value, state, unit |
| Alarm-history columns | datahora, tag, evento, prioridade, ack, duracao_segundos |

Sensor families represented included AT (pH/conductivity), FT (flow), PT (pressure), and TT (temperature). The equipment mapping for feed/product streams was not established from the available documentation.

### 5.3 Data-quality observations

- Measurements were consolidated from 11 tag exports.
- Decimal commas were converted to decimal points for numeric parsing.
- Sampling frequencies varied by tag; readings were not aligned into simultaneous timestamp rows.
- Sensor states included `NORMAL`, `INVÁLIDO`, `BAIXO`, `FAIXA`, `OFFLINE`, and `ALTO`.
- The documented `FAIXA` state combines operational-limit violations.
- Empty values were observed in 12 records and corresponded to offline readings.
- Flow readings were frequently zero, with relatively few non-zero observations.
- Some values across the full dataset were extreme or physically questionable; therefore, filtering by documented state and investigating sensor quality is important before use.
- No rows were removed or imputed during the inspection.

### 5.4 Suitability decision

**Decision: Not suitable for direct filter-life validation or normalization experiments in its current form.** The dataset is a short functional-validation SCADA record, not a membrane/filter-lifetime dataset. It does not provide the verified equipment mapping, aligned multi-sensor readings, and lifetime labels needed to directly validate the HydroPulse life-prediction model. It remains useful for studying sensor states, operational alarms, missingness, and data reliability.

The project's `import_csv.py` expects a long-format-to-wide mapping with aligned timestamps and known sensor roles. Because timestamp frequencies differ and stream roles are uncertain, the data was not forced into that importer and was not used to claim model validation.

## 6. Phase 3 – Ten-seed benchmark

### 6.1 Method

The baseline `evaluate.py` was run with seeds 1 through 10. Each seed's JSON output was saved separately under:

`Person3_Results/Ten_Seed_Benchmark/`

### 6.2 Mean ± sample SD

| Metric | Standard | Harder | Real-noise stress |
|---|---:|---:|---:|
| Surprise failures reduced vs old counter | 95.7 ± 1.3% | 90.9 ± 1.6% | 94.6 ± 1.0% |
| Surprise failures reduced vs tuned counter | 77.5 ± 7.1% | 76.9 ± 4.7% | 70.1 ± 8.9% |
| Warned ≥14 days before failure | 85.6 ± 5.1% | 72.9 ± 4.5% | 90.3 ± 3.3% |
| Safe-date reliability | 91.6 ± 1.6% | 84.1 ± 1.2% | 90.3 ± 1.3% |
| Prediction-range coverage | 82.6 ± 2.2% | 80.1 ± 1.6% | 74.1 ± 1.9% |
| False alarms | 21.1 ± 3.9% | 9.9 ± 3.2% | 43.5 ± 6.8% |
| Filter life utilized | 75.2 ± 0.8% | 76.2 ± 1.1% | 67.2 ± 1.1% |
| Technician visit reduction | 19.1 ± 1.0% | 19.8 ± 1.2% | 18.1 ± 1.2% |
| Carbon detection within 90 days | 32.3 ± 5.0% | 16.6 ± 5.4% | 24.1 ± 6.3% |

### 6.3 Findings

- The reduction in surprise failures against the old counter was consistently strong.
- Performance against the tuned counter was lower than performance against the old counter.
- Safe-date reliability reached or exceeded 90% in Standard and Real-noise averages, but not in Harder.
- Prediction-range coverage met the 80% target on average for Standard and Harder, but not Real-noise stress.
- Fourteen-day warning performance met the target on average only in Real-noise stress.
- False alarms were substantially above the 5% target across all scenarios.
- Filter-life utilization and carbon-filter detection remained below target.

## 7. Phase 4 – Stress testing

Each stress-test configuration was isolated in a separate evaluation copy, leaving the original `evaluate.py` baseline configuration unchanged.

### 7.1 Stress test 4.1 – Double noise

**Change:** Ordinary simulated sensor noise was increased from 0.04 to 0.08 in the isolated copy `evaluate_double_noise.py`. Other settings were left unchanged. Ten seeds were run.

| Metric | Standard | Harder | Real-noise stress |
|---|---:|---:|---:|
| Failure reduction vs old counter | 95.7 ± 1.3% | 91.0 ± 1.3% | 94.6 ± 1.0% |
| Failure reduction vs tuned counter | 77.3 ± 9.3% | 77.1 ± 4.0% | 69.3 ± 8.1% |
| Warned ≥14 days | 85.3 ± 5.0% | 72.8 ± 4.4% | 90.0 ± 3.8% |
| Safe-date reliability | 91.6 ± 1.6% | 84.0 ± 1.3% | 90.2 ± 1.0% |
| Prediction-range coverage | 82.6 ± 2.2% | 80.0 ± 1.5% | 74.2 ± 2.0% |
| False alarms | 20.8 ± 3.7% | 9.9 ± 3.2% | 43.6 ± 6.7% |
| Filter life utilized | 75.1 ± 0.8% | 76.0 ± 1.0% | 67.1 ± 1.3% |
| Technician visit reduction | 19.2 ± 0.8% | 19.7 ± 1.2% | 18.1 ± 0.9% |
| Carbon detection within 90 days | 32.1 ± 4.7% | 16.7 ± 5.0% | 24.1 ± 6.0% |

**Observation:** Doubling ordinary noise produced broadly similar results to the original ten-seed benchmark. Existing weaknesses—especially false alarms, low filter-life utilization, and low carbon detection—remained.

### 7.2 Stress test 4.2 – Half homes per area

**Change:** The evaluation configuration was reduced from 8 homes per area to 4 (`PER=4`), while keeping 10 areas (`LOCS=10`) and 1,100 days (`DAYS=1100`). Fleet size was reduced from 80 to 40 simulated homes. Ten seeds were run in `evaluate_half_homes.py`.

| Metric | Standard | Harder | Real-noise stress |
|---|---:|---:|---:|
| Failure reduction vs old counter | 96.8 ± 0.6% | 93.2 ± 1.3% | 95.2 ± 1.2% |
| Failure reduction vs tuned counter | 82.4 ± 4.4% | 83.9 ± 4.9% | 66.2 ± 15.5% |
| Warned ≥14 days | 90.0 ± 4.3% | 76.0 ± 6.8% | 90.25 ± 2.49% |
| Safe-date reliability | 91.2 ± 2.4% | 82.8 ± 3.4% | 89.8 ± 2.1% |
| Prediction-range coverage | 82.9 ± 2.3% | 79.2 ± 3.4% | 75.3 ± 3.1% |
| False alarms | 24.74 ± 7.77% | 13.8 ± 4.63% | 45.97 ± 5.05% |
| Filter life utilized | 71.65 ± 1.72% | 73.01 ± 2.10% | 62.65 ± 1.04% |
| Technician visit reduction | 17.7 ± 1.7% | 19.5 ± 0.71% | 19.0 ± 1.49% |
| Carbon detection within 90 days | 36.7 ± 6.36% | 18.6 ± 5.1% | 24.9 ± 4.12% |

**Observation:** Failure reduction against the old counter remained strong in the reduced fleet. Harder-case warning and safe-date reliability remained weaker. Real-noise stress continued to show the highest false-alarm rates and lowest filter-life utilization.

### 7.3 Stress test 4.3 – Multi-week sensor outage

**Change:** In `evaluate_sensor_outage.py`, the outage duration was changed to a random 14–28 consecutive days when a sensor gap was triggered. The original outage trigger probabilities were retained (1% standard / 2% real scenario). Ten seeds were run.

| Metric | Standard | Harder | Real-noise stress |
|---|---:|---:|---:|
| Failure reduction vs old counter | 94.3 ± 1.1% | 87.4 ± 1.7% | 90.8 ± 1.1% |
| Failure reduction vs tuned counter | 74.3 ± 5.7% | 71.1 ± 5.2% | 50.1 ± 13.8% |
| Warned ≥14 days | 88.3 ± 4.1% | 79.5 ± 4.1% | 90.6 ± 3.1% |
| Safe-date reliability | 90.5 ± 1.4% | 80.7 ± 1.9% | 91.1 ± 1.1% |
| Prediction-range coverage | 81.5 ± 1.6% | 77.0 ± 2.2% | 74.7 ± 3.0% |
| False alarms | 44.5 ± 7.2% | 21.2 ± 2.9% | 58.5 ± 4.0% |
| Filter life utilized | 65.9 ± 1.5% | 67.1 ± 1.2% | 58.7 ± 0.9% |
| Technician visit reduction | 18.0 ± 0.7% | 19.5 ± 0.7% | 19.2 ± 0.9% |
| Carbon detection within 90 days | 25.4 ± 3.6% | 18.1 ± 3.8% | 23.1 ± 3.6% |

**Observation:** Prolonged outages were associated with higher false-alarm rates and lower filter-life utilization. The Real-noise scenario was most affected, with average false alarms of 58.5%. Failure reduction against the old counter remained positive and substantial, but comparison against the tuned counter was weaker—especially under Real-noise stress.

## 8. Phase 5 – Soak test / long-duration emulator observation

### 8.1 Test setup

- Server launched in a separate terminal using `python server.py`.
- Emulator command: `python device_emulator.py --days 5000 --delay 0`.
- Intended duration: 5,000 simulated days.
- The emulator was manually stopped before completion after observing more than 819 simulated days. Therefore, this is a **partial soak run**, not a completed 5,000-day test.

### 8.2 Observed output

Status transitions observed included:
- `HEALTHY`
- `WATCH`
- `ORDER NOW`
- `FALLBACK` after invalid readings, with the advisory falling back to the usage counter

The output included successful readings (`ok`) and fallback messages such as `Invalid reading: advisory falls back to the usage counter`. The test showed that the emulator progressed through multiple simulated periods and that fallback messages appeared when invalid readings were encountered.

### 8.3 Result and limitation

**Partial run observed: at least 819 simulated days.** The run was stopped manually due to time. No claim is made that 5,000 days completed, or that long-run resource usage, memory stability, or uninterrupted operation over the full target duration were verified. The observed fallback messages indicate that invalid readings triggered the fallback path during this run.

## 9. KPI summary and cross-test interpretation

| KPI / reliability area | Target | Overall observation |
|---|---|---|
| Surprise-failure reduction vs old counter | ≥40% | Consistently exceeded in benchmark and stress scenarios |
| Surprise-failure reduction vs tuned counter | ≥40% | Generally exceeded in benchmark and noise / reduced-fleet tests; weaker under long outages, especially Real-noise |
| 14-day warning | 90% | Achieved in Real-noise benchmark averages; weaker in Harder and some Standard conditions |
| Safe-date reliability | 90% | Standard and Real-noise often near/above target; Harder consistently weaker |
| Prediction range coverage | 80% | Standard generally meets; Harder near target; Real-noise below target |
| False alarm rate | <5% | Not achieved in any scenario; major area for improvement |
| Filter-life utilization | ≥85% | Not achieved; model tends to advise replacement too early |
| Technician visit reduction | ≥20% | Close to target, generally about 18–20% |
| Carbon filter detection within 90 days | ≥70% | Not achieved; detection rate remains low |
| Fail-safe handling | Tests pass | Six baseline fail-safe tests passed; fallback events observed in emulator |

## 10. Major findings

### Strengths
1. The fail-safe suite passed all six tests.
2. Surprise-failure reduction versus the old usage counter was strong across benchmark and stress scenarios.
3. Safe-date reliability was near or above target for Standard and Real-noise scenarios in several test configurations.
4. The emulator displayed multiple operational states and fallback events during the partial soak run.
5. The external SCADA data provided useful insight into sensor states, sampling differences, offline records, and operational alarms.

### Weaknesses
1. False alarms were substantially above the 5% target in every scenario, particularly Real-noise and multi-week outage conditions.
2. Filter-life utilization remained below the 85% target, indicating predictions can encourage premature replacement.
3. Carbon-filter detection within 90 days remained far below the 70% target.
4. Harder scenario safe-date and warning performance were consistently weaker.
5. Real-noise stress prediction-range coverage remained below the target.
6. The SCADA dataset could not directly validate filter-life prediction because its scope, label information, stream mapping, and time alignment were insufficient for this purpose.
7. The 5,000-day soak test was not completed.

## 11. Recommendations

- Prioritize reducing false alarms, especially under noisy measurements and prolonged sensor outages.
- Review prediction confidence and safe-date logic when readings are missing for extended periods.
- Investigate the causes of low filter-life utilization and improve replacement timing to reduce premature changes.
- Improve spent-carbon detection and verify the target against a dataset with known carbon-filter replacement/failure labels.
- Obtain a real RO dataset with clearly mapped sensor streams, aligned timestamps, and actual filter replacement or failure records before claiming real-world predictive validation.
- Repeat the soak test at a shorter, explicitly completed duration and record the completion marker, runtime, and any server/emulator errors; a partial run should not be treated as proof of full-duration stability.
- Preserve separate benchmark/stress configurations and results for reproducibility.

## 12. Conclusion

HydroPulse demonstrated promising simulated failure-warning behavior and robust fail-safe handling under the tested baseline conditions. Across repeated runs, the system substantially reduced surprise failures compared with the old counter. However, its reliability is not yet balanced: false alarms are high, filters are not being used to the desired proportion of their life, carbon-filter detection is weak, and the Harder and prolonged-outage conditions reduce prediction reliability. The external SCADA data was valuable for data-quality assessment but could not be used as direct filter-life ground truth. The partial soak test confirmed that the emulator progressed through many simulated days and exercised fallback behavior, but it did not verify completion of 5,000 days.

Overall, Person 3 testing provides a reproducible evaluation baseline and identifies the most important next improvements: false-alarm reduction, better behavior during sensor outages, more reliable filter-life utilization, improved carbon-filter detection, and real-life validation using appropriately labeled RO data.

## 13. Test artifacts and folders

Results were saved or intended to be saved in the project under:

- `Person3_Results/Ten_Seed_Benchmark/` – ten benchmark JSON results
- `data_validation_Results/Double_Noise/` – ten double-noise stress results
- `data_validation_Results/Half_Homes/` – ten reduced-fleet results
- `data_validation_Results/Sensor_Outage/` – ten multi-week outage results
- `real_data/` – the examined SCADA files

Isolated evaluation scripts are in folder testing:

- `evaluate_double_noise.py`
- `evaluate_half_homes.py`
- `evaluate_sensor_outage.py`

Original `evaluate.py` was retained for the baseline configuration.


---
**Prepared by:** Person 3 – Data, Validation and Reliability  
**Project:** HydroPulse – Smart RO Filter Life Prediction & Monitoring System
