# Search-strategy benchmark

Each strategy is run once per seed with the same budget. Detection probability is the share of seeds whose campaign contains at least one run in the region (`avval/benchmark.py::REGIONS`). Runs to first failure is averaged over the seeds that found a failure.

| metric | random | grid | agent |
| --- | --- | --- | --- |
| seeds | 100 | 100 | 3 |
| runs/seed | 300 | 300 | 177 |
| runs to first failure (mean ± SD) | 8.8 ± 8.9 (100/100 seeds found one) | 9.1 ± 8.9 (100/100 seeds found one) | 23.0 ± 29.4 (3/3 seeds found one) |
| distinct failing cells (mean ± SD) | 20.5 ± 2.5 | 21.1 ± 2.8 | 13.7 ± 4.0 |
| P(detect attentive_preventable_collision) [95% CI] | 0.67 [0.57, 0.76] | 0.64 [0.54, 0.73] | 1.00 [0.29, 1.00] |
| P(detect misuse_handback_collision) [95% CI] | 1.00 [0.96, 1.00] | 1.00 [0.96, 1.00] | 1.00 [0.29, 1.00] |
| P(detect silent_margin_erosion) [95% CI] | 0.99 [0.95, 1.00] | 0.99 [0.95, 1.00] | 1.00 [0.29, 1.00] |
| P(detect comfort_exceedance) [95% CI] | 1.00 [0.96, 1.00] | 1.00 [0.96, 1.00] | 1.00 [0.29, 1.00] |

## Matched budget: first 188 runs

`agent` campaigns stop early; they used 188 runs on average. Here every other strategy's campaigns are cut to their first 188 runs and compared with the `agent` campaigns as they ran.

| metric | random | grid | agent |
| --- | --- | --- | --- |
| seeds | 100 | 100 | 3 |
| runs/seed | 188 | 188 | 177 |
| runs to first failure (mean ± SD) | 8.8 ± 8.9 (100/100 seeds found one) | 9.1 ± 8.9 (100/100 seeds found one) | 23.0 ± 29.4 (3/3 seeds found one) |
| distinct failing cells (mean ± SD) | 15.2 ± 2.7 | 16.1 ± 2.9 | 13.7 ± 4.0 |
| P(detect attentive_preventable_collision) [95% CI] | 0.51 [0.41, 0.61] | 0.43 [0.33, 0.53] | 1.00 [0.29, 1.00] |
| P(detect misuse_handback_collision) [95% CI] | 1.00 [0.96, 1.00] | 1.00 [0.96, 1.00] | 1.00 [0.29, 1.00] |
| P(detect silent_margin_erosion) [95% CI] | 0.94 [0.87, 0.98] | 0.94 [0.87, 0.98] | 1.00 [0.29, 1.00] |
| P(detect comfort_exceedance) [95% CI] | 1.00 [0.96, 1.00] | 1.00 [0.96, 1.00] | 1.00 [0.29, 1.00] |

![Discovery curves](discovery_curves.png)

## Regions

- `attentive_preventable_collision`: `collision AND preventable AND driver_state = 'attentive'`
- `misuse_handback_collision`: `collision AND preventable AND tor_issued AND driver_category = 'foreseeable_misuse'`
- `silent_margin_erosion`: `NOT collision AND NOT tor_issued AND min_ttc_accel < 2.0`
- `comfort_exceedance`: `NOT tor_issued AND max_jerk > 5.0`
