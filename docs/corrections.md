# Corrections to v0.2

v0.2 published five findings and an agent benchmark. Rebuilding the simulator and the
acceptance logic for v1.0 showed that one finding was wrong, and that several others rested
on definitions or statistics that could not carry them. This page lists what was corrected
and why. v0.2 numbers come from the v0.2 result files (`git show v0.2:results/<file>`);
corrected numbers come from [`results/`](../results/) and are conditional on the placeholder
exposure weights and driver parameters. Code comments that refer to `REMEDIATION_SUMMARY.md`
point to an internal working document that is not part of this release; this page
summarises it.

## Retracted or changed findings

**1. The hand-back monitor blind spot (v0.2 finding 2): retracted.**
- *v0.2 claim:* the monitor's TTC check assumes a constant lead speed, so in 822 of 60,000
  random and grid runs (all lead braking, minimum 1.65 s) an acceleration-aware TTC fell
  below the 2 s threshold with no hand-back (`findings.md` at v0.2).
- *What was wrong:* the acceleration-aware TTC extrapolated a braking lead vehicle past
  standstill, as if it then reversed towards the ego vehicle. The "erosion" was produced by
  the metric, not by the monitor.
- *How it was found:* while fixing the simulator's step ordering, the old metric was applied
  to corrected traces. It flagged runs only at instants where the lead was about to stop, and
  a stop-aware version of the same metric flagged none. Analytic stopping-lead tests and a
  timestep-convergence study were added because of it (`tests/test_sim_and_metrics.py`,
  `tests/test_sim_verification.py`).
- *Corrected result:* 0 runs of margin erosion without a hand-back in 180,000 baseline runs
  ([`findings.md`](../results/findings.md)); no hazardous run without a takeover request in
  the 100,000-run estimation ([`handback_diagnostics_estimate.md`](../results/handback_diagnostics_estimate.md)).

**2. "The agent finds the rare collision mode more reliably than search" (v0.2 benchmark): changed.**
- *v0.2 claim:* 10/10 agent seeds against 4.88 and 4.10 expected for random and grid search,
  probability 7.4e-04 and 1.3e-04 (`benchmark.md` at v0.2).
- *What was wrong:* the probabilities were plug-in values that ignored the uncertainty in the
  baselines' detection rates; there were only two non-adaptive baselines; three seeds ran
  before the protocol was written; and the agent could see the AC-02 boundary and the
  reference deceleration level.
- *How it was found:* by re-deriving the test statistic and auditing everything the agent's
  prompt and tools exposed.
- *Corrected result:* under a frozen protocol, with the leaks removed and four adaptive
  baselines added, the agent still detects the region in 10/10 seeds. Its advantage holds
  over random, grid and boundary search (95% upper bounds 0.007, 0.002, 9.6e-07), is
  borderline over evolutionary search (0.043) and absent over CEM (0.156) and Bayesian
  optimisation (0.996), which detected the region in 100 of 100 campaigns
  ([`benchmark.md`](../results/benchmark.md)).

**3. AC-03, collisions after hand-back to a distracted driver (9.3% at v0.2): changed.**
- *What was wrong:* the population was conditioned on the system issuing a takeover request,
  so a system that issued fewer requests could shrink its own denominator.
- *Corrected result:* AC-03 now counts every distracted-driver run the reference avoids. It
  fails at 1.88% overall because of the stratum where hand-back is required: 47.7%
  (n = 537), while AC-07 records 0 missed or late hand-backs out of 2,647
  ([`report_estimate.md`](../results/report_estimate.md)).

**4. "The metric definition decides AC-04" (v0.2 finding 3, 5.04 m/s³): changed.**
- *What was wrong:* the population was runs without a hand-back, which again depends on the
  system's own behaviour.
- *Corrected result:* jerk is measured over automated-control intervals of all runs:
  4.95 m/s³ overall, failing in the cut-in stratum at 5.17 m/s³; 4,499 of the 4,554 runs
  above 5 m/s³ are cut-ins ([`findings.md`](../results/findings.md)).

**5. "Design matters more than the attentive driver's reaction time" (v0.2 finding 4): withdrawn.**
- *What was wrong:* four factors were varied one at a time, and authority variants above
  3.5 m/s² confounded actuator authority with policy extrapolation.
- *Corrected result:* 16 factors over 171 variants (OAT, factorial, Latin hypercube). AC-03
  fails in all 171 variants; AC-02 depends on the driver's brake demand
  ([`sensitivity_oat.md`](../results/sensitivity_oat.md) and the factorial and LHS reports).

**6. Post-hoc check of the agent's conditions: replaced.**
- *What was wrong:* the reference box was derived from, and scored on, the same estimation
  campaign, so it was not a held-out evaluation.
- *Corrected result:* predicates are frozen and scored on a fresh 100,000-run hold-out. The
  distracted lead-braking condition is exposure-supported in 8 of 10 seeds; 8 of 10 cut-in
  conditions have zero exposure measure ([`holdout_predicates.md`](../results/holdout_predicates.md)).

## Methodological changes

- **Fail-closed requirement status:** a provisional, illustrative or undefined requirement can never yield a formal GO.
- **Reference-independent collision gates:** AC-09/AC-10 count every collision, whatever the reference says.
- **Added baselines:** CEM, evolutionary, boundary and Bayesian-optimisation search join random and grid.
- **Frozen hold-out:** predicates and the hold-out seed and size are hashed before a fresh campaign scores them.
- **Sensitivity redesign:** 16 factors in OAT, two-level factorial and LHS designs, common random numbers, frozen protocol.
- **Provenance and evidence packaging:** release IDs over parsed config, policy and code; a verifiable evidence package.
- **Simulator:** same-step monitor timing, in-step contact roots, stop-aware TTC and a driver standstill brake hold.
