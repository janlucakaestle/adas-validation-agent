# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s2` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s2`: kind `search`, method `agent`, status **COMPLETE**, 259 of 300 planned runs, seed 2, created 2026-10-21 21:58:01
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `f4a6504bb28a40c536c4dc8171e4327cb49a9cbab863df9fcb7fff49fd9f0804`
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

## Campaign summary (agent_s2, 259/300 runs used)

**Approach:** Ran a structured coverage sweep across the full ODD grid (bin midpoints for ego_speed, headway, friction, lead_decel/closing_speed, crossed with scenario and driver_state — 216 runs, 1 per coverage cell), then used `runs` queries to find where collisions clustered, formed hypotheses, and confirmed them with targeted replicate runs (43 further runs) and `test_predicate`.

**Key finding 1 — Distracted driver + strong lead braking at short/medium headway (lead_brake).**
Across the coverage sweep, zero collisions occurred for attentive drivers anywhere in the lead_brake ODD (including at lead_decel=9, headway=0.8 — the most severe coverage cell tested for attentive, 0/12 collisions). For **distracted** drivers, collisions appeared as soon as lead_decel reached ~6 m/s² together with headway ≤ ~2 s and ego_speed ≥ ~18.5 m/s, with collision rate ≈ 67% inside vs ≈4% outside this predicate (lift ≈15×, test_id c7cc7f19dbbb). The mechanism visible in the data: the distracted driver's reaction/takeover delay (takeover_time) is stochastic and often exceeds ~3.5–4 s; when it does, under hard lead braking at short headway the gap closes to contact before the driver (or the ACC) can react. At the lowest ego_speed bin (15 m/s) even decel=9, headway=0.8, distracted showed 0/6 collisions — low speed gives enough margin despite the long reaction delay, so the condition is speed-dependent as stated.

**Key finding 2 — Extreme cut-in corner (very short headway + very high closing speed), independent of driver state.**
In the broad coverage sweep (bin midpoints, closing_speed up to 7.5 m/s, headway down to 0.58 s) zero cut_in collisions occurred for either driver state (0/108 for cut_in specifically). Only when probing the extreme ODD corner — headway ≤ 0.35 s and closing_speed ≥ 9 m/s (the ODD maxima) at low friction (0.5) and high ego_speed (36 m/s) — did collisions appear, and at a high rate (≈77% inside vs ≈8% outside, lift ≈9.5×, test_id 08f63d20be6c). Notably this triggers for **both** attentive (5/8, 62.5%) and distracted (5/5, 100%) drivers, indicating the kinematic margin at this ODD corner is so small that even an attentive driver's ~1 s reaction time is often too slow. Reducing closing_speed to 6 m/s or headway to 0.87 s (one bin up) at the same extreme removed all collisions in the samples taken — consistent with a narrow, corner-of-the-ODD effect rather than a broad cut_in weakness.

**Limitations:**
- Sample sizes for the confirmatory conditions are modest (13–30 runs inside each predicate); confidence intervals are wide (e.g., 47–95% for the cut_in corner).
- Thresholds (lead_decel≈6, headway≈2.0, ego_speed≈18.5 for lead_brake; headway≈0.35, closing_speed≈9 for cut_in) are empirical boundaries from the specific values tested, not exact minima — finer sweeps near these boundaries would sharpen them.
- All rates are internal to this search-driven campaign (deliberately oversampling rare/severe regions) and must not be read as real-world incidence rates.
- `avoidable_by_reference` was not analyzed in depth; a follow-up should check whether these collisions are flagged as avoidable or not by the reference policy to separate function deficiencies from physically-constrained cases.

**Recommended next tests:** finer sweep of lead_decel in [5,7] and headway in [1.5,2.5] at ego_speed∈[18,22] to localize the lead_brake threshold; finer sweep of closing_speed in [7,9] and headway in [0.3,0.9] to localize the cut_in corner boundary; repeat both at additional friction levels (currently only 0.5/0.625/0.75/0.875 sampled, not the 1.0 dry extreme for the corner case).

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

- Runs executed: 259
- Target runs: 30
- Distinct target coverage cells: 9
- Runs to first target run: 60

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 11 | 9 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 9 | 5 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 9 | 5 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 4 | 4 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 6 | 3 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 4 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 259 | 0 | 54 | 30 | 30 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `759ef3ec21075c6d416b179adb754d6cf8514faf220e88e60adaadcf5863fa9d`.

### TC-01: Lead_brake scenario with a distracted (foreseeable-misuse) driver, strong lead-vehicle braking (>=6 m/s^2), short-to-medium headway (<=2.0 s), and ego speed >=18.5 m/s: the driver's stochastic takeover delay frequently exceeds the time available to stop, producing collisions at ~67% rate versus ~4% outside this condition (lift ~15x). No collisions were observed for attentive drivers under the same severe braking/headway combinations.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.0 AND ego_speed >= 18.5`

- Condition SHA-256 `ec3d66ee5527df822fc8f3668f101abae302e6f48548b440d0a54343b1220b76`
- Predicate test `c7cc7f19dbbb` (target `collision`, on 259 runs): 30 runs inside, target rate inside 0.6667 [95% two-sided 0.4719, 0.8271], outside 0.04367, lift 15.27
- Evidence query `8e1a1626b54a` (result SHA-256 `daf030519b071515…`):

