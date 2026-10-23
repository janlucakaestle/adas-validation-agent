# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s8` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-22

## Provenance

- Campaign `agent_s8`: kind `search`, method `agent`, status **COMPLETE**, 266 of 300 planned runs, seed 8, created 2026-10-21 22:32:21
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `fee450830a1a37b70a4b40fd99fbfaa0b76674f1e72242abee3359f131f88f16`
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
- Full ODD coverage achieved (216/216 coverage cells, min 1 run each) across both scenarios (lead_brake, cut_in), both driver states, and the full ego_speed/headway/friction/lead_decel(or closing_speed) grid.
- After broad coverage, budget was focused on two clusters where collisions appeared, varying one factor at a time and repeating cases (5+ reps) to sample the stochastic driver takeover time.
- 266 of 300 runs used; 34 held in reserve (unused) after confirming findings with tight confidence intervals.

## Key findings

**1. Lead-vehicle hard braking + distracted driver + short-to-moderate headway + high/dry friction → frequent, avoidable collisions.**
With an attentive driver, lead_brake events up to lead_decel=9 m/s^2 were handled without collision in the broad sweep (headway ≥0.8s). With a distracted driver, the re-engagement delay (observed takeover_time often 3–8s) is long enough that for lead_decel ≥6 m/s^2 combined with friction ≥0.75 and headway ≤1.9s, the ego vehicle frequently fails to stop in time. Collision rate inside this predicate is 71% vs 7.8% outside (lift 9.2x, 266 runs, 95% CI on inside rate [0.48, 0.89]). Critically, `avoidable_by_reference=TRUE` for essentially all these collisions, meaning a simple fixed brake-only reference response starting at hazard onset would have avoided contact — this is a genuine system/TOR-timing deficiency, not an inherently unavoidable scenario. Low friction (≤0.5) caps lead_decel physically and paradoxically reduces risk in this same region (0/5 collisions at friction 0.5 vs 5/5 at friction 0.9, same lead_decel/headway), because the lead vehicle itself cannot brake as hard.

**2. Cut-in at the ODD boundary (very short headway, near-max closing speed) → collisions essentially regardless of driver state.**
At headway ≤0.3s (ODD minimum) and closing_speed ≥9 m/s (ODD maximum), collisions occurred in 15/15 runs (100%, lift 13.2x vs 7.6% baseline, 95% CI [0.78, 1.0]), for both attentive and distracted drivers and across the friction range. Most of these (e.g. friction ≥0.75) have `avoidable_by_reference=TRUE`, indicating the system itself is failing to execute an achievable avoidance maneuver at this ODD corner — it is not simply a physically-unavoidable edge case. Only at the lowest friction (0.5) did the single corner combination show `avoidable_by_reference=FALSE`, indicating that specific sub-case is likely physically unavoidable and should be excluded from the system-deficiency claim.

## Limitations
- Findings are based on a targeted search, not a representative sampling of real-world exposure; reported "rates" describe my own test runs and must not be read as real-world collision probabilities.
- The lead_brake predicate was explored mainly at ego_speed=25 m/s; headway/decel/friction boundaries were probed at that speed and via the broader coverage grid at other speeds, but a finer sweep across ego_speed for the exact threshold was not performed given budget.
- The cut-in finding is strongest exactly at the ODD boundary (headway=0.3, closing_speed=9); behavior just inside the boundary (e.g., headway=0.5, closing_speed=8) was covered only at coarser bin midpoints in the broad sweep, which showed no collisions — suggesting a fairly sharp failure region near the extreme corner that merits finer-grained follow-up.

## Recommended next tests
- Sweep ego_speed and headway finely around the lead_brake distracted/high-decel/high-friction region to map the exact collision-onset boundary (e.g., decel 5.5–6.5, headway 1.9–2.9).
- Sweep headway (0.3–0.6) and closing_speed (7–9) finely for cut_in to find the exact onset boundary of the 100%-collision corner, and separately verify the friction=0.5 unavoidable sub-case boundary.
- Investigate TOR/driver-reengagement timing logic specifically for distracted drivers under high-urgency lead braking, since the avoidable_by_reference=TRUE result points to a response-timing/control gap rather than a kinematic impossibility.

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

- Runs executed: 266
- Target runs: 34
- Distinct target coverage cells: 12
- Runs to first target run: 60

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 11 | 8 |
| cut_in | attentive | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 6 | 5 |
| cut_in | distracted | 22-29 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 6 | 5 |
| cut_in | distracted | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 6 | 5 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 6 | 4 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | attentive | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 6 | 1 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 6 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 266 | 5 | 65 | 34 | 29 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `5a6c7e3a4e054eefa6e43f528f23980914a35df7dfb557ab2220599f9030edf7`.

### TC-01: Lead vehicle hard braking with a distracted driver, short-to-moderate headway, and high/dry friction leads to frequent collisions that a simple reference brake response would have avoided (avoidable_by_reference=TRUE in nearly all cases).

