# Held-out evaluation of frozen triggering conditions

Hold-out protocol `11f362476056b96f…` (seed 4242, 100,000 planned runs, final evidence). Frozen set `ae153ba5af675f78…` (22 predicates, frozen 2026-10-22T13:58:12.088873, derived from agent_s0, agent_s1, agent_s2, agent_s3, agent_s4, agent_s5, agent_s6, agent_s7, agent_s8, agent_s9, estimate). Hold-out campaign `holdout`: 100,000 fresh exposure-weighted runs, created after the freeze, sharing no campaign or seed with the discovery data. Rates are conditional on the exposure model; intervals are two-sided 95% Clopper-Pearson.

| source | TC | predicate | support | exposure measure | runs inside | target rate inside [95% CI] | lift | region events inside |
|---|---|---|---|---|---|---|---|---|
| agent_s0 | TC-01 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel >= 6` | exposure-supported | 0.640% | 601 | 36.6% [32.7%, 40.6%] | 169.2 | 0 / 55 |
| agent_s0 | TC-02 | `scenario='cut_in' AND headway <= 0.3 AND closing_speed >= 9` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s1 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.5` | exposure-supported | 0.522% | 492 | 38.4% [34.1%, 42.9%] | 155.4 | 0 / 55 |
| agent_s1 | TC-02 | `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 8.5` | neighbourhood (low exposure measure) | 0.017% | 18 | 77.8% [52.4%, 93.6%] | 184.7 | 10 / 55 |
| agent_s2 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.0 AND ego_speed >= 18.5` | exposure-supported | 0.251% | 244 | 62.7% [56.3%, 68.8%] | 221.8 | 0 / 55 |
| agent_s2 | TC-02 | `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 9.0` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s3 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.63` | exposure-supported | 0.515% | 484 | 43.2% [38.7%, 47.7%] | 190.1 | 0 / 55 |
| agent_s3 | TC-02 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 9` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s4 | TC-01 | `scenario='lead_brake' AND driver_state='distracted' AND headway<=1.9 AND lead_decel>=7 AND friction>=0.6` | exposure-supported | 0.147% | 139 | 69.8% [61.4%, 77.3%] | 206.2 | 0 / 55 |
| agent_s4 | TC-02 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s5 | TC-01 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 9.0 AND headway <= 2.27 AND ego_speed >= 22 AND friction >= 0.75` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s5 | TC-02 | `scenario = 'cut_in' AND headway <= 0.3 AND closing_speed >= 6.0` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s6 | TC-01 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6.5 AND friction>0.5 AND headway<2.3` | exposure-supported | 0.322% | 304 | 53.6% [47.8%, 59.3%] | 196.5 | 0 / 55 |
| agent_s6 | TC-02 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s7 | TC-01 | `driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.2` | neighbourhood (low exposure measure) | 0.069% | 66 | 84.8% [73.9%, 92.5%] | 223.7 | 0 / 55 |
| agent_s7 | TC-02 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND friction < 1.0` | neighbourhood (low exposure measure) | 0.074% | 77 | 49.4% [37.8%, 61.0%] | 124.2 | 27 / 55 |
| agent_s8 | TC-01 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND friction>=0.75 AND headway<=1.9` | exposure-supported | 0.195% | 181 | 64.6% [57.2%, 71.6%] | 202.9 | 0 / 55 |
| agent_s8 | TC-02 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| agent_s9 | TC-01 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND ego_speed>=25.5` | exposure-supported | 1.263% | 1,224 | 22.2% [19.9%, 24.7%] | 134.7 | 0 / 55 |
| agent_s9 | TC-02 | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | unsupported (zero exposure measure) | 0.000% | 0 | - | - | 0 / 55 |
| reference | box-cut_in | `scenario = 'cut_in' AND headway <= 0.60 AND closing_speed >= 5.9` | exposure-supported | 0.702% | 718 | 10.2% [8.1%, 12.6%] | 27.9 | 50 / 55 |
| reference | box-lead_brake | `scenario = 'lead_brake' AND headway <= 1.65 AND lead_decel >= 7.4` | exposure-supported | 0.422% | 383 | 15.7% [12.2%, 19.7%] | 41.6 | 2 / 55 |

Only `exposure-supported` conditions generalise under the exposure model. Exact-point descriptions and unsupported conditions describe sampled points, not triggering conditions, and are not evidence of a generalising failure mode.
