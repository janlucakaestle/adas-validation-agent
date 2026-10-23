# Sensitivity (factorial2)

Frozen sensitivity protocol `0703cc9e2fcada557bc2efc140dbbb1f63f5280ec9a9e847879edc995d20af33`.

65 variants, each re-running the same exposure-weighted sample (2000 runs, seed 0; common random numbers: identical cases and per-run seeds, only the varied factor changes). Only these factors were varied, over these ranges; nothing here supports a conclusion about any other assumption (for example the correlation of reaction time with speed, or the exposure structure):

- `attentive_takeover_mean_s`: 1-1.8 (`driver.states.attentive.takeover_mean_s`)
- `attentive_takeover_sd_s`: 0.4-0.6 (`driver.states.attentive.takeover_sd_s`)
- `distracted_takeover_mean_s`: 3.5-6 (`driver.states.distracted.takeover_mean_s`)
- `distracted_takeover_sd_s`: 0.9-1.8 (`driver.states.distracted.takeover_sd_s`)
- `brake_onset_delay_s`: 0-0.5 (`driver.brake_onset_delay_s`)
- `brake_demand_factor`: 1-2 (`driver.brake_demand_factor`)
- `peak_decel_fraction`: 0.7-1 (`driver.states.*.peak_decel_fraction`)
- `brake_jerk_mps3`: 10-40 (`driver.states.*.brake_jerk`)
- `standstill_hold_decel_mps2`: 1-4 (`driver.standstill_hold_decel_mps2`)
- `distracted_share`: 0.05-0.4 (`exposure.factors.driver_state.weights.distracted`)
- `tor_required_decel_mps2`: 2.5-3.5 (`sim.monitor.tor_required_decel_mps2`)
- `tor_ttc_s`: 1.5-3 (`sim.monitor.tor_ttc_s`)
- `monitor_detection_delay_s`: 0-0.5 (`sim.monitor.detection_delay_s`)
- `actuator_delay_s`: 0-0.3 (`sim.ego.actuator_delay_s`)
- `required_decel_margin_m`: 1-3 (`sim.required_decel.margin_m`)
- `acc_authority_mps2`: 3-4.5 (`sim.ego.accel_min_mps2`)

## Primary responses (paired differences from the nominal variant)

Each cell: the variant's value; Δ = variant − nominal (row 0), computed run by run on the common sample; [95% paired percentile bootstrap interval, 1000 draws over run indices]; MDE = realised minimum detectable difference (2.80 × bootstrap SE: two-sided 5%, power 80%). These intervals are the Monte Carlo uncertainty of the finite sample, given the frozen model. A paired MDE rests on the runs whose outcome changed; "MDE n/a" means no run changed, so a zero interval is not a precision claim (the protocol's conservative unpaired MDEs below then apply). Definitions:

- `eff_ttc_p01`: 1% quantile of `CASE WHEN collision OR end_state = 'horizon_unresolved' THEN 0.0 ELSE coalesce(min_ttc, 'Infinity'::DOUBLE) END`
- `eff_ttc_p05`: 5% quantile of `CASE WHEN collision OR end_state = 'horizon_unresolved' THEN 0.0 ELSE coalesce(min_ttc, 'Infinity'::DOUBLE) END`
- `eff_ttc_p50`: 50% quantile of `CASE WHEN collision OR end_state = 'horizon_unresolved' THEN 0.0 ELSE coalesce(min_ttc, 'Infinity'::DOUBLE) END`
- `required_decel_exceedance`: share of runs with `coalesce(max_required_decel, 0.0) > 3.5`
- `near_miss_1p5s`: share of runs with `NOT collision AND end_state <> 'horizon_unresolved' AND coalesce(min_ttc, 'Infinity'::DOUBLE) < 1.5`

