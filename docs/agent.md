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

Ten seeds on Claude Sonnet 5 with a 300-run budget (`results/report_agent_s*.md`,
`results/benchmark.md`). What would be reported, and the one test of "more reliably", were
fixed in [`agent_protocol.md`](agent_protocol.md) and committed before seeds 3–9 ran; it
also records the one deviation (the estimation ran after the seeds instead of before). All
ten seeds submitted a report; none hit its cost cap or the turn limit.

| seed | runs used | turns | cost | finds the collision mode | random at the same runs | grid at the same runs | failing cells (random, grid) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| s0 | 177 | 16 | $0.53 | yes | 0.50 [0.40, 0.60] | 0.41 [0.31, 0.51] | 9 (14.4, 15.4) |
| s1 | 168 | 19 | $0.63 | yes | 0.47 [0.37, 0.57] | 0.40 [0.30, 0.50] | 16 (13.9, 14.8) |
| s2 | 219 | 13 | $0.57 | yes | 0.59 [0.49, 0.69] | 0.47 [0.37, 0.57] | 16 (16.7, 17.6) |
| s3 | 168 | 16 | $0.59 | yes | 0.47 [0.37, 0.57] | 0.40 [0.30, 0.50] | 16 (13.9, 14.8) |
| s4 | 155 | 24 | $0.66 | yes | 0.44 [0.34, 0.54] | 0.37 [0.28, 0.47] | 19 (13.2, 14.1) |
| s5 | 163 | 19 | $0.57 | yes | 0.45 [0.35, 0.55] | 0.39 [0.29, 0.49] | 15 (13.6, 14.6) |
| s6 | 162 | 16 | $0.66 | yes | 0.45 [0.35, 0.55] | 0.39 [0.29, 0.49] | 20 (13.6, 14.6) |
| s7 | 196 | 19 | $0.58 | yes | 0.51 [0.41, 0.61] | 0.44 [0.34, 0.54] | 15 (15.6, 16.4) |
| s8 | 186 | 17 | $0.68 | yes | 0.50 [0.40, 0.60] | 0.42 [0.32, 0.52] | 14 (15.0, 15.9) |
| s9 | 178 | 24 | $0.72 | yes | 0.50 [0.40, 0.60] | 0.41 [0.31, 0.51] | 21 (14.5, 15.5) |

"Random/grid at the same runs" is the share of the 100 campaigns that contain the collision
mode within their first n runs, n being the seed's runs used, with a 95% Clopper–Pearson
interval.

- **The pre-specified test.** The agent found the mode in 10 of 10 seeds (1.00 [0.69,
  1.00]). At the same per-seed budgets, random search would be expected to find it 4.88
  times and grid search 4.10 times. The probability of 10 of 10 is 7.4 × 10⁻⁴ for random and
  1.3 × 10⁻⁴ for grid (Poisson-binomial, treating the baseline shares as known).
- **Breadth.** At matched budgets the agent averages 16.1 distinct failing cells, against
  14.4 (random) and 15.4 (grid). Against the baselines' full 300 runs it finds fewer (20.5
  and 21.1), because it stops early.
- **Speed.** Its first failure comes at run 12.0 ± 16.1, against 8.8 and 9.1, because each
  seed first puts one run in all 108 cells.
- **v0.1 to v0.2.** With three seeds compared at their mean budget, v0.1 reported fewer
  failing cells and called the detection result indicative. Per-seed matching and seven
  more seeds change both.

**Transcripts.** Every tool call of the ten seeds, with its input and output, is in
`results/transcript_agent_s0.json` to `_s9.json`. Outputs are cut at 2,000 characters. The
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

`python -m avval.cli posthoc` re-evaluates every submitted SQL predicate, 24 in all, on the
100,000 estimation runs the agent never saw (`results/posthoc_predicates.md`). Failure means
a collision or a TTC below 1.5 s. Per seed, the condition holding the most AC-01 collisions:

