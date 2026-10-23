# Findings: supporting numbers

Recomputed by `python -m avval.cli findings` under release `fe59625d94287538…`. Conditional on this release's simulator, models and exposure model.

## Margin erosion without hand-back

Across 600 campaigns (180,000 runs): runs without collision or hand-back whose stop-aware acceleration TTC fell below the monitor's 2 s: **0**

Why the monitor stayed silent in these runs is decomposed by `python -m avval.cli diagnose` (`results/handback_diagnostics_<campaign>.md`).

## Comfort and the jerk definition

All 100,000 runs of `estimate` (AC-04's population):

- 95th percentile of automated-control jerk (0.5 s moving average): **4.95 m/s³**
- whole-run filtered jerk (includes the driver phase): 6.51 m/s³
- raw sample-difference jerk: 25.00 m/s³
- runs above 5 m/s³ (automated control): 4,554, of which cut-ins 4,499
