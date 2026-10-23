# Validation traceability map

Each validation concept, and where it is defined, implemented and tested.

| Validation concept | Where | Tests |
| --- | --- | --- |
| ODD definition, coverage dimensions (incl. driver state) | `config/odd.yaml`, `avval/evaluation.py::coverage` | `test_store_and_evaluation.py` |
| Immutable release configuration and release ID | `avval/config.py`, `avval/frozen.py` | `test_provenance.py` |
| Simulator, step ordering, exact contact, terminal states | `config/sim.yaml`, `avval/sim.py` | `test_sim_timing.py`, `test_sim_verification.py`, `test_sim_and_metrics.py` |
| Learned system under test (demonstrator) | `avval/policy.py` | `test_provenance.py` |
| Driver fallback / foreseeable misuse | `config/driver.yaml`, `avval/driver.py` | `test_driver_model.py`, `test_driver_config.py` |
| Reference responses and hand-back oracle | `config/reference.yaml`, `avval/reference.py` | `test_reference.py` |
| Acceptance criteria, populations, one-sided statistics, requirement maturity and verdict layers | `config/acceptance.yaml`, `avval/evaluation.py` | `test_acceptance.py` |
| Driver standstill brake hold (behavioural assumption) | `config/driver.yaml`, `avval/sim.py` | `test_standstill_hold.py` |
| Final-evidence mode and release-addressed output | `avval/cli.py --final`, `avval/campaign.py`, `avval/provenance.py` | `test_diagnostics_cli.py` |
| Exposure model and estimation eligibility | `config/exposure.yaml`, `avval/exposure.py`, `avval/estimation.py` | `test_exposure.py`, `test_estimation.py` |
| Campaign identity, lifecycle, deterministic streams, resume | `avval/campaign.py`, `avval/store.py` | `test_campaign.py` |
| Versioned schema, constraints, sandboxed SQL | `avval/store.py` | `test_store_and_evaluation.py`, `test_sql_guard.py` |
| Search interface and secret boundary | `avval/search.py`, `avval/protected.py` | `test_agent_isolation.py` |
| LLM agent and evidence protocol | `avval/agent.py`, `avval/evidence.py` | `test_agent_loop.py`, `test_evidence.py`, `test_predicate.py` |
| Baselines (random, grid, adaptive) and frozen benchmark | `avval/baselines.py`, `config/benchmark.yaml`, `avval/benchmark.py` | `test_benchmark.py` |
| Held-out evaluation: frozen predicates and frozen execution protocol | `avval/holdout.py`, `avval/clusters.py` | `test_holdout.py` |
| Sensitivity designs and frozen sensitivity protocol | `config/sensitivity.yaml`, `avval/sensitivity.py` | `test_sensitivity.py`, `test_standstill_hold.py` |
| Hand-back diagnostics | `avval/diagnostics.py`, `avval/replay.py` | `test_diagnostics_cli.py` |
| Compatibility of historical evidence | `avval/compat.py`, `scripts/rerender_agent_reports.py` | `test_compat_package.py` |
| Evidence packages (selection by manifests/IDs, deep verification) and runtime lock | `avval/package.py`, `avval/evidence.py::verify_bundle`, `avval/provenance.py`, `scripts/lock_env.py` | `test_package.py`, `test_diagnostics_cli.py` |
| Reports | `avval/report.py` | throughout |
| Final v1.0 results and evidence manifest | `results/`, `results/EVIDENCE_MANIFEST.json` | `verify-package` |
| Corrections to v0.2 findings | `docs/corrections.md` | — |
