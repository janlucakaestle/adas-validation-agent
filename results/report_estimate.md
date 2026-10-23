# Validation report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `estimate` · **Author:** estimation (automatic) · **Date:** 2026-10-22

## Provenance

- Campaign `estimate`: kind `nominal_estimation`, method `estimate`, status **COMPLETE**, 100000 of 100000 planned runs, seed 0, created 2026-10-21 20:05:17
- Release ID: `fe59625d9428753862687a3969fa0abf194b64e8afeabe42898bdbcca7498d81`
- Runtime ID: `d37505bee00e01c235487f54dbb579f8dc71978020d9565f2c940eb2fcf3ae3c`; exposure model ID: `9b025cdb5828fa42574c0dd79797f6b94434d542e7bef4529b3194c10a025abc`
- Data SHA-256: `8458f60a7075bf46d593bc338e6043cfa77766c948b520a605d7dd2663adb44e`
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

## Verdict: NO-GO

- **Engineering verdict** (evidence against the configured targets): **NO-GO**
- **Requirement maturity:** not approved: AC-01, AC-02, AC-03, AC-04, AC-07, AC-08, AC-09, AC-10. A provisional, illustrative or undefined requirement can never authorise release (a violation still counts as NO-GO).
- **Formal release decision:** **NO-GO**

Evaluated on `estimate` (100000 runs sampled from the exposure model): criteria AC-01, AC-03, AC-04 failed. no requirement defined for AC-09, AC-10.

## Acceptance criteria

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

## Exposure model

`factorized-placeholder` (factorized, status: **placeholder**). Independent factors except headway and the scenario-specific parameter, which depend on the scenario. Weights are invented; all risk numbers are conditional on this model. Every rate and quantile in this report is conditional on this model.

Zero-exposure subregions (inside the ODD, explicitly weighted 0): none.

## Reference outcomes

`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: braking at a fixed deceleration (the nominal design authority, frozen) from hazard onset does not avoid contact (independent of the tested ACC's authority). Both are scenario properties, computed for every run independently of the system.

| runs | not_avoided_by_reference | handback_required | collisions | collisions_avoidable_by_reference | unresolved |
| --- | --- | --- | --- | --- | --- |
| 100000 | 3 | 2647 | 448 | 445 | 0 |

## Coverage

216 / 216 coverage cells (100%) meet the minimum run count, over the full set of ODD coverage dimensions: scenario, driver_state, ego_speed, headway, lead_decel, friction. Coverage is structural: it says nothing about how often the function fails in a cell.