| campaign | distracted_takeover_mean_s | tor_required_decel_mps2 | acc_authority_mps2 | brake_demand_factor | distracted_share | standstill_hold_decel_mps2 | eff_ttc_p01 [s] | eff_ttc_p05 [s] | eff_ttc_p50 [s] | required_decel_exceedance | near_miss_1p5s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sens_factorial2_000 | 4.59 | 3.0 | 3.5 | 1.5 | 0.2 | 2.0 | 0.985; Δ +0.000 [+0.000, +0.000] (MDE 0.000) | 1.855; Δ +0.000 [+0.000, +0.000] (MDE 0.000) | 2.705; Δ +0.000 [+0.000, +0.000] (MDE 0.000) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE 0.00) | 1.35%; Δ +0.00 pp [+0.00, +0.00] (MDE 0.00) |
| sens_factorial2_001 | 3.5 | 2.5 | 3.0 | 1.0 | 0.05 | 1.0 | 0.911; Δ -0.074 [-0.438, +0.253] (MDE 0.521) | 1.055; Δ -0.800 [-0.856, -0.767] (MDE 0.067) | 2.486; Δ -0.218 [-0.261, -0.145] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 30.35%; Δ +29.00 pp [+27.05, +31.10] (MDE 2.91) |
| sens_factorial2_002 | 3.5 | 2.5 | 3.0 | 1.0 | 0.05 | 4.0 | 0.911; Δ -0.074 [-0.438, +0.253] (MDE 0.521) | 1.853; Δ -0.002 [-0.253, +0.074] (MDE 0.261) | 4.968; Δ +2.263 [+1.981, +2.652] (MDE 0.421) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 3.60%; Δ +2.25 pp [+1.40, +3.10] (MDE 1.19) |
| sens_factorial2_003 | 3.5 | 2.5 | 3.0 | 1.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.281, -0.260] (MDE 0.819) | 1.005; Δ -0.850 [-0.900, -0.810] (MDE 0.067) | 2.486; Δ -0.218 [-0.261, -0.145] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 29.10%; Δ +27.75 pp [+25.80, +29.80] (MDE 2.87) |
| sens_factorial2_004 | 3.5 | 2.5 | 3.0 | 1.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.281, -0.260] (MDE 0.819) | 1.234; Δ -0.621 [-0.889, -0.360] (MDE 0.482) | 4.399; Δ +1.694 [+1.487, +1.984] (MDE 0.351) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 4.85%; Δ +3.50 pp [+2.65, +4.35] (MDE 1.24) |
| sens_factorial2_005 | 3.5 | 2.5 | 3.0 | 2.0 | 0.05 | 1.0 | 1.513; Δ +0.528 [+0.141, +0.918] (MDE 0.559) | 2.118; Δ +0.263 [+0.196, +0.311] (MDE 0.085) | 4.294; Δ +1.589 [+1.467, +1.690] (MDE 0.157) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.75%; Δ -0.60 pp [-1.10, -0.10] (MDE 0.68) |
| sens_factorial2_006 | 3.5 | 2.5 | 3.0 | 2.0 | 0.05 | 4.0 | 1.513; Δ +0.528 [+0.141, +0.918] (MDE 0.559) | 2.118; Δ +0.263 [+0.196, +0.311] (MDE 0.085) | 5.667; Δ +2.962 [+2.645, +3.272] (MDE 0.461) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.75%; Δ -0.60 pp [-1.10, -0.10] (MDE 0.68) |
| sens_factorial2_007 | 3.5 | 2.5 | 3.0 | 2.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.281, -0.032] (MDE 0.938) | 1.998; Δ +0.143 [+0.062, +0.190] (MDE 0.095) | 3.993; Δ +1.288 [+1.171, +1.420] (MDE 0.186) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 1.15%; Δ -0.20 pp [-0.70, +0.30] (MDE 0.73) |
| sens_factorial2_008 | 3.5 | 2.5 | 3.0 | 2.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.281, -0.032] (MDE 0.938) | 1.998; Δ +0.143 [+0.062, +0.190] (MDE 0.094) | 4.942; Δ +2.238 [+1.959, +2.556] (MDE 0.394) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 1.15%; Δ -0.20 pp [-0.70, +0.30] (MDE 0.73) |
| sens_factorial2_009 | 3.5 | 2.5 | 4.5 | 1.0 | 0.05 | 1.0 | 0.961; Δ -0.024 [-0.400, +0.318] (MDE 0.541) | 1.060; Δ -0.795 [-0.851, -0.760] (MDE 0.068) | 2.234; Δ -0.471 [-0.523, -0.413] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 31.85%; Δ +30.50 pp [+28.50, +32.55] (MDE 2.94) |
| sens_factorial2_010 | 3.5 | 2.5 | 4.5 | 1.0 | 0.05 | 4.0 | 0.961; Δ -0.024 [-0.400, +0.318] (MDE 0.541) | 1.788; Δ -0.066 [-0.148, -0.024] (MDE 0.092) | 4.946; Δ +2.241 [+1.958, +2.547] (MDE 0.379) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 3.50%; Δ +2.15 pp [+1.35, +3.00] (MDE 1.16) |
| sens_factorial2_011 | 3.5 | 2.5 | 4.5 | 1.0 | 0.4 | 1.0 | 0.924; Δ -0.061 [-0.437, +0.224] (MDE 0.525) | 1.032; Δ -0.823 [-0.878, -0.788] (MDE 0.067) | 2.236; Δ -0.469 [-0.520, -0.412] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 30.90%; Δ +29.55 pp [+27.55, +31.55] (MDE 2.90) |
| sens_factorial2_012 | 3.5 | 2.5 | 4.5 | 1.0 | 0.4 | 4.0 | 0.924; Δ -0.061 [-0.437, +0.224] (MDE 0.525) | 1.485; Δ -0.369 [-0.567, -0.162] (MDE 0.318) | 4.359; Δ +1.654 [+1.392, +1.888] (MDE 0.372) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 4.85%; Δ +3.50 pp [+2.65, +4.35] (MDE 1.22) |
| sens_factorial2_013 | 3.5 | 2.5 | 4.5 | 2.0 | 0.05 | 1.0 | 1.725; Δ +0.739 [+0.352, +0.986] (MDE 0.524) | 1.898; Δ +0.044 [-0.009, +0.084] (MDE 0.071) | 4.223; Δ +1.518 [+1.401, +1.631] (MDE 0.158) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.45%; Δ -0.90 pp [-1.35, -0.40] (MDE 0.68) |
| sens_factorial2_014 | 3.5 | 2.5 | 4.5 | 2.0 | 0.05 | 4.0 | 1.725; Δ +0.739 [+0.352, +0.986] (MDE 0.524) | 1.898; Δ +0.044 [-0.009, +0.084] (MDE 0.071) | 5.518; Δ +2.814 [+2.540, +3.103] (MDE 0.396) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.45%; Δ -0.90 pp [-1.35, -0.40] (MDE 0.68) |
| sens_factorial2_015 | 3.5 | 2.5 | 4.5 | 2.0 | 0.4 | 1.0 | 1.417; Δ +0.432 [+0.037, +0.646] (MDE 0.481) | 1.873; Δ +0.018 [-0.037, +0.052] (MDE 0.067) | 3.898; Δ +1.193 [+1.080, +1.347] (MDE 0.193) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 1.05%; Δ -0.30 pp [-0.80, +0.25] (MDE 0.78) |
| sens_factorial2_016 | 3.5 | 2.5 | 4.5 | 2.0 | 0.4 | 4.0 | 1.417; Δ +0.432 [+0.037, +0.646] (MDE 0.481) | 1.875; Δ +0.021 [-0.036, +0.056] (MDE 0.067) | 4.901; Δ +2.197 [+1.890, +2.419] (MDE 0.376) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 1.05%; Δ -0.30 pp [-0.80, +0.25] (MDE 0.78) |
| sens_factorial2_017 | 3.5 | 3.5 | 3.0 | 1.0 | 0.05 | 1.0 | 0.559; Δ -0.427 [-0.892, -0.124] (MDE 0.582) | 0.962; Δ -0.893 [-0.946, -0.861] (MDE 0.065) | 2.487; Δ -0.218 [-0.259, -0.145] (MDE 0.077) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 20.65%; Δ +19.30 pp [+17.65, +21.10] (MDE 2.51) |
| sens_factorial2_018 | 3.5 | 3.5 | 3.0 | 1.0 | 0.05 | 4.0 | 0.559; Δ -0.427 [-0.892, -0.124] (MDE 0.582) | 0.962; Δ -0.893 [-0.946, -0.861] (MDE 0.065) | 2.501; Δ -0.204 [-0.254, -0.143] (MDE 0.076) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 15.30%; Δ +13.95 pp [+12.45, +15.60] (MDE 2.19) |
| sens_factorial2_019 | 3.5 | 3.5 | 3.0 | 1.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.782; Δ -1.073 [-1.316, -1.001] (MDE 0.209) | 2.487; Δ -0.218 [-0.259, -0.145] (MDE 0.077) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 17.25%; Δ +15.90 pp [+14.30, +17.55] (MDE 2.34) |
| sens_factorial2_020 | 3.5 | 3.5 | 3.0 | 1.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.782; Δ -1.073 [-1.316, -1.001] (MDE 0.209) | 2.497; Δ -0.207 [-0.256, -0.145] (MDE 0.076) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 13.75%; Δ +12.40 pp [+11.00, +13.95] (MDE 2.14) |
| sens_factorial2_021 | 3.5 | 3.5 | 3.0 | 2.0 | 0.05 | 1.0 | 0.559; Δ -0.427 [-0.892, -0.078] (MDE 0.593) | 1.305; Δ -0.550 [-0.657, -0.470] (MDE 0.123) | 2.896; Δ +0.191 [+0.128, +0.290] (MDE 0.115) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 6.95%; Δ +5.60 pp [+4.50, +6.85] (MDE 1.65) |
| sens_factorial2_022 | 3.5 | 3.5 | 3.0 | 2.0 | 0.05 | 4.0 | 0.559; Δ -0.427 [-0.892, -0.078] (MDE 0.593) | 1.305; Δ -0.550 [-0.657, -0.470] (MDE 0.123) | 2.974; Δ +0.270 [+0.160, +0.401] (MDE 0.163) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 6.95%; Δ +5.60 pp [+4.50, +6.85] (MDE 1.65) |
| sens_factorial2_023 | 3.5 | 3.5 | 3.0 | 2.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.851; Δ -1.003 [-1.316, -0.894] (MDE 0.304) | 2.789; Δ +0.084 [+0.029, +0.157] (MDE 0.089) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 7.05%; Δ +5.70 pp [+4.65, +6.80] (MDE 1.57) |
| sens_factorial2_024 | 3.5 | 3.5 | 3.0 | 2.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.851; Δ -1.003 [-1.316, -0.894] (MDE 0.304) | 2.825; Δ +0.121 [+0.041, +0.204] (MDE 0.111) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 7.05%; Δ +5.70 pp [+4.65, +6.80] (MDE 1.57) |
| sens_factorial2_025 | 3.5 | 3.5 | 4.5 | 1.0 | 0.05 | 1.0 | 0.945; Δ -0.040 [-0.417, +0.290] (MDE 0.534) | 1.017; Δ -0.838 [-0.892, -0.801] (MDE 0.068) | 2.248; Δ -0.457 [-0.508, -0.399] (MDE 0.079) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 17.75%; Δ +16.40 pp [+14.85, +18.15] (MDE 2.39) |
| sens_factorial2_026 | 3.5 | 3.5 | 4.5 | 1.0 | 0.05 | 4.0 | 0.945; Δ -0.040 [-0.417, +0.290] (MDE 0.534) | 1.266; Δ -0.588 [-0.681, -0.519] (MDE 0.112) | 2.259; Δ -0.446 [-0.500, -0.392] (MDE 0.078) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 9.65%; Δ +8.30 pp [+7.05, +9.55] (MDE 1.85) |
| sens_factorial2_027 | 3.5 | 3.5 | 4.5 | 1.0 | 0.4 | 1.0 | 0.825; Δ -0.161 [-0.632, +0.067] (MDE 0.546) | 0.998; Δ -0.857 [-0.912, -0.819] (MDE 0.067) | 2.248; Δ -0.457 [-0.508, -0.399] (MDE 0.079) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 16.30%; Δ +14.95 pp [+13.40, +16.55] (MDE 2.27) |
| sens_factorial2_028 | 3.5 | 3.5 | 4.5 | 1.0 | 0.4 | 4.0 | 0.825; Δ -0.161 [-0.632, +0.067] (MDE 0.546) | 0.998; Δ -0.857 [-0.910, -0.663] (MDE 0.190) | 2.257; Δ -0.448 [-0.500, -0.394] (MDE 0.078) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 10.85%; Δ +9.50 pp [+8.15, +10.85] (MDE 1.96) |
| sens_factorial2_029 | 3.5 | 3.5 | 4.5 | 2.0 | 0.05 | 1.0 | 1.300; Δ +0.315 [-0.061, +0.656] (MDE 0.534) | 1.532; Δ -0.322 [-0.379, -0.277] (MDE 0.074) | 2.774; Δ +0.069 [-0.063, +0.162] (MDE 0.158) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 3.85%; Δ +2.50 pp [+1.65, +3.45] (MDE 1.29) |
| sens_factorial2_030 | 3.5 | 3.5 | 4.5 | 2.0 | 0.05 | 4.0 | 1.300; Δ +0.315 [-0.061, +0.656] (MDE 0.534) | 1.532; Δ -0.322 [-0.379, -0.277] (MDE 0.074) | 2.819; Δ +0.115 [-0.055, +0.233] (MDE 0.204) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 3.85%; Δ +2.50 pp [+1.65, +3.45] (MDE 1.29) |
| sens_factorial2_031 | 3.5 | 3.5 | 4.5 | 2.0 | 0.4 | 1.0 | 0.863; Δ -0.122 [-0.632, +0.177] (MDE 0.600) | 1.474; Δ -0.381 [-0.449, -0.345] (MDE 0.074) | 2.602; Δ -0.103 [-0.216, +0.030] (MDE 0.184) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 5.20%; Δ +3.85 pp [+2.90, +4.85] (MDE 1.41) |
| sens_factorial2_032 | 3.5 | 3.5 | 4.5 | 2.0 | 0.4 | 4.0 | 0.863; Δ -0.122 [-0.632, +0.177] (MDE 0.600) | 1.474; Δ -0.381 [-0.449, -0.345] (MDE 0.074) | 2.603; Δ -0.102 [-0.211, +0.075] (MDE 0.219) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 5.20%; Δ +3.85 pp [+2.90, +4.85] (MDE 1.41) |
| sens_factorial2_033 | 6.0 | 2.5 | 3.0 | 1.0 | 0.05 | 1.0 | 0.864; Δ -0.121 [-0.524, +0.146] (MDE 0.531) | 1.049; Δ -0.806 [-0.859, -0.773] (MDE 0.066) | 2.486; Δ -0.218 [-0.261, -0.145] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 29.95%; Δ +28.60 pp [+26.65, +30.65] (MDE 2.89) |
| sens_factorial2_034 | 6.0 | 2.5 | 3.0 | 1.0 | 0.05 | 4.0 | 0.864; Δ -0.121 [-0.524, +0.146] (MDE 0.531) | 1.761; Δ -0.094 [-0.370, +0.050] (MDE 0.314) | 4.947; Δ +2.243 [+1.921, +2.582] (MDE 0.408) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 3.60%; Δ +2.25 pp [+1.45, +3.10] (MDE 1.19) |
| sens_factorial2_035 | 6.0 | 2.5 | 3.0 | 1.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.919; Δ -0.936 [-1.034, -0.899] (MDE 0.102) | 2.486; Δ -0.218 [-0.261, -0.145] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 25.05%; Δ +23.70 pp [+21.75, +25.75] (MDE 2.80) |
| sens_factorial2_036 | 6.0 | 2.5 | 3.0 | 1.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.919; Δ -0.936 [-1.034, -0.899] (MDE 0.102) | 4.166; Δ +1.461 [+1.180, +1.693] (MDE 0.354) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 5.00%; Δ +3.65 pp [+2.70, +4.70] (MDE 1.40) |
| sens_factorial2_037 | 6.0 | 2.5 | 3.0 | 2.0 | 0.05 | 1.0 | 1.287; Δ +0.301 [-0.396, +0.586] (MDE 0.710) | 2.091; Δ +0.237 [+0.171, +0.287] (MDE 0.082) | 4.283; Δ +1.578 [+1.461, +1.684] (MDE 0.161) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.85%; Δ -0.50 pp [-0.95, +0.00] (MDE 0.73) |
| sens_factorial2_038 | 6.0 | 2.5 | 3.0 | 2.0 | 0.05 | 4.0 | 1.287; Δ +0.301 [-0.396, +0.586] (MDE 0.710) | 2.091; Δ +0.237 [+0.171, +0.287] (MDE 0.082) | 5.610; Δ +2.905 [+2.577, +3.232] (MDE 0.467) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.85%; Δ -0.50 pp [-0.95, +0.00] (MDE 0.73) |
| sens_factorial2_039 | 6.0 | 2.5 | 3.0 | 2.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 1.361; Δ -0.494 [-0.864, -0.316] (MDE 0.394) | 3.856; Δ +1.152 [+0.993, +1.332] (MDE 0.230) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 2.60%; Δ +1.25 pp [+0.50, +2.05] (MDE 1.07) |
| sens_factorial2_040 | 6.0 | 2.5 | 3.0 | 2.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 1.361; Δ -0.494 [-0.864, -0.316] (MDE 0.394) | 4.533; Δ +1.828 [+1.631, +2.141] (MDE 0.352) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 2.60%; Δ +1.25 pp [+0.50, +2.05] (MDE 1.07) |
| sens_factorial2_041 | 6.0 | 2.5 | 4.5 | 1.0 | 0.05 | 1.0 | 0.933; Δ -0.052 [-0.415, +0.282] (MDE 0.528) | 1.058; Δ -0.797 [-0.852, -0.761] (MDE 0.068) | 2.234; Δ -0.471 [-0.523, -0.413] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 31.65%; Δ +30.30 pp [+28.35, +32.30] (MDE 2.93) |
| sens_factorial2_042 | 6.0 | 2.5 | 4.5 | 1.0 | 0.05 | 4.0 | 0.933; Δ -0.052 [-0.415, +0.282] (MDE 0.528) | 1.764; Δ -0.091 [-0.232, -0.037] (MDE 0.116) | 4.925; Δ +2.220 [+1.931, +2.486] (MDE 0.390) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 3.60%; Δ +2.25 pp [+1.45, +3.10] (MDE 1.18) |
| sens_factorial2_043 | 6.0 | 2.5 | 4.5 | 1.0 | 0.4 | 1.0 | 0.276; Δ -0.709 [-1.239, -0.446] (MDE 0.597) | 1.008; Δ -0.847 [-0.902, -0.810] (MDE 0.069) | 2.244; Δ -0.460 [-0.514, -0.407] (MDE 0.079) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 28.15%; Δ +26.80 pp [+24.90, +28.65] (MDE 2.82) |
| sens_factorial2_044 | 6.0 | 2.5 | 4.5 | 1.0 | 0.4 | 4.0 | 0.276; Δ -0.709 [-1.239, -0.411] (MDE 0.588) | 1.120; Δ -0.735 [-0.897, -0.464] (MDE 0.387) | 4.064; Δ +1.359 [+1.000, +1.618] (MDE 0.441) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 5.60%; Δ +4.25 pp [+3.30, +5.20] (MDE 1.35) |
| sens_factorial2_045 | 6.0 | 2.5 | 4.5 | 2.0 | 0.05 | 1.0 | 1.583; Δ +0.598 [+0.235, +0.871] (MDE 0.501) | 1.881; Δ +0.026 [-0.022, +0.064] (MDE 0.067) | 4.218; Δ +1.514 [+1.389, +1.620] (MDE 0.161) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.70%; Δ -0.65 pp [-1.10, -0.15] (MDE 0.71) |
| sens_factorial2_046 | 6.0 | 2.5 | 4.5 | 2.0 | 0.05 | 4.0 | 1.583; Δ +0.598 [+0.235, +0.871] (MDE 0.501) | 1.881; Δ +0.026 [-0.022, +0.064] (MDE 0.067) | 5.489; Δ +2.784 [+2.494, +3.058] (MDE 0.388) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 0.70%; Δ -0.65 pp [-1.10, -0.15] (MDE 0.71) |
| sens_factorial2_047 | 6.0 | 2.5 | 4.5 | 2.0 | 0.4 | 1.0 | 0.276; Δ -0.709 [-1.239, -0.411] (MDE 0.588) | 1.723; Δ -0.131 [-0.245, -0.097] (MDE 0.096) | 3.761; Δ +1.057 [+0.909, +1.249] (MDE 0.236) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 2.65%; Δ +1.30 pp [+0.65, +1.95] (MDE 0.90) |
| sens_factorial2_048 | 6.0 | 2.5 | 4.5 | 2.0 | 0.4 | 4.0 | 0.276; Δ -0.709 [-1.239, -0.411] (MDE 0.588) | 1.723; Δ -0.131 [-0.245, -0.097] (MDE 0.096) | 4.497; Δ +1.792 [+1.502, +2.043] (MDE 0.364) | 1.50%; Δ +0.00 pp [+0.00, +0.00] (MDE n/a: no run differs) | 2.65%; Δ +1.30 pp [+0.65, +1.95] (MDE 0.90) |
| sens_factorial2_049 | 6.0 | 3.5 | 3.0 | 1.0 | 0.05 | 1.0 | 0.000; Δ -0.985 [-1.307, -0.495] (MDE 0.671) | 0.962; Δ -0.893 [-0.947, -0.862] (MDE 0.065) | 2.487; Δ -0.218 [-0.259, -0.145] (MDE 0.077) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 20.10%; Δ +18.75 pp [+17.15, +20.55] (MDE 2.49) |
| sens_factorial2_050 | 6.0 | 3.5 | 3.0 | 1.0 | 0.05 | 4.0 | 0.000; Δ -0.985 [-1.307, -0.495] (MDE 0.671) | 0.962; Δ -0.893 [-0.947, -0.862] (MDE 0.065) | 2.501; Δ -0.204 [-0.254, -0.143] (MDE 0.076) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 14.75%; Δ +13.40 pp [+11.95, +15.00] (MDE 2.18) |
| sens_factorial2_051 | 6.0 | 3.5 | 3.0 | 1.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.000; Δ -1.855 [-1.906, -1.814] (MDE 0.070) | 2.487; Δ -0.218 [-0.259, -0.145] (MDE 0.077) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 13.95%; Δ +12.60 pp [+11.10, +14.20] (MDE 2.21) |
| sens_factorial2_052 | 6.0 | 3.5 | 3.0 | 1.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.000; Δ -1.855 [-1.906, -1.814] (MDE 0.070) | 2.497; Δ -0.207 [-0.256, -0.145] (MDE 0.076) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 10.40%; Δ +9.05 pp [+7.65, +10.50] (MDE 1.98) |
| sens_factorial2_053 | 6.0 | 3.5 | 3.0 | 2.0 | 0.05 | 1.0 | 0.000; Δ -0.985 [-1.307, -0.436] (MDE 0.673) | 1.286; Δ -0.569 [-0.693, -0.500] (MDE 0.135) | 2.894; Δ +0.189 [+0.126, +0.288] (MDE 0.114) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 6.70%; Δ +5.35 pp [+4.20, +6.55] (MDE 1.65) |
| sens_factorial2_054 | 6.0 | 3.5 | 3.0 | 2.0 | 0.05 | 4.0 | 0.000; Δ -0.985 [-1.307, -0.436] (MDE 0.673) | 1.286; Δ -0.569 [-0.693, -0.500] (MDE 0.135) | 2.966; Δ +0.261 [+0.159, +0.401] (MDE 0.165) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 6.70%; Δ +5.35 pp [+4.20, +6.55] (MDE 1.65) |
| sens_factorial2_055 | 6.0 | 3.5 | 3.0 | 2.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.000; Δ -1.855 [-1.906, -1.814] (MDE 0.070) | 2.766; Δ +0.061 [-0.000, +0.133] (MDE 0.094) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 5.50%; Δ +4.15 pp [+3.15, +5.25] (MDE 1.52) |
| sens_factorial2_056 | 6.0 | 3.5 | 3.0 | 2.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.548) | 0.000; Δ -1.855 [-1.906, -1.814] (MDE 0.070) | 2.789; Δ +0.084 [+0.000, +0.172] (MDE 0.122) | 14.55%; Δ +13.05 pp [+11.55, +14.60] (MDE 2.15) | 5.50%; Δ +4.15 pp [+3.15, +5.25] (MDE 1.52) |
| sens_factorial2_057 | 6.0 | 3.5 | 4.5 | 1.0 | 0.05 | 1.0 | 0.922; Δ -0.063 [-0.439, +0.257] (MDE 0.518) | 1.016; Δ -0.839 [-0.893, -0.802] (MDE 0.067) | 2.248; Δ -0.457 [-0.508, -0.399] (MDE 0.079) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 17.55%; Δ +16.20 pp [+14.55, +17.90] (MDE 2.39) |
| sens_factorial2_058 | 6.0 | 3.5 | 4.5 | 1.0 | 0.05 | 4.0 | 0.922; Δ -0.063 [-0.439, +0.257] (MDE 0.518) | 1.265; Δ -0.590 [-0.688, -0.522] (MDE 0.121) | 2.259; Δ -0.446 [-0.500, -0.392] (MDE 0.078) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 9.45%; Δ +8.10 pp [+6.90, +9.35] (MDE 1.85) |
| sens_factorial2_059 | 6.0 | 3.5 | 4.5 | 1.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.546) | 0.974; Δ -0.881 [-0.933, -0.842] (MDE 0.068) | 2.248; Δ -0.457 [-0.508, -0.399] (MDE 0.079) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 15.00%; Δ +13.65 pp [+12.00, +15.25] (MDE 2.24) |
| sens_factorial2_060 | 6.0 | 3.5 | 4.5 | 1.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.546) | 0.974; Δ -0.881 [-0.933, -0.776] (MDE 0.102) | 2.257; Δ -0.448 [-0.500, -0.394] (MDE 0.078) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 9.65%; Δ +8.30 pp [+7.00, +9.70] (MDE 1.91) |
| sens_factorial2_061 | 6.0 | 3.5 | 4.5 | 2.0 | 0.05 | 1.0 | 1.268; Δ +0.282 [-0.133, +0.515] (MDE 0.509) | 1.522; Δ -0.332 [-0.392, -0.289] (MDE 0.073) | 2.772; Δ +0.067 [-0.079, +0.150] (MDE 0.159) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 4.00%; Δ +2.65 pp [+1.80, +3.70] (MDE 1.34) |
| sens_factorial2_062 | 6.0 | 3.5 | 4.5 | 2.0 | 0.05 | 4.0 | 1.268; Δ +0.282 [-0.133, +0.515] (MDE 0.509) | 1.522; Δ -0.332 [-0.392, -0.289] (MDE 0.073) | 2.798; Δ +0.094 [-0.070, +0.223] (MDE 0.205) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 4.00%; Δ +2.65 pp [+1.80, +3.70] (MDE 1.34) |
| sens_factorial2_063 | 6.0 | 3.5 | 4.5 | 2.0 | 0.4 | 1.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.546) | 1.325; Δ -0.530 [-0.601, -0.466] (MDE 0.096) | 2.516; Δ -0.189 [-0.281, -0.034] (MDE 0.180) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 6.25%; Δ +4.90 pp [+3.90, +6.10] (MDE 1.55) |
| sens_factorial2_064 | 6.0 | 3.5 | 4.5 | 2.0 | 0.4 | 4.0 | 0.000; Δ -0.985 [-1.361, -0.638] (MDE 0.546) | 1.325; Δ -0.530 [-0.601, -0.466] (MDE 0.096) | 2.522; Δ -0.183 [-0.279, +0.005] (MDE 0.199) | 11.10%; Δ +9.60 pp [+8.35, +10.95] (MDE 1.83) | 6.25%; Δ +4.90 pp [+3.90, +6.10] (MDE 1.55) |

