# Validation of a learned ADAS function with agent-assisted failure discovery

A validation strategy for a learned SAE Level 2 driving function, implemented end to end in
simulation. The function under test is an Adaptive Cruise Control driven by a
behaviour-cloned policy, which asks the driver to take over when it can't cope. The
pipeline has five parts:

- general-purpose driving metrics;
- acceptance criteria fixed before testing, each with explicit evidence requirements;
- coverage-based and agent-driven discovery of SOTIF triggering conditions;
- an exposure-weighted estimation campaign that alone determines the validation status
  (GO, NO-GO or INSUFFICIENT EVIDENCE);
- traceability that ties every result to the release it was computed on.

The LLM agent does one job, failure discovery. It doesn't set criteria, and it doesn't
determine the validation status.

> **Data status:** driver reaction times come from named published studies. Every other
> input (exposure weights, acceptance thresholds, ODD ranges and some driver-response
> parameters) is a placeholder, marked `TODO(data)` in `config/`. The results show the
> method working; they are not real-world risk levels.

![Failure boundary](results/failure_boundary.png)

*Collision probability for lead-vehicle braking at 30 m/s, μ = 0.7. The attentive driver
(left) avoids a collision almost everywhere. The distracted driver at hand-back (right)
collides increasingly often once the lead brakes harder than about 5 m/s², and almost
always below about 1.5 s headway.*

## Summary for release

**Validation recommendation: NO-GO.** Validation supplies the evidence and the
recommendation; the release decision itself is taken across Product, Safety and
Engineering. Three of the four acceptance criteria fail, on 100,000 exposure-weighted runs
with placeholder weights.

- **Further testing of this release won't change the outcome.** AC-01 and AC-03 fail with
  their whole 95% intervals outside the target.
- **The failures point to the function's design more than to the driver assumptions
  tested.**
  - AC-01 and AC-03: braking authority is limited to 3.5 m/s², with no emergency braking,
    so close, fast cut-ins and hard lead braking are left to the driver. Authority and the
    hand-back threshold each move AC-03 by several points, while the attentive driver's
    reaction time barely moves AC-01.
  - AC-04: the policy steps its braking without jerk limiting.
  - Not yet tested: the distracted driver's reaction time, which drives AC-03, comes from a
    single study and was not varied.
- **AC-01 is probably overstated.** In the model, attentive drivers start reacting only
  when the takeover request fires. That assumption should be fixed before AC-01 drives an
  ODD or design decision.

| Criterion | Result (95% interval) | Target | Status |
| --- | --- | --- | --- |
| AC-01 Preventable collisions, attentive driver | 0.084% (0.065–0.106%) | 0 | FAIL |
| AC-02 5th-percentile min. time-to-collision, collision-free runs | 1.89 s (1.88–1.89) | ≥ 1.5 s | PASS |
| AC-03 Preventable collisions after hand-back to a distracted driver | 9.3% (8.4–10.2%) | ≤ 5% | FAIL |
| AC-04 95th-percentile jerk, no hand-back | 5.04 m/s³ (5.03–5.05) | ≤ 5.0 m/s³ | FAIL, on the threshold |

Full report: [`results/report_estimate.md`](results/report_estimate.md). Seeds are fixed:
re-running the estimation under the release code reproduced this report exactly.

## Validation strategy

Five principles shape the pipeline. Each answers a way that validating a learned function
commonly goes wrong. The thread running through them is that **structural coverage and
statistical evidence are different things**: testing every cell of the scenario space says
nothing about how often the function fails in any of them.

1. **Discovery and estimation are separate campaigns.** Discovery should over-sample
   failures. Estimation must sample situations as often as they occur on the road. A
   campaign that does one well gets the other wrong.
   - Discovery campaigns (coverage grid, random, agent) find and evidence triggering
     conditions. They never determine the validation status.
   - The estimation campaign measures rates and alone determines the validation status,
     so the status doesn't depend on how discovery was run.
2. **Evidence requirements are part of each acceptance criterion.** Every criterion fixes
   a population, a confidence interval and a minimum sample size before testing.
   - Without enough evidence, the status is INSUFFICIENT EVIDENCE, never PASS.
   - A zero-failure target can be falsified but never proven. With no failures observed,
     the report states an upper bound on the rate.
3. **Failures are attributed before they're counted.**
   - Each collision is replayed with an ideal controller that brakes as soon as the hazard
     appears. Collisions no system could have avoided are reported separately and don't
     count against the function.
   - Intended use (attentive driver) and foreseeable misuse (distracted driver) have
     separate criteria.
