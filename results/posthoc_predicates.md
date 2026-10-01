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
