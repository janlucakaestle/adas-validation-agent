# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s9` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-22

## Provenance

- Campaign `agent_s9`: kind `search`, method `agent`, status **COMPLETE**, 256 of 300 planned runs, seed 9, created 2026-10-22 00:28:10
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `f0b6be36aedbbe23689b26a415b20eddca4c0ef4145a389057d9790b9c35465b`
- Policy SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`; source code SHA-256: `3cc05645a19f25d7a70ab70c09cfd95b61bc4682a260b32515ad05a5b87daeee`; git commit `43d549f3981403b13317ba99cffb86c97d5e5abe` (traceability only)
- Python 3.11.9 on Windows AMD64; PyYAML 6.0.3, anthropic 1.8.0, duckdb 1.5.5, matplotlib 3.11.2, numpy 2.4.6, pandas 3.0.5, pyarrow 25.0.1, scikit-learn 1.9.1, scipy 1.17.1
- Lock file: matches
- Parsed config `acceptance` SHA-256: `0a49d9d0083831e7beab7389706a8d66ac11a05d1784b88f48d4ec5862fca628`
- Parsed config `driver` SHA-256: `6165e60b72b4fb58f35b0e3fdbb746aa9dd8689df8cede4878c5ec78e6c38355`
- Parsed config `exposure` SHA-256: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`
- Parsed config `odd` SHA-256: `64b0f925ef6f25d076435ab2497a1bcaf272a9e7f08e10a3b8e2e1a76cf5eef6`
- Parsed config `reference` SHA-256: `9a6c5660e2b64562e00d39cc2d10432e57184d5e65aa49367758f78875cc93f2`
- Parsed config `sim` SHA-256: `71ed89eee9d3a8a80d3ac3f3d9afd072164c93be4239999e8027c331100a9bb0`

**Scope.** Every number below is conditional on this release's simulator, ODD, exposure model, driver model, controller and configuration (release ID above). Exposure weights, acceptance thresholds and several driver parameters are placeholders (`TODO(data)` in `config/`), so the numbers show the method, not real-world risk.

## Summary

## Campaign overview
- 256 of 300 budgeted runs used. 216 runs gave full coverage (1+ run) of all 216 ODD bins (scenario × driver_state × ego_speed × headway × friction × lead_decel/closing_speed bins). The remaining 40 runs targeted hypotheses raised by the coverage sweep (repeats to sample stochastic takeover_time, and boundary probes).
- Two distinct triggering conditions for `collision` were found and confirmed with test_predicate + query evidence. A third observation (near-miss clustering) is noted as a follow-up.

## Finding 1 — lead_brake: distracted driver + strong lead braking + higher ego speed
In the `lead_brake` scenario, every collision observed (6/6) occurred with a **distracted** driver, `lead_decel >= 4.75 m/s²`, and `ego_speed >= 25.5 m/s`. No collisions occurred with an attentive driver anywhere in the sweep, nor with distracted drivers at low lead_decel (2.25) or low ego_speed (18.5), even though headway spanned the full ODD range (1.17–3.0 s) and some long-headway/long-decel cases still collided (e.g. headway 2.63 s, lead_decel 7.5). The mechanism is the distracted-driver reaction-time distribution: collisions cluster at takeover_time ≈ 3.5–8.9 s, i.e. only the slow tail of the distracted-driver reaction-time distribution combined with a demanding brake event overwhelms the margin that the ACC + TOR strategy leaves. Headway and friction did not reliably protect against this in the sampled region once decel/speed were high enough.
- test_predicate: `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND ego_speed>=25.5` → inside collision rate 17.6% (34 runs) vs 5.0% outside, lift ≈3.6, 95% CI on inside rate [6.8%, 34.5%].
- This is a foreseeable-misuse (distracted driver) condition, not an intended-use failure — attentive runs at identical kinematic severity (including the most extreme tested: ego_speed 36, friction 0.5, headway 0.8, lead_decel 9) never collided (0/5), while distracted runs at those same extreme parameters collided in 1/5 (and in repeated sampling of similar bins ~15-20%).