Detectable effects declared in the protocol (conservative, unpaired, n = 2000): `eff_ttc_p01` 0.78 s; `eff_ttc_p05` 0.11 s; `eff_ttc_p50` 0.20 s; `required_decel_exceedance` 1.2 percentage points (about 70% relative); `near_miss_1p5s` 1.1 percentage points (about 75% relative); `secondary_attentive_collision_rate` 0.28 percentage points (about 280% relative): not informative on its own.

## Factorial effects on eff_ttc_p01 (primary)

| term | effect (high - low) |
| --- | --- |
| distracted_share | -0.672 |
| acc_authority_mps2 | 0.533 |
| tor_required_decel_mps2 | -0.339 |
| distracted_takeover_mean_s | -0.318 |
| brake_demand_factor | 0.229 |
| tor_required_decel_mps2 x distracted_share | 0.189 |
| brake_demand_factor x distracted_share | -0.163 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.144 |
| tor_required_decel_mps2 x brake_demand_factor | -0.137 |
| distracted_takeover_mean_s x distracted_share | -0.116 |
| acc_authority_mps2 x brake_demand_factor | 0.101 |
| tor_required_decel_mps2 x acc_authority_mps2 | 0.093 |
| distracted_takeover_mean_s x brake_demand_factor | -0.052 |
| acc_authority_mps2 x distracted_share | 0.04 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.039 |
| distracted_share x standstill_hold_decel_mps2 | 0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.0 |
| standstill_hold_decel_mps2 | 0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | 0.0 |