4. **A result holds only for the release it was computed on.** Every campaign records
   hashes of the policy, config and code. If any of them changes, no validation status is
   shown until estimation reruns.
5. **Automated discovery has to be auditable and blind to the answer key.** The agent never
   sees the thresholds, the validation status, other campaigns, the driver-model parameters
   or how the policy was trained. A test checks its prompt for leaked terms.
   - Every claim it makes cites a SQL query over runs it chose itself.
   - Every tool call is logged, and the three agent transcripts are published
     (`results/transcript_agent_s*.json`).

Details: [`docs/evaluation.md`](docs/evaluation.md) and [`docs/system.md`](docs/system.md).

## Findings and recommendations

| # | Finding | Recommendation | Owner |
| --- | --- | --- | --- |
| 1 | **Coverage is not confidence.** Every 300-run grid campaign covers all 108 cells, yet 36% miss the attentive-driver collision mode. One such campaign once reported a false PASS. | Set minimum sample counts within the risky population for every rare-event criterion, in addition to one run per cell. | Validation |
| 2 | **The hand-back monitor has a blind spot.** Its time-to-collision check assumes the lead vehicle keeps its speed. In 822 lead-braking runs, a time-to-collision that accounts for the lead's braking fell below the 2 s threshold, with no hand-back. | Base the hand-back on a time-to-collision that includes braking, or on a brake threat number. Add a criterion on margin loss without hand-back. | Autonomy Eng.; Validation |
| 3 | **The metric definition decides AC-04.** Jerk is 7.32 m/s³ from raw 20 Hz samples and 5.04 m/s³ after smoothing, against a threshold of 5.0. All exceedances are cut-ins. | Fix metric definitions together with thresholds before testing. Add a rate limiter to the policy output. | Validation, Product; Autonomy Eng. |
| 4 | **The design of the function matters more than the attentive driver's reaction time.** Across the tested range (mean 1.0–1.8 s), the attentive driver's reaction time barely moves AC-01. Braking authority and the hand-back threshold each move AC-03 by several points. | Direct effort for AC-03 to braking authority and hand-back timing first. Vary the distracted driver's reaction time before ruling the driver model out. | Autonomy Eng.; Safety |
| 5 | **Attentive-driver collisions are concentrated.** 61 of the 67 sit in close, fast cut-ins, a region with under 1% of runs. There the hand-back arrives as the hazard does, with no emergency braking. | Decide between restricting the ODD, adding AEB, or accepting the residual risk. Fix the attentive-driver timing first (see Summary). | Product, Safety |

