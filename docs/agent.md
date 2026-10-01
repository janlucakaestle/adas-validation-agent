# The validation agent

## Tools and constraints

The agent never touches the simulator or database directly. Every tool validates its
inputs: out-of-ODD cases are rejected with a reason, and the run budget is enforced.

| Tool | Gives the agent |
| --- | --- |
| `get_system_spec` | ODD parameters and ranges, the two driver-state definitions, the failure predicate, the coverage definition, remaining budget |
| `run_scenarios` | The outcome of each case it runs |
| `query_results`, `check_coverage` | Its own campaign's rows only |
| `test_predicate` | How strongly a SQL `WHERE` clause concentrates failures in its own runs: rates inside/outside, lift, 95% interval. Every call is logged and listed in the report. |
| `submit_report` | Triggering conditions, each evidenced by SQL |

The system prompt describes the function, the job (find and evidence triggering conditions)
and a general method: cover the ODD, form hypotheses, probe boundaries, repeat seeds where
driver behaviour is stochastic, cite a query for every claim.

## What the agent is not told

The acceptance criteria and thresholds; the validation status or any estimation, benchmark or
other campaign's results; the driver-model parameters; the preventability reference; how
the policy was built. A test checks the prompt, tool descriptions and spec for
banned phrases including "training", "fault", "ground truth", "weak", "estimation" and
"threshold". The validation status is attached to its report by code, after submission.

## SQL sandbox

Two layers (`avval/store.py::Store.query`):

- A filter accepts only a single `SELECT`/`WITH` statement without write keywords.
- The statement runs in a fresh in-memory DuckDB connection whose only table is a read-only
  view, `runs`, over a snapshot of the campaign's rows. It has no handle on the results
  database, external access disabled (no ATTACH, COPY or file reads), locked configuration,
  a memory cap, a 10 s timeout and a bounded row count.

The tests bypass the filter and try to write and to read other campaigns. **This is defence
in depth for a local, trusted tool, not a security boundary.**

## Results

Three seeds on Claude Sonnet 5, 300-run budget (`results/report_agent_s*.md`). Each seed
submitted early, after 177, 168 and 219 runs (mean 188), so baselines are also shown cut to
their first 188 runs. Intervals are 95% Clopper–Pearson over seeds.

| | agent (3 seeds) | random (100 seeds) | grid (100 seeds) |
| --- | --- | --- | --- |
| P(finds a preventable attentive collision), 300 runs | 3/3 = 1.00 [0.29, 1.00] | 0.67 [0.57, 0.76] | 0.64 [0.54, 0.73] |
| same, first 188 runs | (as above) | 0.51 [0.41, 0.61] | 0.43 [0.33, 0.53] |
| distinct failing cells, 300 runs | 13.7 ± 4.0 | 20.5 ± 2.5 | 21.1 ± 2.8 |
| distinct failing cells, first 188 runs | (as above) | 15.2 ± 2.7 | 16.1 ± 2.9 |
| runs to first failure | 23.0 ± 29.4 | 8.8 ± 8.9 | 9.1 ± 8.9 |

**Trade-off.** Every seed found the rare attentive pocket and described it as a triggering
condition. The agent finds fewer cells and reaches its first failure later, because each
seed first puts one run in all 108 cells before probing. Against the baselines' first 188
runs the cell gap is small.

**Why preliminary.** The agent's interval overlaps both baselines'. If it were no better
than random at 188 runs, all three seeds would still find the pocket about 13% of the time
(0.51³). The matched comparison cuts baselines at the agent's mean, not per seed.

**Transcripts.** Every tool call of the three seeds, with its input and output, is in
`results/transcript_agent_s0.json` to `_s2.json`. Outputs are cut at 2,000 characters. The
only edit: the report path in each `submit_report` result is shortened from the local
absolute path to `results/report_agent_s<k>.md`.

## How a run unfolds: seed 0

From `results/transcript_agent_s0.json`:

- **Coverage first.** The agent read the system spec and the coverage definition, then spent
  108 runs putting one attentive-driver case in the centre of every coverage cell, in three
  batches. The lead-braking cells showed nothing; the cut-in sweep produced the first
  failures, at 0.58 s headway and 7.25 m/s closing speed.
