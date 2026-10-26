# Backtest

```
radar backtest --out docs
```

## Setup

* 1,000 simulated members, each with a full year of daily activity. Seed 7.
* About 20% do not renew. Their behaviour starts to shift 40 to 130 days before renewal.
* Everyone else has normal noise: travel gaps of 4 to 12 days, missed replies, off weeks.
* Each method is checked **30 days before renewal**, the last point a coach can realistically act. Lead time is the earliest weekly check in the 120 days before renewal that flagged a member who went on to leave.

Methods compared:

* **Radar**: band is Drifting or Needs care.
* **Logins**: fewer than 2 portal logins in the last 30 days.
* **NPS**: latest survey answer is 6 or below.

## Results

**Default scenario**

| Method | Precision | Recall | Flagged | Revenue caught | Median lead |
|---|---|---|---|---|---|
| Radar | 96% | 41% | 9% | 41% | 64 days |
| Logins | 35% | 6% | 4% | 7% | 71 days |
| NPS | 44% | 22% | 10% | 23% | 120 days |

**Subtle drift** (churners change half as much)

| Method | Precision | Recall | Flagged | Revenue caught | Median lead |
|---|---|---|---|---|---|
| Radar | 90% | 18% | 4% | 18% | 60 days |
| Logins | 21% | 2% | 2% | 2% | 78 days |
| NPS | 40% | 18% | 9% | 17% | 120 days |

![Backtest](backtest.png)
![Threshold sweep](threshold_sweep.png)

## How to read this

**The simulator encodes the hypothesis.** It assumes leavers change their daily behaviour before renewal and that logins and NPS barely move. So of course the radar wins in the default scenario. What this run actually shows:

1. **The pipeline works end to end.** Simulate, ingest, score, evaluate, all with no future leakage.
2. **How fast the edge decays.** When drift is half as strong, the radar's recall at the default cut-off falls from 41% to 18%, level with NPS. If real members drift quietly, the cut-off has to come down, or new signals are needed.
3. **The precision vs recall trade-off is the real decision.** See the threshold table in [design.md](design.md).

NPS shows a 120 day "lead" because the simulator gives leavers a lower NPS all year. That is a property of the simulator, not evidence NPS predicts anything.

**What would make this real:** two years of de-identified member activity and renewal outcomes from one clinic. Same harness, real labels.

Every parameter is listed in `SimParams` in [`synth.py`](../src/retention_radar/synth.py) and saved in `backtest.json`.