## Factorial effects on eff_ttc_p05 (primary)

| term | effect (high - low) |
| --- | --- |
| tor_required_decel_mps2 | -0.547 |
| brake_demand_factor | 0.452 |
| distracted_share | -0.363 |
| acc_authority_mps2 | 0.252 |
| tor_required_decel_mps2 x acc_authority_mps2 | 0.243 |
| acc_authority_mps2 x distracted_share | 0.206 |
| distracted_takeover_mean_s | -0.195 |
| distracted_takeover_mean_s x distracted_share | -0.178 |
| tor_required_decel_mps2 x brake_demand_factor | -0.16 |
| standstill_hold_decel_mps2 | 0.133 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.132 |
| distracted_takeover_mean_s x acc_authority_mps2 | 0.125 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.101 |
| distracted_share x standstill_hold_decel_mps2 | -0.083 |
| tor_required_decel_mps2 x distracted_share | -0.068 |
| distracted_takeover_mean_s x brake_demand_factor | -0.037 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.034 |
| acc_authority_mps2 x brake_demand_factor | 0.026 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | 0.024 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | -0.021 |
| brake_demand_factor x distracted_share | -0.015 |

## Factorial effects on eff_ttc_p50 (primary)

| term | effect (high - low) |
| --- | --- |
| tor_required_decel_mps2 | -1.471 |
| standstill_hold_decel_mps2 | 0.84 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.817 |
| brake_demand_factor | 0.761 |
| tor_required_decel_mps2 x brake_demand_factor | -0.365 |
| distracted_share | -0.287 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.283 |
| tor_required_decel_mps2 x distracted_share | 0.194 |
| acc_authority_mps2 | -0.165 |
| distracted_share x standstill_hold_decel_mps2 | -0.152 |
| brake_demand_factor x distracted_share | -0.113 |
| distracted_takeover_mean_s | -0.063 |
| distracted_takeover_mean_s x distracted_share | -0.052 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.049 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | 0.047 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | -0.038 |
| acc_authority_mps2 x brake_demand_factor | 0.029 |
| distracted_takeover_mean_s x brake_demand_factor | -0.028 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | 0.02 |
| acc_authority_mps2 x distracted_share | -0.009 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.004 |