Evidence: [`docs/evaluation.md#findings`](docs/evaluation.md#findings). The sensitivity
analysis is in [`docs/evaluation.md#sensitivity`](docs/evaluation.md#sensitivity).

## Agent-driven discovery

The question is whether an LLM agent finds the failure modes that matter more reliably than
coverage-based search with the same number of runs. I compared three agent seeds (Claude
Sonnet 5) with 100 seeds each of random and grid search. Each agent run chose to stop after
188 runs on average, so the baselines are shown at their first 188 runs.

| | Agent (3 seeds) | Random (100) | Grid (100) |
| --- | --- | --- | --- |
| Finds the rare attentive-driver collision mode | 3/3 [0.29, 1.00] | 0.51 [0.41, 0.61] | 0.43 [0.33, 0.53] |
| Distinct failing cells | 13.7 ± 4.0 | 15.2 ± 2.7 | 16.1 ± 2.9 |
| Runs to first failure | 23.0 ± 29.4 | 8.8 ± 8.9 | 9.1 ± 8.9 |
| Cost per campaign (prompt-cached) | $0.53–0.63 | — | — |

**Result.** Every agent seed found the rare collision mode and stated it as a triggering
condition, written as a SQL predicate. Re-tested on 100,000 runs the agent never saw,
failures were 35–62 times more frequent inside its conditions than outside them. The
conditions are precise, with a precision–coverage trade-off across seeds. The cost is
breadth and speed: the agent found slightly fewer distinct failing cells and reached its
first failure later, because each seed covers all 108 cells before it starts probing.

**Confidence.** The evidence is indicative, not conclusive. An agent no better than random
search would still go 3 for 3 about 13% of the time. Its interval also overlaps both
baselines'.

**Recommendation.** Run agent-driven search alongside coverage-based search, not instead of
it. Cost is not the constraint. What would decide the question is a comparison at several
budgets against adaptive baselines: the cross-entropy method and decision-tree rule
extraction.

Details: [`docs/agent.md`](docs/agent.md).

## Scaling to a production programme

This prototype runs both campaigns in one simulator with placeholder inputs. In a
production programme the method stays the same; what changes is where the inputs come
from.

| Input | Here | In a programme | Depends on |
| --- | --- | --- | --- |
| Exposure model | Placeholder weights | Scenario frequencies mined from fleet logs, per ODD segment | Data |
| Acceptance thresholds | Illustrative | Derived from a residual-risk argument and agreed per release | Product, Safety |
| Scenario space | Two longitudinal scenarios | Scenario catalogue spanning simulation, test track and road, with shared metric definitions | Simulation, Evaluation |
| Perception | Ideal | Sensor and perception models, and perception-driven triggering conditions | Simulation |
| Driver response | Published takeover data | Response models per driver state, and benchmarks such as the careful and competent human driver | Human factors, Safety |
| Correlation between simulation and the road | None | On-road replay of discovered triggering conditions to confirm or reject them | Vehicle testing |

## Scope and limits

This covers the verification and validation part of SOTIF (ISO 21448) for one function. It
is not SOTIF compliant, and it is not a safety case. In particular:

- **No hazard analysis.** There's no hazard analysis and risk evaluation behind the
  acceptance targets.
- **Ideal perception.** The controller sees the true state of the road.
- **Longitudinal dynamics only.** There is no AEB and no driver monitoring.
- **No safety argument for the learned component** of the kind ISO/PAS 8800 expects.

Full list: [`docs/limitations.md`](docs/limitations.md).

## Next steps

1. **Close the assumption that dominates AC-01.** Make the attentive driver react when the
   hazard appears rather than at the takeover request, and add a careful and competent human
   driver as a benchmark. This decides whether finding 5 calls for a design change or a
   different reference.
2. **Settle whether agent-assisted discovery earns its place.** Run more seeds at several
   budgets against adaptive baselines.
3. **Bring perception into scope.** Make detection range a triggering-condition parameter,
   and derive a range requirement from the preventability reference.

Full roadmap: [`docs/roadmap.md`](docs/roadmap.md).

## Architecture and usage

```
            ┌───────────── ValidationAgent (LLM, tool use) ─────────────┐
            │ get_system_spec · run_scenarios · query_results (SQL)     │
            │ check_coverage · test_predicate · submit_report           │
            └──────────────┬──────────────────────────┬─────────────────┘
      ODD check + budget   │                          │ read-only, scoped
                           ▼                          ▼
   Campaign ──► Simulator ──► metrics ──► DuckDB `runs` ──► discovery / coverage / report
   (estimate: exposure-weighted sample) ─────────────────────► acceptance + status
                   │
      learned ACC policy + hand-back monitor + driver takeover model
```

```bash
pip install -r requirements.txt
python -m avval.cli train                                    # system under test (~5 s)
python -m avval.cli estimate --n 100000 --seed 0             # validation status (20–40 min)
python -m avval.cli benchmark --method random --seeds 100 --budget 300
python -m avval.cli benchmark --method grid   --seeds 100 --budget 300
ANTHROPIC_API_KEY=... python -m avval.cli agent --budget 300 --first-seed 0 --max-cost-usd 2.5
python -m avval.cli compare random grid agent                # benchmark incl. matched budget
python -m avval.cli posthoc                                  # agent conditions on held-out runs
pytest -q
```

| Doc | Contents |
| --- | --- |
| [`docs/system.md`](docs/system.md) | System definition, scenarios, metrics, preventability, driver model, simulator verification |
| [`docs/evaluation.md`](docs/evaluation.md) | Status rules, provenance, sensitivity, findings, SOTIF mapping, all commands |
| [`docs/agent.md`](docs/agent.md) | Agent tools and information boundary, SQL sandbox, full results, held-out check, cost |
| [`docs/limitations.md`](docs/limitations.md) | Limitations in full |
| [`docs/roadmap.md`](docs/roadmap.md) | Specified, unbuilt work |
| [`docs/traceability.md`](docs/traceability.md) | Validation traceability map: each concept to its implementation |
| [`docs/readme_claims.md`](docs/readme_claims.md) | Every number in the README and docs, with the results file it comes from |

---

**Dr Jan Luca Kästle.** I work on driver-behaviour evaluation and automated-driving
takeover. I was technical lead on an SAE Level 3 takeover research programme (126
drivers, UN R157-based scenarios). The distracted-driver model here uses reaction times
from my own experiments (Kästle et al., 2025, *IEEE Transactions on Haptics*).
[LinkedIn](https://linkedin.com/in/jan-luca-kaestle) ·
[Google Scholar](https://scholar.google.com/citations?user=gDgG4dEAAAAJ)

## License

MIT. See [`LICENSE`](LICENSE).
