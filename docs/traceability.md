# Validation traceability map

Each validation concept, and where it is defined and implemented.

| Validation concept | Where |
| --- | --- |
| ODD definition and parameter space | `config/odd.yaml` |
| Acceptance criteria written *before* testing, evaluated as SQL | `config/acceptance.yaml`, `avval/evaluation.py` |
| Driving metrics (TTC, acceleration-aware TTC, THW, filtered and raw jerk, decel, impact speed, hand-back timing) | `avval/sim.py::compute_metrics` |
| Coverage requirement (108 cells) and gap reporting | `avval/evaluation.py::coverage` |
| Learned system under test (MLP behaviour-cloned from IDM) | `avval/policy.py` |
| Driver fallback / foreseeable misuse (SOTIF) | `config/driver.yaml`, `avval/driver.py` |
| Results store with read-only, campaign-scoped SQL | `avval/store.py` (DuckDB) |
| LLM agent with tool use, budget and ODD enforcement | `avval/agent.py` |
| Baselines, multi-seed benchmark, discovery curves | `avval/baselines.py`, `avval/benchmark.py`, `avval/plots.py` |
| Exposure model and estimation campaign | `config/exposure.yaml`, `avval/estimation.py` |
| Estimation and search reports | `avval/report.py` |
| Preventable vs. unpreventable failures | `avval/reference.py`, `config/reference.yaml` |
| Held-out check of agent predicates; numbers behind the findings | `avval/posthoc.py`, `avval/findings.py` |
| Sensitivity to modelling assumptions | `avval/sensitivity.py` |
| Traceability: policy, config and code hashes | `avval/provenance.py`, `campaigns` table |
| Agent evaluation protocol, fixed before seeds 3–9 ran | `docs/agent_protocol.md` |
| Re-rendering agent reports; AC-01 cluster analysis | `scripts/rerender_agent_reports.py`, `scripts/ac01_clusters.py` |
| Every number in the docs, with its source | `docs/readme_claims.md` |
| Tests, including the agent loop with a scripted fake LLM | `tests/` |
