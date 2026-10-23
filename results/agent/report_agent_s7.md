# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s7` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s7`: kind `search`, method `agent`, status **COMPLETE**, 176 of 300 planned runs, seed 7, created 2026-10-21 22:25:38
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `c515552f03b7c928d666893153b97ac7735e0724a956c26a85a919d9d8b99c99`
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

## Campaign summary (agent_s7, 176 of 300 runs used)

I ran a broad coverage sweep across the lead_brake and cut_in grids (bin-center values for ego_speed, friction, headway, lead_decel/closing_speed, crossed with driver_state), found a strong early signal, then ran targeted/repeated probes to localize two distinct triggering conditions and to check the effect of driver_state, friction and headway on each.

### Finding 1 — Distracted driver + strong lead braking at short/moderate headway (lead_brake)
With an **attentive** driver, the function handled lead_decel up to the ODD max (9 m/s²) at all tested ego speeds (18.5–32.5 m/s) and headways down to 1.17 s with zero collisions and zero near-misses (40 runs). With a **distracted** driver (foreseeable misuse: driver must re-engage after a reading task), the same lead_decel/headway combinations produced frequent collisions: takeover times of 3–10 s (vs ~0.6–2.2 s attentive) were too slow for the vehicle to stop in time. Collisions only appear when lead_decel ≥ 6 m/s² AND initial headway is short-to-moderate (≤ ~1.2 s); at headway ≥ 2.6 s the same distracted+high-decel case produced no collisions in 3/3 repeats, and at headway 1.9 s only 2/5 collided, showing headway as a mitigating factor. Friction alone (0.5–1.0) did not matter: distracted + friction ≤0.65 + lead_decel <6 produced zero collisions, so the dominant factors are driver_state (distracted) and lead_decel, modulated by headway.

Predicate: `driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.2`
- test_predicate (final data, 176 runs): 60.0% collision rate inside vs 7.1% outside, lift ≈ 8.5 (test_id 17c079442b98, 35 runs inside / 141 outside).

### Finding 2 — Very short headway + high closing speed cut-in (scenario-level edge case, largely driver-independent)
At the extreme corner of the cut_in ODD (headway near the 0.3 s minimum, closing_speed near the 9 m/s maximum, friction <1.0), collisions occurred in both attentive and distracted runs (6/6 in the final isolated set; 7 of 8 in the raw probe before narrowing to friction<1.0 — the one survivor was attentive at friction=1.0). Moving headway to 0.5 s or closing_speed down to 4.75 m/s eliminated collisions entirely at the same friction/speed. `avoidable_by_reference` was `true` for 4 of 6 of these collisions, indicating a plain reference brake response would often have avoided contact — i.e. this is at least partly a system performance gap under a very short reaction window, not purely a physically unavoidable scenario.

Predicate: `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND friction < 1.0`
- test_predicate (final data, 176 runs): 100% collision rate inside (6/6) vs 14.7% outside, lift ≈ 6.8 (test_id 10d29cef45ee).

## Limitations
- Sample sizes for the cut_in extreme-corner condition are small (6–8 runs); the qualitative pattern (headway/closing-speed edge, largely state-independent) is clear but precise collision-rate estimates have wide CIs.
- These rates reflect my targeted search of the ODD (deliberately oversampling hazardous corners), not real-world incidence.
- Coverage of the full 216-cell grid was partial; most budget was redirected toward confirming the two hazard clusters found early.

## Recommended next tests
- Finer sweep of headway between 1.2–2.6 s at lead_decel 6–9 with distracted driver to map the collision-rate decay curve.
- Finer sweep of headway between 0.3–0.5 s at closing_speed 7–9 to localize the cut-in collision boundary precisely, with more repeats per cell.
- Investigate whether TOR timing/threshold logic could be adjusted to issue earlier requests when projected time-to-stop is short, to compensate for distracted-driver reaction delay.

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

- Runs executed: 176
- Target runs: 31
- Distinct target coverage cells: 11
- Runs to first target run: 61

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 11 | 9 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 10 | 7 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 6 | 3 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 11 | 3 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| cut_in | attentive | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 1 | 1 |
| cut_in | distracted | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 1 | 1 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 2 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 176 | 2 | 60 | 31 | 29 | 0 |

## Coverage