## Factorial effects on required_decel_exceedance (primary)

| term | effect (high - low) |
| --- | --- |
| tor_required_decel_mps2 | 0.113 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.017 |
| acc_authority_mps2 | -0.017 |
| standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | -0.0 |
| distracted_share | -0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | -0.0 |
| brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.0 |
| distracted_takeover_mean_s | 0.0 |
| tor_required_decel_mps2 x brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.0 |
| brake_demand_factor x distracted_share | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x distracted_share | 0.0 |
| distracted_share x standstill_hold_decel_mps2 | 0.0 |
| distracted_takeover_mean_s x distracted_share | -0.0 |
| acc_authority_mps2 x distracted_share | -0.0 |

## Factorial effects on near_miss_1p5s (primary)

| term | effect (high - low) |
| --- | --- |
| brake_demand_factor | -0.123 |
| standstill_hold_decel_mps2 | -0.077 |
| brake_demand_factor x standstill_hold_decel_mps2 | 0.077 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | 0.049 |
| tor_required_decel_mps2 x brake_demand_factor | 0.034 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.013 |
| brake_demand_factor x distracted_share | 0.012 |
| tor_required_decel_mps2 | 0.01 |
| acc_authority_mps2 | -0.008 |
| distracted_share x standstill_hold_decel_mps2 | 0.008 |
| acc_authority_mps2 x distracted_share | 0.008 |
| distracted_takeover_mean_s x brake_demand_factor | 0.007 |
| tor_required_decel_mps2 x distracted_share | -0.006 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | -0.005 |
| distracted_takeover_mean_s x acc_authority_mps2 | 0.004 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.004 |
| distracted_takeover_mean_s | -0.004 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | 0.003 |
| distracted_takeover_mean_s x distracted_share | -0.003 |
| distracted_share | -0.003 |
| acc_authority_mps2 x brake_demand_factor | -0.001 |

