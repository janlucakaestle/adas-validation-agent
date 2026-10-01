# Findings: supporting numbers

Recomputed from the stored campaigns by `python -m avval.cli findings`.

## Silent margin erosion

Across 200 benchmark campaigns (60,000 runs; `random_s*` and `grid_s*`):

- runs without collision or hand-back whose constant-speed TTC fell below 2 s: **0**
- runs without collision or hand-back whose acceleration-aware TTC fell below 2 s: **822** (822 of them lead braking), minimum **1.65 s**
- of those, friction below 0.75: 409; friction 0.75 or above: 413

## Comfort and the jerk definition

Runs without a hand-back in `estimate` (AC-04's population): 77,863.

- 95th percentile of filtered jerk (`max_jerk`, 0.5 s moving average): **5.04 m/s³**
- 95th percentile of raw 20 Hz sample-difference jerk (`max_jerk_raw`): **7.32 m/s³**
- runs above 5 m/s³ (filtered): 4,338, of which cut-ins 4,338; largest 5.70 m/s³

## Single seed-0 baseline campaigns

| campaign | runs | attentive runs | collisions | unpreventable | attentive preventable collisions |
|---|---|---|---|---|---|
| `random` | 300 | 140 | 13 | 0 | 1 |
| `grid` | 300 | 138 | 16 | 0 | 1 |
