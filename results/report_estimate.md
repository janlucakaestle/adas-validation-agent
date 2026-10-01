# Validation report: Adaptive Cruise Control (learned policy) with driver-intervention request, SAE L2

**Campaign:** `estimate` · **Author:** estimation (automatic) · **Date:** 2026-10-01

## Provenance

Recorded when the campaign was created (2026-10-01 02:29:01); method `estimate`, budget 100000, seed 0.

- Policy (`results/policy.json`) SHA-256: `5e14254aff132c1b2d674702e85ad3cc3d2c326c6c2440d9f3e43861ceb1a214`
- Source code (`avval/*.py`) SHA-256: `330d6d3bcb9a0e3323d41a5ae68bd1042fa00ecfcbe74c4c8bc0c74a893a2c9c`
- Git commit: `7a91541b28e9b17eaadb7dc9d441a8b8ee3f77df`
- Python 3.11.9; duckdb 1.5.5, numpy 2.4.6, scikit-learn 1.9.1
- Config `acceptance.yaml` SHA-256: `f294c520054a85c4f5df8b99563e1e390982061a5a225acafd66a5aeb1e0f5fe`
- Config `driver.yaml` SHA-256: `b9dfc342b59084813b0e7d0125e655fae1996b254fce1bfc08f577cac84953b8`
- Config `exposure.yaml` SHA-256: `2b95ea73f490f4dfa3626f4cccbf31d5279d936a469e45a7da5eb1945750d3fe`
- Config `odd.yaml` SHA-256: `c2f1afb3bbd345c00eae9a27a8c90d2dcde82b46a93116475d699b2b2fe88d52`
- Config `reference.yaml` SHA-256: `43ab88cffbef2c0d8c0897fd6a0c75a205171dc5cae8cec0bc906f6cf0f6a709`

## Verdict: NO-GO

Evaluated on the exposure-weighted estimation campaign `estimate` (100000 runs sampled from `config/exposure.yaml`, whose weights are illustrative placeholders): criteria AC-01, AC-03, AC-04 failed.

## Acceptance criteria

| id | name | value | 95% CI | target | n | min_n | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AC-01 | Collision-free with attentive supervision | 0.000837 | [0.000649, 0.00106] | <= 0.0 | 80025 | 100 | FAIL |
| AC-02 | TTC safety margin | 1.89 | [1.88, 1.89] | >= 1.5 | 99514 | 100 | PASS |
| AC-03 | Hand-back robustness under foreseeable misuse | 0.0927 | [0.0844, 0.102] | <= 0.05 | 4509 | 100 | FAIL |
| AC-04 | Longitudinal comfort | 5.04 | [5.03, 5.05] | <= 5.0 | 77863 | 100 | FAIL |
| AC-06 | Share of unpreventable runs (information only) | 1e-05 | [2.53e-07, 5.57e-05] | - | 100000 | 100 | INFO |

Rates use a 95% Clopper-Pearson interval, quantiles a 95% percentile bootstrap (fixed seed). A PASS needs the conservative end of the interval to meet the target.

## Preventability

A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 count preventable runs only.

| collisions | preventable_collisions | unpreventable_collisions | unpreventable_runs |
| --- | --- | --- | --- |
| 486 | 485 | 1 | 1 |

## Coverage

108 / 108 coverage cells (100%) meet the minimum run count.
