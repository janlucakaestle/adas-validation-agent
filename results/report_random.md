# Search report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `random` · **Author:** baseline (random) · **Date:** 2026-09-30

## Provenance

Recorded when the campaign was created (2026-09-30 19:58:48); method `random`, budget 300, seed 0.

- Policy (`results/policy.json`) SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`
- Source code (`avval/*.py`) SHA-256: `013dfb4c010a2ec66b5b2ab55a4135888d2c0aa6f9f3dac32b053f394944e563`
- Git commit: `43cb1ae50f56ebd58ab4dfab766e88eb5b371b02`
- Python 3.11.9; duckdb 1.5.5, numpy 2.4.6, scikit-learn 1.9.1
- Config `acceptance.yaml` SHA-256: `a7b59b09f1f62392bb43c562f6123b44e8cbedfbf105906dd7e4a72883254876`
- Config `driver.yaml` SHA-256: `b9dfc342b59084813b0e7d0125e655fae1996b254fce1bfc08f577cac84953b8`
- Config `exposure.yaml` SHA-256: `2b95ea73f490f4dfa3626f4cccbf31d5279d936a469e45a7da5eb1945750d3fe`
- Config `odd.yaml` SHA-256: `6551f07c7bb57a5a19f98a4fba07fc6951fc1980e38caf3aff22faadaf06147e`
- Config `reference.yaml` SHA-256: `5d96ab3655542260859e4c3f03c777413f20c97adc59f47deff4f3e8e0fefc06`

## Summary

A **random** baseline search campaign. It reports what it found (discovery metrics, failing coverage cells) but no release verdict: verdicts come only from the exposure-weighted estimation campaign (`python -m avval.cli estimate`). No triggering-condition analysis is performed by the baseline.

## Discovery

Search campaigns choose where to look, so their failure *rates* say nothing about real-world risk and are not reported. What matters is what the search found and how fast.

- Runs executed: 300
- Failing runs (`collision OR coalesce(min_ttc < 1.5, false)`): 34
- Distinct failing coverage cells: 22
- Runs to first failure: 19

### Failing coverage cells

| scenario | ego_speed | headway | friction | scenario_param | runs | failing | preventable_collisions |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lead_brake | 29-36 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 4 | 4 | 2 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 4 | 4 | 3 |
| cut_in | 15-22 | 0.3-0.8667 | 0.5-0.75 | closing_speed 6-9 | 2 | 2 | 2 |
| lead_brake | 15-22 | 0.8-1.5333 | 0.75-1 | lead_decel 6-9 | 2 | 2 | 1 |
| lead_brake | 29-36 | 2.2667-3 | 0.5-0.75 | lead_decel 6-9 | 4 | 2 | 1 |
| lead_brake | 22-29 | 2.2667-3 | 0.5-0.75 | lead_decel 3.5-6 | 4 | 2 | 0 |
| cut_in | 22-29 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 7 | 2 | 0 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 8 | 2 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 3.5-6 | 1 | 1 | 0 |
| lead_brake | 22-29 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 2 | 1 | 1 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.75-1 | lead_decel 6-9 | 2 | 1 | 1 |
| lead_brake | 15-22 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 2 | 1 | 0 |
| cut_in | 29-36 | 0.3-0.8667 | 0.75-1 | closing_speed 6-9 | 3 | 1 | 0 |
| lead_brake | 29-36 | 1.5333-2.2667 | 0.5-0.75 | lead_decel 6-9 | 3 | 1 | 1 |
| lead_brake | 22-29 | 0.8-1.5333 | 0.5-0.75 | lead_decel 6-9 | 3 | 1 | 0 |

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 13 | 13 | 0 | 0 |

## Coverage

100 / 108 coverage cells (93%) meet the minimum run count.

## Triggering conditions and evidence

_None reported._