## Secondary responses: collision counts and acceptance statuses

Rare-event results at 2000 runs per variant: most acceptance statuses are INSUFFICIENT EVIDENCE or decided by a handful of events, so they are not informative on their own and are not the basis of any sensitivity conclusion.

| campaign | distracted_takeover_mean_s | tor_required_decel_mps2 | acc_authority_mps2 | brake_demand_factor | distracted_share | standstill_hold_decel_mps2 | note | attentive_collisions | attentive_runs | AC-01_status | AC-02_status | AC-03_status | AC-04_status | AC-07_status | AC-08_status | AC-09_status | AC-10_status | AC-06_status | AC-02-S_status | AC-03-C_status | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sens_factorial2_000 | 4.59 | 3.0 | 3.5 | 1.5 | 0.2 | 2.0 |  | 1 | 1597 | FAIL | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | PASS | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_001 | 3.5 | 2.5 | 3.0 | 1.0 | 0.05 | 1.0 |  | 2 | 1888 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_002 | 3.5 | 2.5 | 3.0 | 1.0 | 0.05 | 4.0 |  | 2 | 1888 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_003 | 3.5 | 2.5 | 3.0 | 1.0 | 0.4 | 1.0 |  | 1 | 1193 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_004 | 3.5 | 2.5 | 3.0 | 1.0 | 0.4 | 4.0 |  | 1 | 1193 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_005 | 3.5 | 2.5 | 3.0 | 2.0 | 0.05 | 1.0 |  | 2 | 1888 | FAIL | PASS | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_006 | 3.5 | 2.5 | 3.0 | 2.0 | 0.05 | 4.0 |  | 2 | 1888 | FAIL | PASS | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_007 | 3.5 | 2.5 | 3.0 | 2.0 | 0.4 | 1.0 |  | 1 | 1193 | FAIL | PASS | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_008 | 3.5 | 2.5 | 3.0 | 2.0 | 0.4 | 4.0 |  | 1 | 1193 | FAIL | PASS | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_009 | 3.5 | 2.5 | 4.5 | 1.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_010 | 3.5 | 2.5 | 4.5 | 1.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_011 | 3.5 | 2.5 | 4.5 | 1.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_012 | 3.5 | 2.5 | 4.5 | 1.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_013 | 3.5 | 2.5 | 4.5 | 2.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_014 | 3.5 | 2.5 | 4.5 | 2.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_015 | 3.5 | 2.5 | 4.5 | 2.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_016 | 3.5 | 2.5 | 4.5 | 2.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_017 | 3.5 | 3.5 | 3.0 | 1.0 | 0.05 | 1.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_018 | 3.5 | 3.5 | 3.0 | 1.0 | 0.05 | 4.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_019 | 3.5 | 3.5 | 3.0 | 1.0 | 0.4 | 1.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_020 | 3.5 | 3.5 | 3.0 | 1.0 | 0.4 | 4.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_021 | 3.5 | 3.5 | 3.0 | 2.0 | 0.05 | 1.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_022 | 3.5 | 3.5 | 3.0 | 2.0 | 0.05 | 4.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_023 | 3.5 | 3.5 | 3.0 | 2.0 | 0.4 | 1.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_024 | 3.5 | 3.5 | 3.0 | 2.0 | 0.4 | 4.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_025 | 3.5 | 3.5 | 4.5 | 1.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_026 | 3.5 | 3.5 | 4.5 | 1.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_027 | 3.5 | 3.5 | 4.5 | 1.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_028 | 3.5 | 3.5 | 4.5 | 1.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_029 | 3.5 | 3.5 | 4.5 | 2.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_030 | 3.5 | 3.5 | 4.5 | 2.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_031 | 3.5 | 3.5 | 4.5 | 2.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_032 | 3.5 | 3.5 | 4.5 | 2.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_033 | 6.0 | 2.5 | 3.0 | 1.0 | 0.05 | 1.0 |  | 2 | 1888 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_034 | 6.0 | 2.5 | 3.0 | 1.0 | 0.05 | 4.0 |  | 2 | 1888 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_035 | 6.0 | 2.5 | 3.0 | 1.0 | 0.4 | 1.0 |  | 1 | 1193 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_036 | 6.0 | 2.5 | 3.0 | 1.0 | 0.4 | 4.0 |  | 1 | 1193 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_037 | 6.0 | 2.5 | 3.0 | 2.0 | 0.05 | 1.0 |  | 2 | 1888 | FAIL | PASS | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_038 | 6.0 | 2.5 | 3.0 | 2.0 | 0.05 | 4.0 |  | 2 | 1888 | FAIL | PASS | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_039 | 6.0 | 2.5 | 3.0 | 2.0 | 0.4 | 1.0 |  | 1 | 1193 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_040 | 6.0 | 2.5 | 3.0 | 2.0 | 0.4 | 4.0 |  | 1 | 1193 | FAIL | FAIL | FAIL | PASS | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_041 | 6.0 | 2.5 | 4.5 | 1.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_042 | 6.0 | 2.5 | 4.5 | 1.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_043 | 6.0 | 2.5 | 4.5 | 1.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_044 | 6.0 | 2.5 | 4.5 | 1.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_045 | 6.0 | 2.5 | 4.5 | 2.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_046 | 6.0 | 2.5 | 4.5 | 2.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | PASS | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_047 | 6.0 | 2.5 | 4.5 | 2.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | INSUFFICIENT EVIDENCE | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_048 | 6.0 | 2.5 | 4.5 | 2.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | INSUFFICIENT EVIDENCE | FAIL | FAIL | INSUFFICIENT EVIDENCE | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_049 | 6.0 | 3.5 | 3.0 | 1.0 | 0.05 | 1.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_050 | 6.0 | 3.5 | 3.0 | 1.0 | 0.05 | 4.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_051 | 6.0 | 3.5 | 3.0 | 1.0 | 0.4 | 1.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_052 | 6.0 | 3.5 | 3.0 | 1.0 | 0.4 | 4.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_053 | 6.0 | 3.5 | 3.0 | 2.0 | 0.05 | 1.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_054 | 6.0 | 3.5 | 3.0 | 2.0 | 0.05 | 4.0 |  | 3 | 1888 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_055 | 6.0 | 3.5 | 3.0 | 2.0 | 0.4 | 1.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_056 | 6.0 | 3.5 | 3.0 | 2.0 | 0.4 | 4.0 |  | 2 | 1193 | FAIL | FAIL | FAIL | PASS | FAIL | INSUFFICIENT EVIDENCE | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_057 | 6.0 | 3.5 | 4.5 | 1.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_058 | 6.0 | 3.5 | 4.5 | 1.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_059 | 6.0 | 3.5 | 4.5 | 1.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_060 | 6.0 | 3.5 | 4.5 | 1.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_061 | 6.0 | 3.5 | 4.5 | 2.0 | 0.05 | 1.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_062 | 6.0 | 3.5 | 4.5 | 2.0 | 0.05 | 4.0 | policy re-trained for authority 4.5 | 0 | 1888 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_063 | 6.0 | 3.5 | 4.5 | 2.0 | 0.4 | 1.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |
| sens_factorial2_064 | 6.0 | 3.5 | 4.5 | 2.0 | 0.4 | 4.0 | policy re-trained for authority 4.5 | 0 | 1193 | INSUFFICIENT EVIDENCE | FAIL | FAIL | FAIL | FAIL | FAIL | NO REQUIREMENT | NO REQUIREMENT | INFO | INFO | INFO | NO-GO |

