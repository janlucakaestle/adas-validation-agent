# Known limitations

## What SOTIF requires that this project does not do

- **No hazard analysis and risk evaluation.** Acceptance criteria are illustrative and
  written before testing, not derived from a HARA.
- **No justified validation targets.** Thresholds, tolerable rates, `min_n`, confidence and
  all exposure weights are placeholders (`TODO(data)`).
- **No perception insufficiencies.** Ground-truth gap, speeds and lead deceleration.
- **No safety argument for the learned component** (ISO/PAS 8800): no training-data
  specification, data-quality management or runtime OOD monitoring.

## The system under test is a demonstrator

- A 32×32 MLP behaviour-cloned from a synthetic IDM expert, with four ground-truth inputs.
  No perception, noise, temporal model, uncertainty, lateral behaviour or OOD handling.
  Results do not transfer to production learned ADAS stacks.
- ACC authority above the training authority is studied with a re-trained policy; with
  `authority_mode: saturate` such variants are labelled confounded.

## Modelling

- **Longitudinal only**, two scenarios; a cut-in simply appears at its headway.
- **Driver states change reaction delay and braking only.** Both states react at the TOR
  (pessimistic for the attentive driver). The standstill brake hold, brake demand, jerk,
  peak deceleration and onset delay are placeholders.
- **One distracted-driver source** (n = 19, reading task, hazard at ≈ 7 s TTC).
- **Reference responses are scoped**: brake-only, no steering, no pre-hazard braking,
  perfect knowledge at onset, a configured deceleration level. "Not avoided by reference"
  is not physical inevitability. The careful-competent-driver reference is disabled.
- **Hand-back oracle** (`handback_required`) is "braking at a fixed 3.5 m/s² from hazard
  onset cannot avoid contact". 3.5 m/s² is the nominal system's own design authority (the
  demonstrator's training authority), frozen; it is not an external capability requirement,
  and its assumed match with a published ACC deceleration envelope (ISO 15622) has not been
  verified (provisional, source to be confirmed). Being fixed, it keeps the populations of
  design variants identical; it only stratifies AC-03 and defines AC-07/AC-08, so a
  distracted collision is gated whatever its value. The same number is the sensitivity
  study's required-deceleration exceedance level.
- **No target is defined for the reference-independent collision criteria** (AC-09/AC-10);
  until one is approved, formal GO is impossible by construction.
- **All acceptance requirements are illustrative**, the hand-back oracle provisional: the
  framework can produce NO-GO, INSUFFICIENT EVIDENCE or DECISION PENDING REQUIREMENTS, but
  not a formal GO, until they are approved.
- **Standstill brake hold** (2.0 m/s²) is a behavioural placeholder, varied 1–4 m/s² in the
  sensitivity study.
- **Monitor and actuator delays** are modelled but zero at the nominal point.
- **Exposure is factorized** with invented weights; correlations between speed, headway,
  friction and driver state are not modelled. Every rate is conditional on it.

## Statistical

- One-sided bounds at 95% per criterion; no multiplicity adjustment across criteria or
  strata (a GO requires every criterion and stratum to pass, which is conservative for the
  verdict but not a family-wise statement).
- FAIL on a point-estimate exceedance is deliberately conservative; reports say whether the
  exceedance is statistically demonstrated.
- The order-statistic quantile bounds are conservative with ties (e.g. many identical
  infinite TTCs).
- The benchmark's posterior-predictive analysis treats agent seeds as fixed observed
  outcomes and propagates only baseline uncertainty; the agent-side uncertainty is reported
  as a Clopper–Pearson interval. The Jeffreys prior on each single-budget marginal is a
  modelling choice; a uniform-prior and a no-prior variant are reported alongside.
- **The benchmark compares complete strategies**: the LLM can use semantic labels that the
  numerical baselines ignore (see agent.md, "Information fairness").
- Sensitivity uses linear screening (SRC) and two-level factorials; strongly non-linear
  responses need more points.

## Engineering

- **The SQL sandbox** is defence in depth for a local tool, not a hardened boundary.
- **Runtime identity** includes OS and machine: evidence produced on another platform is
  treated as a different runtime (conservative), and the lock file does not pin OS libraries.
- **Old databases are not migrated**; v0.2 results must be re-run, not converted.
- **Search reports of agent campaigns** attach a verdict only if an eligible estimation of
  the same release exists when they are written, or after a replay-verified compatibility
  check.
