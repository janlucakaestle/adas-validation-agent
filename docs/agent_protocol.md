# Agent evaluation protocol for v0.2 (fixed before running seeds 3–9)

> **Historical document (v0.2), with its actual chronology.** This protocol was written and
> committed on 2026-10-01, **after** agent seeds 0–2 had already run under earlier agent and
> reporting code. It was prospective only for seeds 3–9; the ten-seed result as a whole was
> **not** fully prospectively pre-registered. The estimation also ran after the seeds
> (deviation 1 below). The v0.2 results are withdrawn. Future
> benchmark runs use the machine-readable frozen protocol (`config/benchmark.yaml`, frozen by
> `python -m avval.cli benchmark-freeze` into `results/benchmark_manifest.json`, whose hash
> every benchmark campaign records).

Written and committed on 2026-10-01, before any of seeds 3–9 was run. The analysis code it
refers to (`avval/benchmark.py::matched_per_seed`, `python -m avval.cli posthoc`) was
committed at the same time. Nothing below was changed after the results came in; any
deviation is listed under "Deviations" at the end, with its reason.

## Runs

- Seeds 3 to 9 of the agent, on Claude Sonnet 5 (`claude-sonnet-5`), with a 300-run budget
  and at most 40 turns, run one at a time. The agent's prompt, tools and loop are the same as
  for seeds 1 and 2. Seed 0 ran before the output-token limit was raised from 4,096 to
  16,000; that is the only difference.
- Spend: the recorded cost of seeds 3–9 together must stay under $5.00. Each seed gets a
  cost cap of min($1.00, $5.00 − spent so far − $0.15). If that cap would be below $0.40, no
  further seed is started.
- Before the seeds run, the 100,000-run estimation is re-run under the same code, so each
  new report carries the release verdict when it is written.
- A seed that fails for an infrastructure reason before it has made any runs (an API error,
  a crash in this code) is fixed and retried once, and the failure is reported. A seed that
  ends on its own (it stops calling tools, reaches 40 turns, or hits its cost cap) is
  reported as it ended and is not re-run. No seed is re-run because of its result.

## What is reported, for all 10 seeds

Seeds 0 to 9, whatever their result:

1. **Per seed:** whether the campaign contains a preventable collision with an attentive
   driver (region `attentive_preventable_collision` in `avval/benchmark.py`), runs used,
   turns, recorded cost, and how the run ended.
2. **Detection across seeds:** the number of seeds that found it, with a 95%
   Clopper–Pearson interval.
3. **Matched budget, per seed:** for each seed that used n runs, the share of the 100 random
   and the 100 grid campaigns that contain the region within their first n runs, with
   Clopper–Pearson intervals, and their mean number of distinct failing cells at n.
4. **The pre-specified comparison:** for each baseline, the number of detections expected
   at the seeds' own budgets (the sum of the per-seed shares), and the probability that the
   baseline would detect the region in at least as many seeds as the agent did
   (Poisson-binomial, treating the baseline shares as known). This is the only test of
   "the agent finds it more reliably". Nothing else will be presented as evidence for it.
5. **Post-hoc check:** every predicate submitted by any of the 10 seeds, re-evaluated on
   the held-out 100,000 estimation runs (`python -m avval.cli posthoc`). Seeds that submit
   nothing are listed.

Distinct failing cells and runs to first failure are reported alongside, as in v0.1.

## Deviations

1. **Order of the estimation and the seeds** (recorded 2026-10-01, before any of seeds 3–9
   ran). The estimation re-run was stopped twice by the host when the machine ran low on
   memory. The seeds run first instead, and the estimation afterwards. This doesn't change
   any result: the agent never sees the estimation (its SQL sandbox holds only its own
   runs), and the estimation is deterministic, so its runs are the same whenever it is
   made. The only effect is that the seeds' reports are written without the release
   verdict and are re-rendered with it afterwards (`scripts/rerender_agent_reports.py`),
   as seeds 0–2 are.