### Factorial effects on AC-01 (secondary)

| term | effect (high - low) |
| --- | --- |
| acc_authority_mps2 | -0.001 |
| tor_required_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.0 |
| tor_required_decel_mps2 x distracted_share | 0.0 |
| acc_authority_mps2 x distracted_share | 0.0 |
| distracted_share | -0.0 |
| tor_required_decel_mps2 x brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | -0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s | -0.0 |
| brake_demand_factor x distracted_share | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | 0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.0 |
| standstill_hold_decel_mps2 | 0.0 |
| brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x distracted_share | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | 0.0 |
| distracted_share x standstill_hold_decel_mps2 | -0.0 |

### Factorial effects on AC-03 (secondary)

| term | effect (high - low) |
| --- | --- |
| acc_authority_mps2 | -0.065 |
| distracted_takeover_mean_s | 0.049 |
| tor_required_decel_mps2 | 0.048 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.029 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.025 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | 0.014 |
| tor_required_decel_mps2 x distracted_share | -0.003 |
| distracted_share | -0.003 |
| distracted_takeover_mean_s x distracted_share | -0.003 |
| acc_authority_mps2 x distracted_share | -0.0 |
| brake_demand_factor x distracted_share | -0.0 |
| distracted_share x standstill_hold_decel_mps2 | -0.0 |
| standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | 0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | 0.0 |
| brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| tor_required_decel_mps2 x brake_demand_factor | -0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | -0.0 |