- **Narrowing.** It tested the predicate `cut_in AND headway < 0.7 AND closing_speed > 6`,
  repeated runs at the ODD corners (0.3 s headway closing at 9 m/s; 0.8 s headway with
  9 m/s² lead braking) for both driver states, and used the `preventable` flag to separate
  physics-limited cut-ins from function failures. It then tightened the cut-in condition to
  headway < 0.45 s and closing speed ≥ 8 m/s (preventable from 22 m/s), and compared
  attentive with distracted drivers in hard lead braking.
- **Submission,** after 177 of 300 runs: TC-01, the close, fast cut-in, which fails largely
  regardless of driver state or friction; TC-02, lead braking above 5 m/s² at headway below
  1.6 s with a distracted driver (81% failures against 0% for an attentive one). Each
  predicate was tested once before submission. It left 123 runs unused and didn't look for
  the four rare attentive lead-braking collisions the estimation found.

## Held-out check of submitted conditions

`python -m avval.cli posthoc` re-evaluates each submitted SQL predicate on the 100,000
estimation runs the agent never saw (`results/posthoc_predicates.md`). Failure = collision
or TTC < 1.5 s.

| seed | condition | failure rate inside [95% CI] | lift | AC-01 collisions inside (of 67) | vs. reference box |
| --- | --- | --- | --- | --- | --- |
| s0 | cut-in, headway < 0.45 s, closing ≥ 8 m/s, speed ≥ 22 m/s | 93.9% [87.3, 97.7] | 54.8 | 18 | entirely inside, covers 26% of its failures |
| s1 | cut-in, headway ≤ 0.6 s, closing ≥ 6 m/s | 51.2% [47.3, 55.1] | 34.7 | 62 | 97% inside, covers 93% |
| s2 | cut-in, headway ≤ 0.4 s, closing ≥ 6 m/s | 78.0% [72.0, 83.2] | 47.8 | 45 | 97% inside, covers 48% |
| s0 | lead braking > 5 m/s², headway < 1.6 s, distracted | 80.5% [76.4, 84.1] | 54.8 | 0 | disjoint: second failure mode |
| s1, s2 | lead braking ≥ 5 m/s², distracted | 52.6% [50.3, 54.9] | 62.4 | 0 | disjoint: second failure mode |

The conditions are precise, with a precision–coverage trade-off across seeds; none holds
more than 62 of the 67 AC-01 collisions. The reference box was drawn after the fact from the
estimation itself, built for coverage (38.7% failure rate, 61 of 67 collisions), so it isn't
a fair precision target. The fair comparison is automatic rule extraction from the same runs
(a decision-tree baseline, on the roadmap). The lead-braking conditions describe the
distracted-driver failures behind AC-03; s1's and s2's contain 54% of all failing runs.

**Validation status in the agent reports.** The agents ran before the final code, so their
reports, written at submission, found no estimation matching the release. The changes since
were to the agent loop, reporting and tooling. The policy and the parsed configuration are
identical, and no simulation module changed. `scripts/rerender_agent_reports.py` re-renders
each report from the stored runs and the agent's logged submission and attaches the release
verdict. Each report says so, and names the source hash the agent ran under. The summary,
conditions and hypothesis tests are the agent's own; the re-render left every other section
unchanged apart from row order in two tables.

## Cost and prompt caching

The seeds cost $0.53, $0.63 and $0.57 at list prices, with 88–92% of input tokens read from
cache; uncached they'd have cost $1.38, $1.90 and $1.41 (`results/usage_agent_s*.json`).
Not counted: a short smoke test on Claude Haiku and one Sonnet run that stopped early because
its replies hit the output-token limit, which has since been raised.

Caching uses two breakpoints: an explicit one on the system prompt (caching tools and
prompt) and top-level automatic caching, which moves a breakpoint to the end of the
conversation each turn. Tool outputs are serialised with sorted keys so cached prefixes stay
byte-identical. `--no-cache` measures the difference. Prices are hard-coded in
`avval/agent.py::PRICES`; check them against current list prices.