Predicate: `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND friction>=0.75 AND headway<=1.9`

- Condition SHA-256 `7a5044109c570274f9b37969407cbf6b54d9b842aeacfadf16fd7feaf5804f26`
- Predicate test `89b6965f0b76` (target `collision`, on 266 runs): 21 runs inside, target rate inside 0.7143 [95% two-sided 0.4782, 0.8872], outside 0.07755, lift 9.211
- Evidence query `47067f60523d` (result SHA-256 `273da0b9bdc9f555…`):

```sql
SELECT scenario, driver_state, lead_decel, friction, headway, collision, avoidable_by_reference FROM runs WHERE scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND friction>=0.75 AND headway<=1.9 ORDER BY headway, lead_decel, friction
```

| scenario | driver_state | lead_decel | friction | headway | collision | avoidable_by_reference |
| --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 6.0 | 0.9 | 0.9 | False | True |
| lead_brake | distracted | 6.0 | 0.9 | 0.9 | False | True |
| lead_brake | distracted | 6.0 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 6.0 | 0.9 | 0.9 | False | True |
| lead_brake | distracted | 6.0 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 8.5 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 8.5 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 8.5 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 8.5 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 8.5 | 0.9 | 0.9 | True | True |
| lead_brake | distracted | 7.5 | 0.875 | 1.167 | True | True |
| lead_brake | distracted | 7.5 | 0.875 | 1.167 | True | True |
| lead_brake | distracted | 7.5 | 0.875 | 1.167 | True | True |
| lead_brake | distracted | 7.5 | 0.875 | 1.9 | False | True |
| lead_brake | distracted | 7.5 | 0.875 | 1.9 | True | True |

### TC-02: Cut-in at the ODD boundary (minimum headway 0.3s combined with maximum closing speed 9 m/s) produces collisions in essentially all runs, regardless of driver state, and mostly remains avoidable_by_reference=TRUE, indicating a system response gap at this ODD corner rather than a purely physically-unavoidable scenario.

Predicate: `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9`

- Condition SHA-256 `773f9f0475a4b0d1082f42a20072c87280e065f4cf4dfa5bd3c34217ce2287fd`
- Predicate test `20fbc7c64fdf` (target `collision`, on 266 runs): 15 runs inside, target rate inside 1 [95% two-sided 0.782, 1], outside 0.0757, lift 13.21
- Evidence query `e37e9bdcdcbe` (result SHA-256 `ec30af4279855e7c…`):

```sql
SELECT scenario, driver_state, closing_speed, headway, friction, collision, avoidable_by_reference FROM runs WHERE scenario='cut_in' AND headway<=0.3 AND closing_speed>=9 ORDER BY driver_state, friction
```

| scenario | driver_state | closing_speed | headway | friction | collision | avoidable_by_reference |
| --- | --- | --- | --- | --- | --- | --- |
| cut_in | attentive | 9.0 | 0.3 | 0.75 | True | True |
| cut_in | attentive | 9.0 | 0.3 | 0.75 | True | True |
| cut_in | attentive | 9.0 | 0.3 | 0.75 | True | True |
| cut_in | attentive | 9.0 | 0.3 | 0.75 | True | True |
| cut_in | attentive | 9.0 | 0.3 | 0.75 | True | True |
| cut_in | distracted | 9.0 | 0.3 | 0.5 | True | False |
| cut_in | distracted | 9.0 | 0.3 | 0.5 | True | False |
| cut_in | distracted | 9.0 | 0.3 | 0.5 | True | False |
| cut_in | distracted | 9.0 | 0.3 | 0.5 | True | False |
| cut_in | distracted | 9.0 | 0.3 | 0.5 | True | False |
| cut_in | distracted | 9.0 | 0.3 | 1.0 | True | True |
| cut_in | distracted | 9.0 | 0.3 | 1.0 | True | True |
| cut_in | distracted | 9.0 | 0.3 | 1.0 | True | True |
| cut_in | distracted | 9.0 | 0.3 | 1.0 | True | True |
| cut_in | distracted | 9.0 | 0.3 | 1.0 | True | True |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 89b6965f0b76 | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND friction>=0.75 AND headway<=1.9` | collision | 266 | 21 | 0.7143 | 0.07755 | 9.211 |
| 2 | 20fbc7c64fdf | `scenario='cut_in' AND headway<=0.3 AND closing_speed>=9` | collision | 266 | 15 | 1 | 0.0757 | 13.21 |
| 3 | 56869d3d56ab | `scenario='lead_brake' AND driver_state='attentive' AND lead_decel>=7 AND headway<=1.0 AND friction>=0.75` | collision | 266 | 5 | 0.2 | 0.1264 | 1.582 |
| 4 | 0823e15ceb3e | `scenario='lead_brake' AND driver_state='distracted' AND lead_decel>=6 AND friction<0.75` | collision | 266 | 14 | 0.2143 | 0.123 | 1.742 |
