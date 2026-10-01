# Known limitations

## What SOTIF requires that this project does not do

- **No hazard analysis and risk evaluation.** No hazard identification, and no severity,
  exposure or controllability assessment. The acceptance criteria are illustrative choices
  written before testing, not derived from one.
- **No justified validation targets.** Thresholds in `acceptance.yaml`, `min_n` = 100 and
  all of `config/exposure.yaml` are placeholders. A real programme would derive the target
  (e.g. fault-free km or hours) from a risk-acceptance argument and field exposure data, and
  size the estimation to it.
- **No perception insufficiencies.** Ground-truth gap, speeds and lead deceleration; no
  sensor model, noise, latency, false or missed detections, or perception triggering
  conditions. In a real ADAS these often dominate.
- **No safety argument for the learned component.** ISO/PAS 8800 expects a training-data
  specification, data-quality management, runtime out-of-distribution monitoring and
  analysis of learned failure modes. This project only measures closed-loop behaviour and
  ties results to the weights hash.

## Modelling

- **Longitudinal only.** Single-lane 1-D; a cut-in simply appears at its headway. The
  driver takes over by braking only; the lead model is simple. The simulator behind
  `simulate()` is designed to be swapped.
- **Driver states change reaction delay only.** No steering, startle, freezing or
  over-braking. Attentive drivers react at the TOR, not at hazard onset, so AC-01 is
  pessimistic.
- **One distracted-driver source** (n = 19, reading task, hazard seen at ≈ 7 s TTC).
- **Reference controller** bounds only responses that start at the hazard; handled by
  counting avoided runs as preventable. The competent-driver reference is disabled.

## Statistical

- **Three agent seeds:** 3/3 has a 95% interval of 0.29–1.00, overlapping both baselines.
  Per-seed budgets differ because the agent chooses when to stop.
- **FAIL uses the point estimate at any n.** Deliberately conservative. At 100,000 runs it
  decides nothing for AC-01 and AC-03, whose whole intervals miss. AC-04's FAIL is narrow
  and depends on the jerk definition.
- **Sensitivity uses 2,000 runs**, one at a time, three points per range; no interactions.

## Engineering

- **The agent has run for real three times**, at one budget, on one model.
- **The agent reports were re-rendered** to attach the release verdict, because the agent
  ran under earlier agent and reporting code (`docs/agent.md`). Re-running the re-render
  needs the results database, which is a local output.
- **The SQL sandbox isn't a security boundary.**
- **Provenance gaps:** sensitivity overrides (`sim_kwargs`) aren't recorded (acceptable only
  because those runs live in throw-away stores); the git commit isn't compared; rows
  migrated from older databases keep NULL in later columns and old metric definitions.