### Factorial effects on AC-07 (secondary)

| term | effect (high - low) |
| --- | --- |
| tor_required_decel_mps2 | 0.073 |
| standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| distracted_share x standstill_hold_decel_mps2 | 0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | -0.0 |
| brake_demand_factor | -0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | -0.0 |
| acc_authority_mps2 x distracted_share | 0.0 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.0 |
| tor_required_decel_mps2 x distracted_share | -0.0 |
| distracted_share | 0.0 |
| distracted_takeover_mean_s x distracted_share | -0.0 |
| acc_authority_mps2 | 0.0 |
| tor_required_decel_mps2 x brake_demand_factor | 0.0 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.0 |
| brake_demand_factor x distracted_share | 0.0 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.0 |
| distracted_takeover_mean_s | -0.0 |

### Factorial effects on AC-08 (secondary)

| term | effect (high - low) |
| --- | --- |
| acc_authority_mps2 | 0.104 |
| tor_required_decel_mps2 | -0.041 |
| tor_required_decel_mps2 x acc_authority_mps2 | 0.015 |
| acc_authority_mps2 x distracted_share | -0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.0 |
| brake_demand_factor | 0.0 |
| distracted_share x standstill_hold_decel_mps2 | -0.0 |
| standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x distracted_share | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | -0.0 |
| distracted_share | 0.0 |
| distracted_takeover_mean_s x distracted_share | -0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| brake_demand_factor x distracted_share | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | -0.0 |
| tor_required_decel_mps2 x brake_demand_factor | 0.0 |
| distracted_takeover_mean_s | 0.0 |

### Factorial effects on AC-09 (secondary)

| term | effect (high - low) |
| --- | --- |
| acc_authority_mps2 | -0.001 |
| tor_required_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.0 |
| tor_required_decel_mps2 x distracted_share | 0.0 |
| acc_authority_mps2 x distracted_share | 0.0 |
| distracted_share | -0.0 |
| tor_required_decel_mps2 x brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | -0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s | -0.0 |
| brake_demand_factor x distracted_share | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | 0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | -0.0 |
| standstill_hold_decel_mps2 | 0.0 |
| brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x distracted_share | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | 0.0 |
| distracted_share x standstill_hold_decel_mps2 | -0.0 |

### Factorial effects on AC-10 (secondary)

| term | effect (high - low) |
| --- | --- |
| acc_authority_mps2 | -0.065 |
| distracted_takeover_mean_s | 0.049 |
| tor_required_decel_mps2 | 0.048 |
| tor_required_decel_mps2 x acc_authority_mps2 | -0.029 |
| distracted_takeover_mean_s x acc_authority_mps2 | -0.025 |
| distracted_takeover_mean_s x tor_required_decel_mps2 | 0.014 |
| tor_required_decel_mps2 x distracted_share | -0.003 |
| distracted_share | -0.003 |
| distracted_takeover_mean_s x distracted_share | -0.003 |
| acc_authority_mps2 x distracted_share | -0.0 |
| brake_demand_factor x distracted_share | -0.0 |
| distracted_share x standstill_hold_decel_mps2 | -0.0 |
| standstill_hold_decel_mps2 | -0.0 |
| distracted_takeover_mean_s x brake_demand_factor | 0.0 |
| brake_demand_factor x standstill_hold_decel_mps2 | 0.0 |
| brake_demand_factor | -0.0 |
| distracted_takeover_mean_s x standstill_hold_decel_mps2 | 0.0 |
| tor_required_decel_mps2 x standstill_hold_decel_mps2 | -0.0 |
| tor_required_decel_mps2 x brake_demand_factor | -0.0 |
| acc_authority_mps2 x brake_demand_factor | -0.0 |
| acc_authority_mps2 x standstill_hold_decel_mps2 | -0.0 |