| seed | condition | failure rate inside [95% CI] | lift | AC-01 collisions inside (of 67) | vs. reference box |
| --- | --- | --- | --- | --- | --- |
| s0 | cut-in, headway < 0.45 s, closing ≥ 8 m/s, speed ≥ 22 m/s | 93.9% [87.3, 97.7] | 54.8 | 18 | inside it |
| s1 | cut-in, headway ≤ 0.6 s, closing ≥ 6 m/s | 51.2% [47.3, 55.1] | 34.7 | 62 | overlapping |
| s2 | cut-in, headway ≤ 0.4 s, closing ≥ 6 m/s | 78.0% [72.0, 83.2] | 47.8 | 45 | overlapping |
| s3 | cut-in, headway ≤ 0.3 s, closing ≥ 9 m/s | no runs | – | 0 | empty |
| s4 | cut-in, headway ≤ 0.5 s, closing ≥ 6 m/s | 62.5% [57.8, 66.9] | 40.9 | 55 | overlapping |
| s5 | cut-in, headway < 0.8 s, closing ≥ 6 m/s | 33.7% [30.9, 36.6] | 23.3 | 63 | contains it |
| s6 | cut-in, initial gap ÷ closing speed < 1.5 s | 100% [99.2, 100] | 73.1 | 63 | overlapping |
| s7 | cut-in, headway < 0.5 s, closing ≥ 8 m/s | 87.5% [81.4, 92.2] | 52.5 | 35 | inside it |
| s8 | cut-in, headway ≤ 0.6 s, closing ≥ 7 m/s | 60.4% [55.7, 64.9] | 39.3 | 54 | inside it |
| s9 | cut-in, initial gap ≤ 14.5 m, closing ≥ 9 m/s | no runs | – | 0 | empty |

- **A precision–coverage trade-off across seeds.** The eight usable cut-in conditions run
  from narrow and precise (s0: 94%, 18 collisions) to broad (s5: 34%, all 63 cut-in
  collisions). None holds the 4 lead-braking collisions except s6's third condition,
  `lead_brake AND attentive`, which is so broad (48,011 runs, lift 0.1) that it says nothing.
- **s6's best condition is partly true by definition.** Initial gap ÷ closing speed is the
  TTC at the cut-in, and failure includes a TTC below 1.5 s, so every run inside fails. Its
  coverage, all 63 cut-in collisions, is the informative part.
- **Four conditions hold no held-out runs** (s3 TC-02 and TC-03, s5 TC-02, s9 TC-01). They
  name exact ODD corners, such as a headway of exactly 0.3 s or a closing speed of exactly
  9 m/s, which the agent can run directly but the exposure model never samples. In
  `results/posthoc_predicates.md` they appear with 0 runs inside; the "disjoint" label in
  its comparison table means empty for these four.
- **The second failure mode.** Eleven conditions describe lead braking of about 5 m/s² or
  more with a distracted driver, the failures behind AC-03, with 49–91% of runs inside
  failing.
- **The reference box is not a fair precision target.** It was drawn after the fact around
  the estimation's own collisions, built for coverage (38.7% failure rate, 61 of 67
  collisions). The fair comparison is automatic rule extraction from the agent's own runs:
  the decision-tree baseline on the roadmap.

**Validation status in the agent reports.** Every report was re-rendered with
`scripts/rerender_agent_reports.py` once the estimation for this release existed, from the
stored runs and the agent's logged submission. Seeds 0–2 ran under earlier agent and
reporting code; seeds 3–9 under code that differs from this release only in how
`results/benchmark.md` is formatted. The policy and the parsed configuration are identical
throughout, and no simulation module changed. Each report says it was re-rendered and names
the source hash the agent ran under. The summary, conditions and hypothesis tests are the
agent's own; the re-render changed nothing else apart from row order in a few tables.

## Cost and prompt caching

The ten seeds cost $0.53–0.72 each at list prices, $6.20 together, with 88–94% of input
tokens read from cache. Uncached they would have cost $1.38–2.44 each, $18.37 together
(`results/usage_agent_s*.json`). Not counted: a short smoke test on Claude Haiku and one
Sonnet run that stopped early because its replies hit the output-token limit, which has
since been raised.

Caching uses two breakpoints: an explicit one on the system prompt (caching tools and
prompt) and top-level automatic caching, which moves a breakpoint to the end of the
conversation each turn. Tool outputs are serialised with sorted keys so cached prefixes stay
byte-identical. `--no-cache` measures the difference. Prices are hard-coded in
`avval/agent.py::PRICES`; check them against current list prices.