124 / 216 coverage cells (57%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `bab92767c65a01b03470da860dfd9624e4d5a609fd181a693ec776a0564435ff`.

### TC-01: Distracted driver combined with strong lead-vehicle braking (lead_decel >= 6 m/s^2) at short-to-moderate initial headway (<=1.2 s) causes frequent collisions in the lead_brake scenario; attentive drivers handle the identical kinematic scenarios without collision. Root cause appears to be the distracted driver's slow takeover time (3-10 s) versus attentive (~0.6-2.2 s).

Predicate: `driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.2`

- Condition SHA-256 `eb6d4aa7bcbd7a1a559156de76f87f09577bc9d8936bffbb2b0ab2cf016cc362`
- Predicate test `17c079442b98` (target `collision`, on 176 runs): 35 runs inside, target rate inside 0.6 [95% two-sided 0.4211, 0.7613], outside 0.07092, lift 8.46
- Evidence query `251c5e98c2a1` (result SHA-256 `cd184d572b2f23bd…`):

```sql
SELECT run_idx, ego_speed, headway, lead_decel, friction, collision, min_ttc, takeover_time FROM runs WHERE driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.2 ORDER BY run_idx
```

| run_idx | ego_speed | headway | lead_decel | friction | collision | min_ttc | takeover_time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 42 | 18.5 | 1.167 | 7.5 | 0.625 | False | 0.523 | 5.434 |
| 51 | 18.5 | 1.167 | 7.5 | 0.875 | False | 0.704 | 3.206 |
| 60 | 25.5 | 1.167 | 7.5 | 0.625 | True | 0.03 | 3.929 |
| 69 | 25.5 | 1.167 | 7.5 | 0.875 | True | 0.039 | 5.254 |
| 78 | 32.5 | 1.167 | 7.5 | 0.625 | True | 0.016 | 5.189 |
| 80 | 18.5 | 1.17 | 6.0 | 0.75 | False | 0.747 | 4.517 |
| 81 | 18.5 | 1.17 | 6.0 | 0.75 | False | 1.382 | 2.792 |
| 82 | 18.5 | 1.17 | 6.0 | 0.75 | False | 0.963 | 3.825 |
| 83 | 18.5 | 1.17 | 6.0 | 0.75 | False | 1.328 | 2.929 |
| 84 | 18.5 | 1.17 | 6.0 | 0.75 | False | 0.907 | 3.968 |
| 85 | 25.5 | 1.17 | 6.0 | 0.75 | True | 0.015 | 4.841 |
| 86 | 25.5 | 1.17 | 6.0 | 0.75 | False | 0.709 | 4.014 |
| 87 | 25.5 | 1.17 | 6.0 | 0.75 | False | 0.863 | 3.886 |
| 88 | 25.5 | 1.17 | 6.0 | 0.75 | True | 0.0 | 4.742 |
| 89 | 25.5 | 1.17 | 6.0 | 0.75 | True | 0.013 | 6.622 |

### TC-02: Cut-in at the extreme corner of the ODD -- very short initial headway (<=0.4 s, near the 0.3 s minimum) combined with high closing speed (>=8 m/s, near the 9 m/s maximum) and sub-dry friction (<1.0) -- produces collisions in essentially all runs, for both attentive and distracted drivers. avoidable_by_reference is true for most of these, indicating this is partly a system response-time/performance gap rather than a purely unavoidable physical scenario.

Predicate: `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND friction < 1.0`

- Condition SHA-256 `0f580b26a38556ac903b718e59004b76f04d05e5ca1e9720b85c690d908aedeb`
- Predicate test `10d29cef45ee` (target `collision`, on 176 runs): 6 runs inside, target rate inside 1 [95% two-sided 0.5407, 1], outside 0.1471, lift 6.8
- Evidence query `81580f5ad3c5` (result SHA-256 `8f9e5520dfe7cc45…`):

```sql
SELECT run_idx, ego_speed, headway, closing_speed, friction, driver_state, collision, min_ttc, avoidable_by_reference FROM runs WHERE scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND friction < 1.0 ORDER BY run_idx
```

| run_idx | ego_speed | headway | closing_speed | friction | driver_state | collision | min_ttc | avoidable_by_reference |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 156 | 32.5 | 0.3 | 9.0 | 0.5 | distracted | True | 0.001 | True |
| 157 | 32.5 | 0.3 | 9.0 | 0.5 | distracted | True | 0.001 | True |
| 158 | 32.5 | 0.3 | 9.0 | 0.5 | attentive | True | 0.01 | True |
| 159 | 32.5 | 0.3 | 9.0 | 0.5 | attentive | True | 0.002 | True |
| 164 | 18.5 | 0.3 | 9.0 | 0.5 | attentive | True | 0.013 | False |
| 165 | 18.5 | 0.3 | 9.0 | 0.5 | distracted | True | 0.013 | False |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | bf1bad683304 | `driver_state = 'distracted' AND lead_decel >= 7 AND scenario = 'lead_brake'` | collision | 80 | 13 | 0.3077 | 0 | - |
| 1 | ca439f597da4 | `driver_state = 'distracted' AND lead_decel >= 7 AND scenario = 'lead_brake'` | near_miss | 80 | 13 | 0.6154 | 0 | - |
| 2 | 07c7e3ef05ce | `driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.2` | collision | 120 | 35 | 0.6 | 0.01176 | 51 |
| 3 | 2649b04c8da2 | `driver_state = 'distracted' AND lead_decel >= 6 AND headway > 1.2` | collision | 120 | 8 | 0.125 | 0.1875 | 0.6667 |
| 4 | 5013adf3e52b | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8` | collision | 168 | 8 | 0.875 | 0.1375 | 6.364 |
| 5 | c17990957927 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8` | near_miss | 168 | 8 | 1 | 0.2062 | 4.848 |
| 6 | 5127b86e9de2 | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND friction < 1.0` | collision | 168 | 6 | 1 | 0.142 | 7.043 |
| 8 | 66c601f0e6b2 | `driver_state = 'distracted' AND friction <= 0.65 AND lead_decel < 6` | collision | 176 | 15 | 0 | 0.1925 | 0 |
| 9 | e5e608727f0f | `driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 2.0` | collision | 176 | 44 | 0.5455 | 0.05303 | 10.29 |
| 12 | 17c079442b98 | `driver_state = 'distracted' AND lead_decel >= 6 AND headway <= 1.2` | collision | 176 | 35 | 0.6 | 0.07092 | 8.46 |
| 13 | 10d29cef45ee | `scenario = 'cut_in' AND headway <= 0.4 AND closing_speed >= 8 AND friction < 1.0` | collision | 176 | 6 | 1 | 0.1471 | 6.8 |
