# Post-hoc check of the agent's triggering conditions

Every predicate the agent submitted, re-evaluated on the held-out estimation campaign `estimate` (100,000 exposure-weighted runs the agent never saw). Target: the failure predicate `collision OR coalesce(min_ttc < 1.5, false)`. The interval is a 95% Clopper-Pearson interval on the failure rate inside the predicate. The reference is the box around the AC-01 collisions of the estimation: `scenario = 'cut_in' AND headway <= 0.73 AND closing_speed >= 6.1`. AC-01 events: `collision AND preventable AND driver_state = 'attentive'`.

| source | TC | predicate | runs inside | failure rate inside [95% CI] | failure rate outside | lift | share of all failures inside | AC-01 events inside |
|---|---|---|---|---|---|---|---|---|
| reference | - | `scenario = 'cut_in' AND headway <= 0.73 AND closing_speed >= 6.1` | 919 | 38.7% [35.6%, 42.0%] | 1.46% | 26.5 | 19.7% | 61 / 67 |
| agent_s0 | TC-01 | `scenario = 'cut_in' AND headway < 0.45 AND closing_speed >= 8 AND ego_speed >= 22` | 99 | 93.9% [87.3%, 97.7%] | 1.71% | 54.8 | 5.2% | 18 / 67 |
| agent_s0 | TC-02 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND headway < 1.6 AND lead_decel > 5` | 425 | 80.5% [76.4%, 84.1%] | 1.47% | 54.8 | 19.0% | 0 / 67 |
| agent_s1 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5` | 1,855 | 52.6% [50.3%, 54.9%] | 0.84% | 62.4 | 54.1% | 0 / 67 |
| agent_s1 | TC-02 | `scenario = 'cut_in' AND headway <= 0.6 AND closing_speed >= 6` | 662 | 51.2% [47.3%, 55.1%] | 1.47% | 34.7 | 18.8% | 62 / 67 |
| agent_s2 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 5` | 1,855 | 52.6% [50.3%, 54.9%] | 0.84% | 62.4 | 54.1% | 0 / 67 |
| agent_s2 | TC-02 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 6` | 227 | 78.0% [72.0%, 83.2%] | 1.63% | 47.8 | 9.8% | 45 / 67 |
| agent_s3 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND friction >= 0.75` | 520 | 72.3% [68.2%, 76.1%] | 1.44% | 50.4 | 20.8% | 0 / 67 |
| agent_s3 | TC-02 | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 9 AND friction >= 1.0 AND headway <= 0.8` | 0 | - | 1.80% | - | 0.0% | 0 / 67 |
| agent_s3 | TC-03 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 9` | 0 | - | 1.80% | - | 0.0% | 0 / 67 |
| agent_s4 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75` | 2,196 | 48.5% [46.4%, 50.7%] | 0.75% | 64.3 | 59.1% | 0 / 67 |
| agent_s4 | TC-02 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND takeover_time >= 3.0` | 551 | 80.4% [76.8%, 83.6%] | 1.37% | 58.7 | 24.6% | 0 / 67 |
| agent_s4 | TC-03 | `scenario='cut_in' AND headway<=0.5 AND closing_speed>=6.0` | 453 | 62.5% [57.8%, 66.9%] | 1.53% | 40.9 | 15.7% | 55 / 67 |
| agent_s5 | TC-01 | `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 6` | 1,104 | 33.7% [30.9%, 36.6%] | 1.45% | 23.3 | 20.6% | 63 / 67 |
| agent_s5 | TC-02 | `scenario = 'cut_in' AND headway < 0.8 AND closing_speed >= 9` | 0 | - | 1.80% | - | 0.0% | 0 / 67 |
| agent_s5 | TC-03 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 1.9` | 265 | 91.3% [87.3%, 94.4%] | 1.57% | 58.3 | 13.4% | 0 / 67 |
| agent_s6 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 4.75 AND headway < 2.6 AND ego_speed >= 22` | 1,368 | 59.4% [56.7%, 62.0%] | 1.01% | 59.0 | 45.0% | 0 / 67 |
| agent_s6 | TC-02 | `scenario = 'cut_in' AND initial_gap_m / closing_speed < 1.5` | 443 | 100.0% [99.2%, 100.0%] | 1.37% | 73.1 | 24.6% | 63 / 67 |
| agent_s6 | TC-03 | `scenario = 'lead_brake' AND driver_state = 'attentive'` | 48,011 | 0.2% [0.1%, 0.2%] | 3.30% | 0.1 | 4.9% | 4 / 67 |
| agent_s7 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.0` | 295 | 90.5% [86.6%, 93.6%] | 1.54% | 58.7 | 14.8% | 0 / 67 |
| agent_s7 | TC-02 | `scenario = 'cut_in' AND headway < 0.5 AND closing_speed >= 8` | 160 | 87.5% [81.4%, 92.2%] | 1.67% | 52.5 | 7.8% | 35 / 67 |
| agent_s8 | TC-01 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6` | 645 | 71.0% [67.3%, 74.5%] | 1.35% | 52.4 | 25.4% | 0 / 67 |
| agent_s8 | TC-02 | `scenario='cut_in' AND headway<=0.6 AND closing_speed>=7` | 454 | 60.4% [55.7%, 64.9%] | 1.54% | 39.3 | 15.2% | 54 / 67 |
| agent_s9 | TC-01 | `scenario = 'cut_in' AND initial_gap_m <= 14.5 AND closing_speed >= 9` | 0 | - | 1.80% | - | 0.0% | 0 / 67 |
| agent_s9 | TC-02 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.3` | 400 | 87.5% [83.9%, 90.6%] | 1.46% | 59.9 | 19.4% | 0 / 67 |

## Comparison with the reference

Overlap counts runs in both. Precision is the failure rate inside (above).

| source | TC | overlap runs | share of predicate inside reference | share of reference covered | share of reference failures covered | boundary vs reference |
|---|---|---|---|---|---|---|
| agent_s0 | TC-01 | 99 | 100.0% | 10.8% | 26.1% | tighter (inside the reference) |
| agent_s0 | TC-02 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s1 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s1 | TC-02 | 639 | 96.5% | 69.5% | 93.0% | overlapping (neither contains the other) |
| agent_s2 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s2 | TC-02 | 220 | 96.9% | 23.9% | 48.3% | overlapping (neither contains the other) |
| agent_s3 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s3 | TC-02 | 0 | - | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s3 | TC-03 | 0 | - | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s4 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s4 | TC-02 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s4 | TC-03 | 437 | 96.5% | 47.6% | 77.5% | overlapping (neither contains the other) |
| agent_s5 | TC-01 | 919 | 83.2% | 100.0% | 100.0% | looser (contains the reference) |
| agent_s5 | TC-02 | 0 | - | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s5 | TC-03 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s6 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s6 | TC-02 | 287 | 64.8% | 31.2% | 80.6% | overlapping (neither contains the other) |
| agent_s6 | TC-03 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s7 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s7 | TC-02 | 160 | 100.0% | 17.4% | 39.3% | tighter (inside the reference) |
| agent_s8 | TC-01 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s8 | TC-02 | 454 | 100.0% | 49.4% | 77.0% | tighter (inside the reference) |
| agent_s9 | TC-01 | 0 | - | 0.0% | 0.0% | disjoint (a different failure mode) |
| agent_s9 | TC-02 | 0 | 0.0% | 0.0% | 0.0% | disjoint (a different failure mode) |
