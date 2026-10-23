# Discovery benchmark (confirmatory)

Protocol ID `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`, frozen 2026-10-21T20:44:29.200317 (final evidence); release `fe59625d94287538…`; runtime `d37505bee00e01c2…`; agent interface `ca0ed8e6e82c3fe9…`.

| strategy | campaigns | runs (median) | RMST runs to first target [95% CI] | censored | P(attentive_reference_avoidable_collision) | P(misuse_handback_collision) | P(silent_margin_erosion) | P(comfort_exceedance) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| agent | 10 | 258 | 42.5 [27.6, 56.0] | 0 | 1.00 [0.69, 1.00] | 1.00 [0.69, 1.00] | 0.00 [0.00, 0.31] | 1.00 [0.69, 1.00] |
| random | 100 | 300 | 20.9 [16.7, 25.7] | 0 | 0.61 [0.51, 0.71] | 1.00 [0.96, 1.00] | 0.00 [0.00, 0.04] | 1.00 [0.96, 1.00] |
| grid | 100 | 300 | 19.9 [16.4, 23.9] | 0 | 0.58 [0.48, 0.68] | 1.00 [0.96, 1.00] | 0.00 [0.00, 0.04] | 1.00 [0.96, 1.00] |
| cem | 100 | 300 | 17.4 [14.9, 20.3] | 0 | 0.81 [0.72, 0.88] | 1.00 [0.96, 1.00] | 0.00 [0.00, 0.04] | 1.00 [0.96, 1.00] |
| evolutionary | 100 | 300 | 22.9 [19.3, 26.5] | 0 | 0.75 [0.65, 0.83] | 1.00 [0.96, 1.00] | 0.00 [0.00, 0.04] | 1.00 [0.96, 1.00] |
| boundary | 100 | 300 | 23.5 [19.2, 28.1] | 0 | 0.18 [0.11, 0.27] | 0.95 [0.89, 0.98] | 0.00 [0.00, 0.04] | 0.96 [0.90, 0.99] |
| bayesopt | 100 | 300 | 19.1 [16.2, 22.0] | 0 | 1.00 [0.96, 1.00] | 1.00 [0.96, 1.00] | 0.00 [0.00, 0.04] | 1.00 [0.96, 1.00] |

Detection shares carry two-sided 95% Clopper-Pearson intervals over seeds. Runs to first target run: Kaplan-Meier restricted mean up to the budget, campaigns with no target run censored at their length.

## Matched budget (primary analysis)

Region `attentive_reference_avoidable_collision`: agent detected it in 10 of 10 seeds (1.00 [0.69, 1.00]).

| baseline | campaigns | expected detections (plug-in) | tail prob. plug-in | posterior-predictive tail prob. (Jeffreys) | 95% upper bound | upper bound, uniform prior | upper bound, no prior | Δ target cells [95% CI] |
|---|---|---|---|---|---|---|---|---|
| random | 100 | 5.46 | 0.002 | 0.003 | 0.007 | 0.007 | 0.007 | +4.2 [+3.0, +5.4] |
| grid | 100 | 4.62 | 3.7e-04 | 5.7e-04 | 0.002 | 0.002 | 0.002 | +3.6 [+2.5, +4.9] |
| cem | 100 | 7.72 | 0.074 | 0.079 | 0.156 | 0.151 | 0.156 | -0.3 [-1.6, +1.1] |
| evolutionary | 100 | 6.69 | 0.017 | 0.020 | 0.043 | 0.044 | 0.045 | -2.1 [-3.4, -0.8] |
| boundary | 100 | 1.80 | 3.6e-08 | 2.3e-07 | 9.6e-07 | 9.7e-07 | 8.7e-07 | +7.0 [+5.7, +8.3] |
| bayesopt | 100 | 9.99 | 0.990 | 0.945 | 0.996 | 0.987 | 0.999 | -4.2 [-5.5, -3.0] |

Tail probability: P(baseline detects in at least as many seeds as the agent at the same per-seed budgets) under the model in `avval/benchmark.py::posterior_predictive_at_least`. Posterior-predictive quantities, not frequentist p-values.

## Agent model identity

Model IDs returned by the API: `claude-sonnet-5`. Agent API calls span 2026-10-21T20:47:19+00:00 to 2026-10-21T23:33:12+00:00 UTC.

**Limitation.** The API returned a model alias, not a dated snapshot ID (the Models API listed no dated snapshot of this model when the protocol was written). The protocol's check that all seeds ran on one returned model ID therefore cannot detect a model update behind the alias. The seeds were run in one sitting to keep that window short; the time span above is the record of when they ran.

## Conclusions (scoped)

- Under this simulator, information interface, target region (`attentive_reference_avoidable_collision`) and run budget (300), the evaluated agent (claude-sonnet-5, 10 seeds) detected the region in more seeds than this baseline would be expected to at the same per-seed budgets (95% upper credible bound of the posterior-predictive tail probability 0.007 < 0.05) relative to `random` (100 campaigns).
- Under this simulator, information interface, target region (`attentive_reference_avoidable_collision`) and run budget (300), the evaluated agent (claude-sonnet-5, 10 seeds) detected the region in more seeds than this baseline would be expected to at the same per-seed budgets (95% upper credible bound of the posterior-predictive tail probability 0.002 < 0.05) relative to `grid` (100 campaigns).
- Under this simulator, information interface, target region (`attentive_reference_avoidable_collision`) and run budget (300), the evaluated agent (claude-sonnet-5, 10 seeds) did not show a detection advantage over this baseline that survives the uncertainty in its detection probabilities (95% upper bound 0.156) relative to `cem` (100 campaigns).
- Under this simulator, information interface, target region (`attentive_reference_avoidable_collision`) and run budget (300), the evaluated agent (claude-sonnet-5, 10 seeds) detected the region in more seeds than this baseline would be expected to at the same per-seed budgets (95% upper credible bound of the posterior-predictive tail probability 0.043 < 0.05) relative to `evolutionary` (100 campaigns).
- Under this simulator, information interface, target region (`attentive_reference_avoidable_collision`) and run budget (300), the evaluated agent (claude-sonnet-5, 10 seeds) detected the region in more seeds than this baseline would be expected to at the same per-seed budgets (95% upper credible bound of the posterior-predictive tail probability 9.6e-07 < 0.05) relative to `boundary` (100 campaigns).
- Under this simulator, information interface, target region (`attentive_reference_avoidable_collision`) and run budget (300), the evaluated agent (claude-sonnet-5, 10 seeds) did not show a detection advantage over this baseline that survives the uncertainty in its detection probabilities (95% upper bound 0.996) relative to `bayesopt` (100 campaigns).
- The comparison is of complete search strategies with the same public information: the agent reads natural-language descriptions and can reason about visible derived labels such as `avoidable_by_reference` (part of the primary region); the numerical baselines optimise a robustness score of `collision`, `end_state` and `min_ttc` only. It is not a comparison of optimisation efficiency on one identical objective.
- These statements do not generalise to other simulators, systems, targets, budgets, models or baselines.

![Discovery curves](discovery_curves.png)

## Regions

- `attentive_reference_avoidable_collision`: `collision AND avoidable_by_reference AND driver_state = 'attentive'`
- `misuse_handback_collision`: `collision AND avoidable_by_reference AND handback_required AND driver_category = 'foreseeable_misuse'`
- `silent_margin_erosion`: `NOT collision AND NOT tor_issued AND min_ttc_accel < 2.0`
- `comfort_exceedance`: `max_jerk_automated > 5.0`