```sql
SELECT driver_state, ego_speed, headway, lead_decel, friction, count(*) AS n, sum(CASE WHEN collision THEN 1 ELSE 0 END) AS collisions, round(avg(CASE WHEN collision THEN 1 ELSE 0 END),3) AS rate FROM runs WHERE scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.0 AND ego_speed >= 18.5 GROUP BY 1,2,3,4,5 ORDER BY ego_speed, lead_decel, headway, friction
```

| driver_state | ego_speed | headway | lead_decel | friction | n | collisions | rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| distracted | 18.5 | 1.167 | 7.5 | 0.625 | 1 | 0 | 0.0 |
| distracted | 18.5 | 1.167 | 7.5 | 0.875 | 1 | 1 | 1.0 |
| distracted | 18.5 | 1.9 | 7.5 | 0.625 | 1 | 0 | 0.0 |
| distracted | 18.5 | 1.9 | 7.5 | 0.875 | 1 | 0 | 0.0 |
| distracted | 25.5 | 1.167 | 6.0 | 0.75 | 5 | 3 | 0.6 |
| distracted | 25.5 | 1.167 | 7.5 | 0.625 | 1 | 1 | 1.0 |
| distracted | 25.5 | 1.167 | 7.5 | 0.75 | 5 | 5 | 1.0 |
| distracted | 25.5 | 1.167 | 7.5 | 0.875 | 1 | 1 | 1.0 |
| distracted | 25.5 | 1.9 | 7.5 | 0.625 | 1 | 0 | 0.0 |
| distracted | 25.5 | 1.9 | 7.5 | 0.875 | 1 | 1 | 1.0 |
| distracted | 29.0 | 1.167 | 6.0 | 0.75 | 3 | 3 | 1.0 |
| distracted | 32.5 | 1.167 | 7.5 | 0.625 | 1 | 1 | 1.0 |
| distracted | 32.5 | 1.167 | 7.5 | 0.875 | 1 | 1 | 1.0 |
| distracted | 32.5 | 1.9 | 7.5 | 0.625 | 1 | 0 | 0.0 |
| distracted | 32.5 | 1.9 | 7.5 | 0.875 | 1 | 1 | 1.0 |

### TC-02: Cut_in scenario at the extreme corner of the ODD: very short initial headway (<=0.35 s) combined with very high closing speed (>=9 m/s, the ODD maximum), at low friction and high ego speed. Collisions occur at a high rate (~77%) regardless of driver state (attentive 62.5%, distracted 100%), indicating the physical/kinematic margin at this corner is too small for either an attentive or distracted driver's reaction time, unlike the rest of the sampled cut_in ODD where zero collisions were observed.

Predicate: `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 9.0`

- Condition SHA-256 `2694019c783910c137845aa4d2a16bc9b05d811b0fcead20f0efbd655c0d16a0`
- Predicate test `08f63d20be6c` (target `collision`, on 259 runs): 13 runs inside, target rate inside 0.7692 [95% two-sided 0.4619, 0.9496], outside 0.0813, lift 9.462
- Evidence query `110908b6886b` (result SHA-256 `a67d361d9db53f23…`):

```sql
SELECT driver_state, ego_speed, headway, closing_speed, friction, count(*) AS n, sum(CASE WHEN collision THEN 1 ELSE 0 END) AS collisions, round(avg(CASE WHEN collision THEN 1 ELSE 0 END),3) AS rate FROM runs WHERE scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 9.0 GROUP BY 1,2,3,4,5 ORDER BY driver_state
```

| driver_state | ego_speed | headway | closing_speed | friction | n | collisions | rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| attentive | 36.0 | 0.3 | 9.0 | 0.5 | 8 | 5 | 0.625 |
| distracted | 36.0 | 0.3 | 9.0 | 0.5 | 5 | 5 | 1.0 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | ecf26c52ba56 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 7.0` | collision | 216 | 18 | 0.3889 | 0 | - |
| 1 | 8f4d134151e4 | `scenario = 'cut_in'` | collision | 216 | 108 | 0 | 0.06481 | 0 |
| 2 | af02ca870739 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 7.0 AND headway <= 2.0` | collision | 216 | 12 | 0.5833 | 0 | - |
| 3 | 37624cfadbab | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 7.0 AND headway > 2.0` | collision | 216 | 6 | 0 | 0.03333 | 0 |
| 4 | dd68fad98aaa | `scenario = 'lead_brake' AND driver_state = 'attentive' AND lead_decel >= 7.0 AND headway <= 2.0` | collision | 216 | 12 | 0 | 0.03431 | 0 |
| 5 | 7cd30fb36738 | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.0 AND ego_speed >= 18.5` | collision | 254 | 30 | 0.6667 | 0.03125 | 21.33 |
| 6 | f8ad5427ff40 | `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 9.0` | collision | 254 | 8 | 0.875 | 0.0813 | 10.76 |
| 9 | c7cc7f19dbbb | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.0 AND headway <= 2.0 AND ego_speed >= 18.5` | collision | 259 | 30 | 0.6667 | 0.04367 | 15.27 |
| 10 | 08f63d20be6c | `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 9.0` | collision | 259 | 13 | 0.7692 | 0.0813 | 9.462 |
