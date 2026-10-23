# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `agent_s1` · **Author:** agent (claude-sonnet-5) · **Date:** 2026-10-21

## Provenance

- Campaign `agent_s1`: kind `search`, method `agent`, status **COMPLETE**, 260 of 300 planned runs, seed 1, created 2026-10-21 21:52:07
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`; protocol ID: `4a879572d3e65102fa78f013d357c0caaabed603db99992e6a02ba64c8c444a9`
- Data SHA-256: `d40bad2f7c9655ecf6697537b227d8cb448d61c26981156c8ace74bfbf9788ef`
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

## Campaign summary (agent_s1, 260/300 runs used)

I ran a full-factorial coverage sweep across both scenarios (lead_brake, cut_in), both driver states, and the coverage grid (ego_speed × headway × lead_decel/closing_speed × friction), achieving 216/216 coverage cells with ≥1 run each. I then used the collision clusters found in the sweep to form and test two triggering-condition hypotheses, refining each with boundary-search runs (varying one parameter at a time) and repeat trials to sample stochastic takeover time.

## Key findings

**1. Distracted-driver takeover failure under hard lead-vehicle braking (lead_brake).**
With an attentive driver, every lead_brake run in the sweep ended safely regardless of lead_decel up to the ODD maximum (9 m/s²) — the ~1-2 s attentive reaction time is always enough. With a distracted driver, reaction/re-engagement times of several seconds (observed 3-7 s in this campaign) are frequently too slow once lead_decel exceeds roughly 6-6.5 m/s²: boundary search showed 0/2 collisions at decel=6.0, 2/2 collisions at decel=6.5, and a mixed/majority-collision rate from 7.0 up to the 9 m/s² max. This is a driver-state-dependent (foreseeable-misuse) gap: the system issues a TOR correctly, but the ADAS deceleration authority/TOR lead time is insufficient to cover realistic distracted re-engagement delay for strong braking events.
Evidence: predicate `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.5` → 60% collision rate inside (30 runs, 18 collisions) vs 3.5% outside (230 runs), lift ≈17×, 95% CI on inside rate [0.41, 0.77]. A companion breakdown by driver_state (query 39f2d7a8efd7) showed 0/22 collisions for attentive vs 18/30 for distracted under the same lead_decel≥6.5 condition, confirming the effect is concentrated almost entirely in the distracted population rather than being driven by braking severity alone.

**2. Scenario-intrinsic unavoidability at the short-headway / high-closing-speed edge of the cut-in ODD.**
Unlike finding 1, this condition produces collisions for BOTH attentive and distracted drivers: at the minimum headway corner (~0.3 s) combined with closing speed near the ODD maximum (≥~8.5 m/s), collisions occurred even for attentive drivers reacting in ~1-2 s. Boundary search showed headway=0.3 s was safe at closing_speed≤8.0 m/s but collided at 8.5-9 m/s (friction-dependent: friction=1.0 survived one 8.5 m/s/0.3 s trial while friction=0.5 did not), and that increasing headway to just 0.4-0.5 s at the same closing speed fully avoided collision for both driver states. This points to a system/physical performance limit at the extreme corner of the ODD (very short gap + large closing speed) rather than a driver-supervision gap — the available stopping distance/time is too short for the ACC's braking response regardless of who/what intervenes.
Evidence: predicate `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 8.5` → 89% collision rate inside (9 runs, 8 collisions) vs lower outside, lift ≈12.4×, 95% CI on inside rate [0.52, 1.0]. A companion breakdown by driver_state showed attentive 5/6 (83%) and distracted 3/3 (100%) collisions — both high, unlike finding 1 where attentive drivers were unaffected.

## Limitations
- Sample sizes at the exact boundaries are modest (9-30 runs per condition); confidence intervals are wide. Rates reported are from my own targeted search and are NOT real-world incidence estimates — cells were deliberately oversampled near suspected failure boundaries.
- The `avoidable_by_reference` column was not analyzed in depth; a follow-up could check whether finding 2's cases are marked unavoidable by the fixed reference policy, which would support the "scenario-intrinsic" interpretation.
- Only two scenario families (lead_brake, cut_in) and two driver states were in scope, per the ODD; no sensor-noise or multi-agent variants were tested.

## Recommended next tests
1. For finding 1: sweep intermediate decel values (6.0-7.0 m/s²) with more repeats per cell to pin the 50%-collision decel threshold precisely, and vary headway to see if longer initial headway compensates for distracted reaction delay.
2. For finding 2: finer closing_speed sweep (8.0-9.0 m/s step 0.25) crossed with friction (0.5/0.75/1.0) at headway=0.3 to map the exact unavoidable boundary and its sensitivity to friction; also test whether any headway below 0.4 s is survivable at max closing speed (9 m/s) for any friction.
3. Check `avoidable_by_reference` flag distribution inside finding-2's predicate region to confirm whether this is a true physical limit vs. a system under-performance relative to the reference policy.

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

- Runs executed: 260
- Target runs: 26
- Distinct target coverage cells: 13
- Runs to first target run: 12

### Coverage cells with target runs

| scenario | driver_state | ego_speed | headway | friction | scenario_param | runs | collision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 17 | 10 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 10 | 3 |
| cut_in | attentive | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 3 | 2 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 9 | 2 |
| lead_brake | distracted | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 1 | 1 |
| lead_brake | distracted | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 6-9 | 1 | 1 |
| cut_in | distracted | 29-36 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 1 |

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 260 | 0 | 51 | 26 | 26 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.

## Triggering conditions and evidence

Every condition below passed the mandatory evidence protocol (`avval/evidence.py`). Evidence bundle SHA-256: `f156035111a21a5f56a003827767aa35e72e06df6ac066c0924677b66d528d87`.

### TC-01: Distracted driver + hard lead-vehicle braking (lead_decel >= 6.5 m/s^2) in the lead_brake scenario: the driver's delayed re-engagement after the takeover request is frequently too slow to avoid collision, whereas attentive drivers handle the same braking severity safely up to the ODD maximum.

Predicate: `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.5`

- Condition SHA-256 `670e92a4390d30bfd325f4c222808e5ebbc62213e90951a31e81781be6e12b64`
- Predicate test `5b4ab7cf0b0f` (target `collision`, on 260 runs): 30 runs inside, target rate inside 0.6 [95% two-sided 0.406, 0.7734], outside 0.03478, lift 17.25
- Evidence query `4af14d9c3c42` (result SHA-256 `bb50f83287c84306…`):

```sql
SELECT count(*) AS n, sum(CASE WHEN collision THEN 1 ELSE 0 END) AS collisions, round(avg(CASE WHEN collision THEN 1.0 ELSE 0.0 END),3) AS rate FROM runs WHERE scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.5
```

| n | collisions | rate |
| --- | --- | --- |
| 30 | 18 | 0.6 |

### TC-02: Short initial headway (<=0.35 s) combined with high closing speed (>=8.5 m/s) at cut-in: collisions occur for both attentive and distracted drivers, indicating a scenario/system-performance limit near the extreme corner of the ODD rather than a driver-supervision failure.

Predicate: `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 8.5`

- Condition SHA-256 `99eb5783ef1dec8b3b63d4ab7ab44fdc745b0fc448621c7c1d9bf99fa6144ab8`
- Predicate test `6463d90fd272` (target `collision`, on 260 runs): 9 runs inside, target rate inside 0.8889 [95% two-sided 0.5175, 0.9972], outside 0.07171, lift 12.4
- Evidence query `b7033faa676e` (result SHA-256 `bf4906f299db0e79…`):

```sql
SELECT count(*) AS n, sum(CASE WHEN collision THEN 1 ELSE 0 END) AS collisions, round(avg(CASE WHEN collision THEN 1.0 ELSE 0.0 END),3) AS rate FROM runs WHERE scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 8.5
```

| n | collisions | rate |
| --- | --- | --- |
| 9 | 8 | 0.889 |

## Hypothesis tests

Every `test_predicate` call, in order, over the agent's own runs (full records in the evidence bundle).

| # | id | where | target | runs | inside | rate inside | rate outside | lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | f4bb42b34d4a | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.5` | collision | 216 | 30 | 0.6 | 0.04301 | 13.95 |
| 2 | 5167a47d596d | `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 8.5` | collision | 216 | 9 | 0.8889 | 0.08696 | 10.22 |
| 5 | 5b4ab7cf0b0f | `scenario = 'lead_brake' AND driver_state = 'distracted' AND lead_decel >= 6.5` | collision | 260 | 30 | 0.6 | 0.03478 | 17.25 |
| 6 | 6463d90fd272 | `scenario = 'cut_in' AND headway <= 0.35 AND closing_speed >= 8.5` | collision | 260 | 9 | 0.8889 | 0.07171 | 12.4 |