## Finding 2 — cut_in: very short headway + high closing speed is unrecoverable regardless of driver state (capability gap)
In the `cut_in` scenario, when the cut-in happens at `headway <= 0.3 s` (ODD's lower bound) together with `closing_speed >= 9 m/s` (ODD's upper bound), the run collides essentially always (11/12 = 92%), **independent of driver_state** (both attentive and distracted collide), and largely independent of friction and ego speed. This contrasts sharply with every other cut_in bin tested (headway ≥ 0.35 s or closing_speed ≤ 6 m/s), which produced zero collisions and zero near-misses across the full coverage sweep (108 cut_in coverage runs, 0 collisions). Critically, most of these collisions have `avoidable_by_reference = TRUE`, meaning a simple fixed brake-only reference response starting at hazard onset would have avoided contact — so this is evidence of an ACC/TOR response-capability gap at the edge of the ODD, not an inherently unavoidable physical conflict.
- test_predicate: `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` → inside collision rate 91.7% (12 runs) vs 2.5% outside, lift ≈37.3, 95% CI on inside rate [61.5%, 99.8%].
- Boundary probing shows a sharp cliff: headway 0.35–0.45 s at the same closing_speed (9 m/s) produced 0 collisions in 4/4 runs, so the failure is tightly localized near the ODD's minimum-headway edge.

## Limitations
- Sample sizes for the tail/stochastic effects (esp. Finding 1) are modest (12–34 runs per predicate); rates are campaign-search artifacts, not real-world incidence estimates.
- Coverage used bin midpoints; some bin-interior behavior (especially near other boundaries) was not swept exhaustively given the 300-run budget.
- Only the `collision` target was used for final predicates; `near_miss` (min_ttc<1.0) shows a similar but broader pattern (e.g., several lead_brake/distracted/high-decel runs with min_ttc 1.0–1.5 s) that was not separately formalized here.

## Recommended next tests
1. Map the exact headway/closing_speed boundary in cut_in more finely (e.g. headway 0.30–0.35 s, closing_speed 7–9 m/s grid) to quantify the capability-gap envelope.
2. For Finding 1, sample many repeats (30+) at the identified (lead_decel≥4.75, ego_speed≥25.5, distracted) cell to get a tighter collision-rate estimate and check sensitivity to headway/friction within that cell.
3. Investigate why friction=1.0 attentive narrowly avoided the cut_in extreme (run 250) while friction=0.5 attentive did not — possible friction-dependent margin inside the otherwise-dangerous cut_in corner.

## Release verdict (from estimation campaign `estimate`): NO-GO

Not computed from this search campaign; same release ID `fe59625d94287538…`. criteria AC-01, AC-03, AC-04 failed. no requirement defined for AC-09, AC-10.

- **Engineering verdict** (evidence against the configured targets): **NO-GO**
- **Requirement maturity:** not approved: AC-01, AC-02, AC-03, AC-04, AC-07, AC-08, AC-09, AC-10. A provisional, illustrative or undefined requirement can never authorise release (a violation still counts as NO-GO).
- **Formal release decision:** **NO-GO**

| id | name | value | one-sided 95% bound | n | n needed | min_n | target | vs target | requirement | supports formal GO |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Collisions with attentive supervision, scenarios avoidable by the ideal reference | 0.0008629 | 0.001054 (upper) | 79966 | 29956 | 100 | <= 0.0001 (zero goal) | FAIL | illustrative | no |
| AC-02 | 5th-percentile effective minimum TTC | 1.865 | 1.859 (lower) | 100000 | 59 | 100 | >= 1.5 | PASS | illustrative | no |
| AC-03 | Collisions under foreseeable misuse, scenarios avoidable by the ideal reference | 0.01877 | 0.02043 (upper) | 20031 | 59 | 100 | <= 0.05 | FAIL | illustrative | no |
| AC-04 | 95th-percentile jerk while automated longitudinal control is active | 4.949 | 4.964 (upper) | 100000 | 59 | 100 | <= 5 | FAIL | illustrative | no |
| AC-07 | Missed or late hand-back when one is required | 0 | 0.001131 (upper) | 2647 | 299 | 100 | <= 0.01; max_tor_latency_s = 0.5 | PASS | illustrative | no |
| AC-08 | Hand-backs in scenarios that do not require one | 0.2017 | 0.2038 (upper) | 97353 | 11 | 100 | <= 0.25 | PASS | illustrative | no |
| AC-09 | Overall collisions with attentive supervision (reference-independent) | 0.0009003 | 0.001095 (upper) | 79969 | - | 100 | none defined | NO REQUIREMENT | undefined | no |
| AC-10 | Overall collisions under foreseeable misuse (reference-independent) | 0.01877 | 0.02043 (upper) | 20031 | - | 100 | none defined | NO REQUIREMENT | undefined | no |

