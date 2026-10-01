# Changelog

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
- **Results.** The agent finds the rare attentive-driver collision mode in 10 of 10 seeds
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
