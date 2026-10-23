# Changelog

## v1.0 (2026-10-23)

**Final campaigns of release `fe59625d…`: estimation, a seven-strategy benchmark, a frozen
hold-out and a sensitivity study. Results in `results/`, corrections in
[`docs/corrections.md`](docs/corrections.md).**

- **v0.2 results withdrawn,** superseded by the corrected simulator, the revised acceptance
  criteria and the frozen protocols.
- **v0.2 finding 2 (the hand-back monitor blind spot) is retracted.** The acceleration-aware
  TTC behind it extrapolated a braking lead vehicle past standstill, as if it then reversed
  towards the ego vehicle. With a stop-aware TTC, no run of the 180,000 baseline runs erodes
  the margin without a hand-back. Analytic stopping-lead and timestep-convergence tests were
  added because of it.
- **Fail-closed requirement status:** every criterion carries a requirement maturity; a
  provisional, illustrative or undefined requirement can never yield a formal GO (verdict
  DECISION PENDING REQUIREMENTS).
- **Reference-independent collision gates:** AC-09/AC-10 count every collision whatever the
  reference response says; AC-03 counts every distracted-driver collision the reference
  avoids, stratified by hand-back need; new AC-07 (missed or late hand-back) and AC-08
  (unneeded hand-backs); gating populations use scenario columns only.
- **Four added baselines:** CEM, evolutionary, boundary and Bayesian-optimisation search,
  alongside random and grid, on the agent's interface and budget, under a frozen, hashed
  protocol; matched-budget comparison with baseline uncertainty propagated and a
  Kaplan–Meier time to first target; scoped conclusions.
- **Hold-out:** agent and reference predicates are frozen, then scored on a fresh
  100,000-run campaign with exposure-support classes; replaces the v0.2 post-hoc check.
- **Sensitivity redesign:** 16 factors (driver, monitor, delays, authority, exposure) in OAT,
  two-level factorial and Latin-hypercube designs, 171 variants of 2,000 runs on common
  random numbers, under a frozen protocol; authority above the training authority uses a
  re-trained policy.
- **Simulator:** current-step lead acceleration reaches the monitor in the same step; exact
  piecewise kinematics with in-step contact roots; continuous required deceleration;
  stop-aware acceleration TTC; explicit terminal states including `horizon_unresolved`;
  configurable actuator and monitor delays; driver standstill brake hold (fixes creeping
  late contacts). All constants in `config/sim.yaml`.
- **Statistics:** exact one-sided Clopper–Pearson and order-statistic bounds; positive
  tolerable rates with permanent zero goals; per-stratum checks.
- **Provenance and evidence packaging:** immutable parsed configuration; release ID over
  parsed configs, policy and code, with overrides first-class; runtime fingerprint and lock
  file; schema-checked store (v4); resumable campaigns with lifecycle and data hashes;
  final-evidence mode (clean tree, lock, release-addressed output); a verifiable evidence
  package with every campaign behind the claims (attached to the GitHub Release) and
  `results/EVIDENCE_MANIFEST.json`.
- **Agent:** shared search interface with a column allowlist; discovery objectives separate
  from acceptance; the leaks of the AC-02 boundary and the reference level removed; semantic
  secret-boundary tests; mandatory, content-addressed evidence protocol; complete
  transcripts (`results/agent/`).
- **Exposure and coverage:** factor-graph exposure model with full-ODD support validation;
  driver state is a coverage dimension (216 cells).

## v0.2 (2026-10-01)

**10 agent seeds; matched-budget comparison per seed.**

- **Seven more agent seeds** (seeds 3–9, Claude Sonnet 5, 300-run budget, $4.47 together).
  How all ten seeds would be reported, including the one test of "more reliably", was fixed
  in `docs/agent_protocol.md` and committed before seeds 3–9 ran. One deviation, recorded
  before they ran: the estimation was re-run after the seeds instead of before, because the
  host stopped it twice for low memory. All ten seeds are reported.
- **Matched budget per seed.** Each agent seed is compared with the 100 random and 100 grid
  campaigns cut to that seed's own number of runs, instead of to the agent's mean. A
  Poisson-binomial test gives the probability that a baseline would match the agent's
  detections at the same budgets.
- **Results** (withdrawn in v1.0; see [`docs/corrections.md`](docs/corrections.md)). The agent
  finds the rare attentive-driver collision mode in 10 of 10 seeds
  (95% CI 0.69–1.00). Random and grid search at the same budgets would be expected to find it
  in 4.9 and 4.1 of 10 (probability of 10 of 10: 7.4 × 10⁻⁴ and 1.3 × 10⁻⁴). At matched
  budgets the agent also finds slightly more distinct failing cells (16.1 against 14.4 and
  15.4); v0.1's "fewer cells" came from comparing at the agent's mean budget. It still
  reaches its first failure later.
- **Post-hoc check for all ten seeds.** 24 submitted conditions re-evaluated on the held-out
  100,000 runs. 8 of 10 seeds stated the collision mode as a condition that holds collisions
  there. Four conditions name exact ODD corners and are empty on held-out data.
- **Agent reports** for all ten seeds carry the release verdict, re-rendered once this
  release's estimation existed; each report says so.
- **Estimation re-run under v0.2 code** reproduced v0.1's estimation exactly; only the
  provenance lines changed.
- **Code:** comments, config and tests no longer cite internal documents. `posthoc` covers
  every agent seed by default and lists seeds that submitted nothing.
- **Known issue:** the post-hoc comparison table labels a condition that holds no held-out
  runs as "disjoint". For the four empty conditions it means empty.

## v0.1 (2026-10-01)

First public release.

- Learned SAE Level 2 ACC with a takeover request, simulated in two longitudinal scenarios
  with an attentive and a distracted driver.
- Acceptance criteria with evidence rules (Clopper–Pearson and bootstrap intervals,
  minimum sample sizes), evaluated only on an exposure-weighted estimation campaign of
  100,000 runs: NO-GO, with AC-01, AC-03 and AC-04 failing.
- Random and grid search benchmarked over 100 seeds each; an LLM agent run for three seeds.
- Provenance hashes tie every result to the policy, config and code it was computed on.