Statistical result: exact one-sided Clopper-Pearson bounds for rates and exact distribution-free order-statistic bounds for quantiles, at 95% one-sided confidence. Engineering comparison ('vs target'): PASS needs the bound to meet the target (in every stratum where strata are listed); FAIL means the point estimate violates it (or a zero goal is falsified); NO REQUIREMENT means no target exists. 'requirement' is the effective maturity (the weakest of the criterion's own status and the definitions its population uses); only 'approved' can support a formal GO. 'n needed' is the smallest sample at which a PASS is possible at all.

- **AC-01:** zero goal falsified: 69 event(s) observed. An observed event cannot be erased by additional event-free runs. Permanent under the zero goal: observed events cannot be erased by more successful runs.

  AC-02 by stratum:

| stratum | n | value | lower | upper | status |
| --- | --- | --- | --- | --- | --- |
| scenario=cut_in | 39919 | 2.431 | 2.401 | 2.47 | PASS |
| scenario=lead_brake | 60081 | 1.795 | 1.786 | 1.802 | PASS |

- **AC-03:** decided by stratum [{'handback_required': True}] Existing evidence is already sufficient for this criterion under the current simulator, models and acceptance rules: additional IID sampling of the unchanged release is unlikely to reverse it (the opposite one-sided 95% bound already violates the threshold).

  AC-03 by stratum:

| stratum | n | value | lower | upper | status |
| --- | --- | --- | --- | --- | --- |
| handback_required=False | 19494 | 0.006156 | 0.005264 | 0.00716 | PASS |
| handback_required=True | 537 | 0.4767 | 0.4405 | 0.5131 | FAIL |

- **AC-04:** decided by stratum [{'scenario': 'cut_in'}] Existing evidence is already sufficient for this criterion under the current simulator, models and acceptance rules: additional IID sampling of the unchanged release is unlikely to reverse it (the opposite one-sided 95% bound already violates the threshold).

  AC-04 by stratum:

| stratum | n | value | lower | upper | status |
| --- | --- | --- | --- | --- | --- |
| scenario=cut_in | 39919 | 5.172 | 5.167 | 5.177 | FAIL |
| scenario=lead_brake | 60081 | 3.859 | 3.85 | 3.87 | PASS |

- **AC-09:** no target is defined: statistics only
- **AC-10:** no target is defined: statistics only

**Descriptive measures (INFO, never gating).** Rows marked *conditional* select runs by the system's own outputs and must not be read as safety evidence.

| id | name | value | one-sided 95% bounds [lower, upper] | n | conditional on outputs |
| --- | --- | --- | --- | --- | --- |
| AC-06 | Share of runs not avoided by the ideal reference (information only) | 3e-05 | [8.177e-06, 7.753e-05] | 100000 | no |
| AC-02-S | 5th-percentile minimum TTC of collision-free runs (descriptive, survivor-only) | 1.888 | [1.882, 1.895] | 99552 | yes |
| AC-03-C | Collisions after a hand-back to a distracted driver (descriptive, conditional) | 0.08397 | [0.07724, 0.0911] | 4478 | yes |

## Discovery

Search campaigns choose where to look, so their rates say nothing about real-world risk and are not reported. What matters is what the search found and how fast. Discovery target: `collision` = `collision` (`config/discovery.yaml`; a search heuristic, not an acceptance criterion).

- Runs executed: 256
- Target runs: 17
- Distinct target coverage cells: 10
- Runs to first target run: 60

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 8 | 5 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 8 | 3 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 6 | 2 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 256 | 2 | 42 | 17 | 15 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `24bf3fea0c1510eae519c5eb94e1e7e9194940074a5486cc7246891602d9b6a9`.

### TC-01: lead_brake: distracted driver with strong lead-vehicle braking (>=4.75 m/s^2) at higher ego speed (>=25.5 m/s) produces collisions driven by the slow tail of the distracted-driver takeover-time distribution; attentive driver never collides under matched kinematics.

Predicate: `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND ego_speed>=25.5`

- Condition SHA-256 `7fe455750e508c041134df5476457d15707ebccd42468fa69383f4408ca2dcd6`
- Predicate test `02073ca18f6a` (target `collision`, on 256 runs): 34 runs inside, target rate inside 0.1765 [95% two-sided 0.06764, 0.3453], outside 0.04955, lift 3.561
- Evidence query `0b64ebbf0824` (result SHA-256 `e51e34eaf54526fc…`):

```sql
SELECT run_idx, ego_speed, headway, lead_decel, friction, driver_state, collision, takeover_time, min_ttc FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND ego_speed>=25.5 ORDER BY collision DESC, run_idx
```

| run_idx | ego_speed | headway | lead_decel | friction | driver_state | collision | takeover_time | min_ttc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 59 | 25.5 | 1.167 | 7.5 | 0.875 | distracted | True | 4.485 | 0.038 |
| 77 | 32.5 | 1.167 | 7.5 | 0.625 | distracted | True | 3.47 | 0.026 |
| 89 | 32.5 | 2.633 | 7.5 | 0.625 | distracted | True | 5.462 | 0.013 |
| 95 | 32.5 | 1.167 | 7.5 | 0.875 | distracted | True | 4.677 | 0.001 |
| 99 | 32.5 | 1.9 | 4.75 | 0.875 | distracted | True | 8.9 | 0.03 |
| 221 | 36.0 | 0.8 | 9.0 | 0.5 | distracted | True | 4.859 | 0.046 |
| 39 | 25.5 | 1.167 | 4.75 | 0.625 | distracted | False | 4.32 | 1.561 |
| 41 | 25.5 | 1.167 | 7.5 | 0.625 | distracted | False | 3.627 | 0.513 |
| 45 | 25.5 | 1.9 | 4.75 | 0.625 | distracted | False | 4.533 | 1.518 |
| 47 | 25.5 | 1.9 | 7.5 | 0.625 | distracted | False | 4.326 | 1.095 |
| 51 | 25.5 | 2.633 | 4.75 | 0.625 | distracted | False | 3.683 | 1.778 |
| 53 | 25.5 | 2.633 | 7.5 | 0.625 | distracted | False | 4.073 | 1.607 |
| 57 | 25.5 | 1.167 | 4.75 | 0.875 | distracted | False | 5.319 | 1.241 |
| 63 | 25.5 | 1.9 | 4.75 | 0.875 | distracted | False | 5.177 | 1.313 |
| 65 | 25.5 | 1.9 | 7.5 | 0.875 | distracted | False | 3.558 | 1.206 |

### TC-02: cut_in: very short initial headway (<=0.3 s, the ODD lower bound) combined with high closing speed (>=9 m/s, the ODD upper bound) causes near-certain collision regardless of driver state, friction, or ego speed; most such collisions are flagged avoidable_by_reference=TRUE, indicating an ACC/TOR response-capability gap at this ODD edge rather than an inherently unavoidable conflict.

Predicate: `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9`

- Condition SHA-256 `42b436cba353a6c4b5734246e39255e14b2bf6372ec21a309df177149ae2ae48`
- Predicate test `34538bb9edea` (target `collision`, on 256 runs): 12 runs inside, target rate inside 0.9167 [95% two-sided 0.6152, 0.9979], outside 0.02459, lift 37.28
- Evidence query `c63b3103e54e` (result SHA-256 `4c328b6ac67c7764…`):

```sql
SELECT run_idx, ego_speed, headway, closing_speed, friction, driver_state, collision, min_ttc, avoidable_by_reference FROM runs WHERE scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 ORDER BY collision DESC, run_idx
```

| run_idx | ego_speed | headway | closing_speed | friction | driver_state | collision | min_ttc | avoidable_by_reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 231 | 36.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.007 | True |
| 232 | 36.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.007 | True |
| 233 | 36.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.007 | True |
| 234 | 36.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.007 | True |
| 235 | 36.0 | 0.3 | 9.0 | 0.5 | distracted | True | 0.007 | True |
| 236 | 36.0 | 0.3 | 9.0 | 0.5 | attentive | True | 0.026 | True |
| 237 | 36.0 | 0.3 | 9.0 | 0.5 | attentive | True | 0.042 | True |
| 238 | 36.0 | 0.3 | 9.0 | 0.5 | attentive | True | 0.039 | True |
| 251 | 36.0 | 0.3 | 9.0 | 1.0 | distracted | True | 0.007 | True |
| 252 | 18.5 | 0.3 | 9.0 | 0.5 | attentive | True | 0.013 | False |
| 253 | 18.5 | 0.3 | 9.0 | 0.5 | distracted | True | 0.013 | False |
| 250 | 36.0 | 0.3 | 9.0 | 1.0 | attentive | False | 0.293 | True |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | f8fa2c584add | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75` | collision | 216 | 36 | 0.1389 | 0 | - |
| 3 | ffc7f416404e | `scenario='lead_brake' AND driver_state='distracted'` | collision | 216 | 54 | 0.09259 | 0 | - |
| 6 | ecc73da3f075 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND ego_speed>=25.5` | collision | 216 | 24 | 0.2083 | 0 | - |
| 8 | 7d0f7c16192e | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 244 | 8 | 1 | 0.02542 | 39.33 |
| 10 | 34538bb9edea | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 256 | 12 | 0.9167 | 0.02459 | 37.28 |
| 11 | 02073ca18f6a | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=4.75 AND ego_speed>=25.5` | collision | 256 | 34 | 0.1765 | 0.04955 | 3.561 |
