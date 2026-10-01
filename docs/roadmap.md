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
- **Settle the comfort metric** with jerk over a 1 s window. AC-04 currently sits on its
  threshold, and its status depends on how jerk is computed.
- **Failures of commission.** Add unnecessary harsh braking as a criterion and a search
  target, and a nuisance-alarm metric for hand-backs that weren't needed.
- **Hand-back threshold trade-off.** An earlier takeover request gives a distracted driver
  more time, but raises more nuisance alarms. Sweep the threshold and quantify both.
- **Evidence rules.** Finish the confidence-bound rules, including the number of runs needed
  to decide each criterion.

## 4. Widen the scenario space

- **Cut-out:** the lead vehicle swerves away and reveals a stopped car, a classic ACC blind
  spot the current scenarios can't produce.
- **Horizon and step-size checks:** a per-run flag showing the 20 s horizon never cuts a run
  short, and a dt = 0.01 s comparison.

## 5. Evidence that agent-assisted discovery earns its place

- **More seeds at several budgets,** under a spend cap.
- **Adaptive baselines:** the cross-entropy method and decision-tree rule extraction, so
  the agent is compared with adaptive search, not just random and grid.
- **Recall against ground truth:** score every strategy on recall of known failure regions,
  using a brute-force ground truth.
- **Planted defect:** a known fault in the system under test, to measure whether each
  strategy finds it.
- **Anonymised parameters:** test whether the agent relies on domain knowledge of
  parameter names or on the data alone.

## 6. Release integrity

- **Freeze and fingerprint the system under test.** Campaigns should refuse to run on a
  mismatch. Hashing and release matching already exist.
- **Retrain on closed-loop driving logs.** This deliberately changes every result, which
  also exercises the full re-validation path.
