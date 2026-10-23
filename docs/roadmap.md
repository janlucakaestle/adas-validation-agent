# Roadmap

Ordered by how much each item changes the current conclusions, from most to least.

## 1. Close the assumptions that dominate the current result

- **Attentive-driver timing.** The attentive driver currently reacts at the takeover
  request; a real attentive driver often reacts at hazard onset. This makes AC-01
  pessimistic, and it has to be settled before AC-01 drives an ODD or design decision.
- **Careful and competent human reference.** Preventability should have two tiers:
  collisions an ideal system could avoid, and collisions a competent human would also have
  had. That separates the function's own share of risk from risk inherent to the scenario.
- **Justified targets.** AC-03's 5% threshold should come from a residual-risk argument,
  not an illustrative choice.
- **Evidence for the driver model.** Replicate the published takeover experiment in the
  simulator and compare crash rates. This is the only check of the driver model against
  observed outcomes. It needs the cut-out scenario (section 4).

## 2. Bring perception into scope

- **Detection range** as a triggering-condition parameter. It is the first perception
  insufficiency; the controller currently sees ground truth.
- **A derived detection-range requirement,** computed from the preventability reference.
  This turns a validation finding into a specification input.

## 3. Strengthen metric and criterion definitions

- **Brake threat number replaces time-to-collision** as the criterion metric.
  Time-to-collision ignores how much braking is still available.
- **Settle the comfort metric** with jerk over a 1 s window. AC-04 fails in the cut-in
  stratum (95th percentile 5.17 m/s³, lower bound 5.167 above the 5 m/s³ target) while the
  overall value, 4.95 m/s³, is below it; the status still depends on how jerk is computed.
- **Failures of commission.** Add unnecessary harsh braking as a criterion and a search
  target. The nuisance-alarm metric for hand-backs that weren't needed is done (AC-08).
- **Hand-back threshold trade-off.** An indicative one-at-a-time result exists (README
  finding 5). Next: a dedicated sweep with enough hand-back-required runs per point (each
  2,000-run sensitivity variant has only 55).
- **Derive the tolerable rates** of AC-01/AC-03 and the `min_n` values from a residual-risk
  argument (the one-sided bound rules and the n needed to pass are implemented).
- **Joint exposure model** from fleet data (the factor-graph interface supports it).

## 4. Widen the scenario space

- **Cut-out:** the lead vehicle swerves away and reveals a stopped car, a classic ACC blind
  spot the current scenarios can't produce.
- **Step-size check at dt = 0.01 s** (dt/2 is done; runs reaching the horizon are now
  classified `horizon_safe` / `horizon_unresolved`).

## 5. Evidence that agent-assisted discovery earns its place

- **Several budgets and models,** under a spend cap. Ten seeds at one budget are done.
- **Target-agnostic ablation**: a benchmark variant in which derived semantic labels (e.g.
  `avoidable_by_reference`) are hidden from every strategy, to separate semantic reasoning
  from search efficiency.
- **Definition sensitivity**: re-evaluate stored campaigns under alternative reference levels
  and hand-back capabilities (replaying only the references, no new system simulation).
- **Derive targets for AC-09/AC-10** (reference-independent collision risk) and approve or
  replace every illustrative requirement; until then no formal GO is possible.
- **Decision-tree rule extraction** as a baseline for submitted conditions (the
  cross-entropy, evolutionary, boundary-seeking and Bayesian-optimisation searchers ran in
  the v1.0 benchmark).
- **Recall against ground truth:** score every strategy on recall of known failure regions,
  using a brute-force ground truth.
- **Planted defect:** a known fault in the system under test, to measure whether each
  strategy finds it.
- **Anonymised parameters:** test whether the agent relies on domain knowledge of
  parameter names or on the data alone.

## 6. Release integrity

- **Container image digest** in the runtime fingerprint (the lock file and runtime ID exist).
- **Retrain on closed-loop driving logs.** This deliberately changes every result, which
  also exercises the full re-validation path.
