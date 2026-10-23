# Evaluation: campaigns, acceptance, statistics and provenance

**Terminology.** The validation status (GO, NO-GO, INSUFFICIENT EVIDENCE) is a
recommendation to a release decision taken across Product, Safety and Engineering. The code
calls it the `verdict`. All results are conditional on the simulator, ODD, exposure model,
driver model, controller and release manifest they were computed under.

This page describes the method; the final v1.0 results are in [`results/`](../results/).

## Search vs. estimation

- **Search campaigns** (`random`, `grid`, `cem`, `evolutionary`, `boundary`, `bayesopt`,
  the agent) choose where to look; they report discovery metrics and coverage, never a
  status.
- **The nominal estimation campaign** samples from the exposure model. It is the only
  source of acceptance results, and only if it is *eligible* (`avval/estimation.py`):
  kind `nominal_estimation`, no overrides, status COMPLETE with every planned run stored,
  recorded under the current release ID and runtime ID, and a data hash that still matches.

## Acceptance criteria (`config/acceptance.yaml`)

| ID | Population (scenario columns only) | Event / metric | Target | Requirement status |
| --- | --- | --- | --- | --- |
| AC-01 | attentive driver, avoidable by the ideal reference | collision or unresolved | ≤ 1e-4, zero goal | illustrative (+ ideal reference: illustrative) |
| AC-02 | all runs; strata by scenario | 5th percentile of effective TTC (collision/unresolved = 0 s, never-closing = ∞) | ≥ 1.5 s | illustrative |
| AC-03 | foreseeable misuse, avoidable by the ideal reference; **strata by `handback_required`** | collision or unresolved | ≤ 5% | illustrative (+ ideal: illustrative, oracle: provisional) |
| AC-04 | all runs; strata by scenario | 95th percentile of automated-control jerk (too-short interval = ∞) | ≤ 5 m/s³ | illustrative |
| AC-07 | hand-back required | no TOR, or TOR later than `max_tor_latency_s` (0.5 s, a named parameter) after onset | ≤ 1% | illustrative (+ oracle: provisional) |
| AC-08 | hand-back not required | TOR issued | ≤ 25% | illustrative (+ oracle: provisional) |
| AC-09 | attentive driver, **all** scenarios | collision or unresolved | none defined | undefined |
| AC-10 | foreseeable misuse, **all** scenarios | collision or unresolved | none defined | undefined |
| AC-06, AC-02-S, AC-03-C | — | descriptive (INFO); AC-02-S/AC-03-C are conditional on system outputs and labelled so | — | — |

**Requirement maturity.** Every gating criterion has `requirement_status` (approved,
provisional, illustrative, undefined). Its effective status is the weakest of its own and of
the reference definitions its population uses. Reports show three layers: the statistical
result (estimate and one-sided bound), the engineering comparison with the target (PASS,
FAIL, INSUFFICIENT EVIDENCE, NO REQUIREMENT), and whether it can support a formal GO. The
verdict is NO-GO on any FAIL (even against an illustrative target), INSUFFICIENT EVIDENCE if
anything is insufficient, DECISION PENDING REQUIREMENTS unless every gating criterion PASSes
against an approved requirement, and GO only then; the formal decision additionally needs a
final-evidence campaign. With the shipped configuration a formal GO is impossible.

**AC-03 and the distracted-collision gap.** AC-03 counts every distracted-driver collision in
a scenario the ideal reference avoids, whether or not a hand-back is required (stratified by
it, each stratum must pass). Previously a collision with `handback_required = false` (the
policy mishandling a scenario its authority could handle) fell out of every gating
criterion. AC-09/AC-10 gate collisions irrespective of the reference, because "not avoided
by the reference" is not physical impossibility; their targets are not derived yet, so they
report statistics and keep a formal GO unavailable. In the v1.0 estimation AC-03 and AC-10
report the same value (1.88%, bound 2.04%) because their populations coincide (n = 20,031
each): the reference fails to avoid only 3 of 100,000 runs (AC-06), and all 3 are
attentive-driver runs (AC-09 has 3 more runs than AC-01), so no distracted run is excluded
from AC-03.

**Why these populations.** v0.2 conditioned on system outputs: AC-03 on `tor_issued` (a
system that suppressed TORs removed runs from its own denominator), AC-04 on `NOT
tor_issued` (more TORs removed uncomfortable runs), AC-02 on `NOT collision` (a near miss
that became a collision left the TTC population). Now `check_acceptance` refuses any gating
population or stratum that uses a system-output column. The monotonicity tests in
`tests/test_acceptance.py` check that suppressing TORs cannot improve AC-03, more TORs
cannot shrink AC-04's population (and are bounded by AC-08), turning near misses into
collisions never improves AC-02, and making a distracted run collide never removes it from
AC-03/AC-10, whatever `handback_required` is.

## Statistical method (`avval/evaluation.py`)

- **Rates:** exact one-sided Clopper–Pearson bounds at the configured confidence (0.95).
  The two-sided interval is used only for descriptive statistics (benchmark, predicates).
- **Quantiles:** exact distribution-free order-statistic bounds: the lower bound of the
  q-quantile is X₍ᵣ₎ with the largest r such that P(Bin(n,q) ≥ r) ≥ 0.95. Coverage ≥ 95% for
  every n and continuous distribution (conservative with ties), checked by simulation in
  the tests. Below the minimum n (59 for q = 0.05 or 0.95) no bound exists and the
  criterion cannot pass. v0.2 used a percentile bootstrap, whose coverage near small n in
  the tails is not guaranteed.
- **Statuses:** PASS needs n ≥ `min_n` and the one-sided bound to meet the target in the
  population and in every stratum (a stratum without data is INSUFFICIENT). FAIL: the point
  estimate violates the target (any n), or a zero goal is falsified; the report says whether
  the exceedance is also demonstrated by the opposite one-sided bound. Otherwise
  INSUFFICIENT EVIDENCE. Each criterion reports the smallest n at which a PASS is possible.
- **Zero targets:** a gating rate threshold must be positive. `zero_goal: true` adds the
  aspiration: one observed event fails the criterion permanently (more event-free runs
  cannot erase it); with no events, PASS still needs the bound below the positive tolerable
  rate. v0.2 counted "no failures observed" as passing.
- **Verdict** (`overall_verdict`, see "Requirement maturity"): NO-GO if any gating
  criterion FAILs, even against an illustrative target; otherwise INSUFFICIENT EVIDENCE if
  any is insufficient; otherwise DECISION PENDING REQUIREMENTS if any gating criterion has
  no target or a requirement that is not approved; GO only if every gating criterion PASSes
  against an approved requirement.
- **Wording:** a demonstrated FAIL is reported as "existing evidence is already sufficient
  for this criterion under the current simulator, models and rules; additional IID sampling
  of the unchanged release is unlikely to reverse it", not as "more testing won't change
  the outcome".

## Provenance, release identity and lifecycle

- **Release** (`avval/config.py`): frozen parsed configs (odd, driver, reference, exposure,
  acceptance, sim), policy SHA-256 and code SHA-256 over `avval/*.py`. `release_id` hashes
  exactly these objects; `with_overrides` builds a variant with its own ID and records the
  overrides. Configs are immutable (`MappingProxyType`), so in-memory config cannot diverge
  from what is attested.
- **Runtime** (`avval/provenance.py`): Python, OS, machine and the versions of numpy, scipy,
  pandas, pyarrow, duckdb, PyYAML, scikit-learn (the Bayesian-optimisation baseline uses it to
  choose runs) and anthropic (agent traffic), all hashed into `runtime_id`; matplotlib only
  renders figures and is recorded, not hashed. Agent usage files record the model IDs the API
  actually returned. `requirements-lock.txt` pins the environment;
  `python -m avval.cli env-check` compares. Reproducing **simulation** needs only
  `results/policy.json`; reproducing **training** needs the recorded recipe and library
  versions (`results/policy_meta.json`) and is not guaranteed bit-identical across versions.
- **Campaign lifecycle** (`campaigns` table): unique ID; kind; planned/completed runs;
  status CREATED → RUNNING → COMPLETE (or FAILED); release, runtime, exposure-model and
  protocol IDs; overrides; data hash on completion. `(campaign, run_idx)` is a primary key.
  Random streams come from `derive_seed(campaign_seed, run_idx, purpose)`, so resuming
  (`estimate --resume`) reproduces an uninterrupted campaign exactly.
- **Schema** (`avval/store.py`): schema and metric-semantics versions, column names, types
  and key constraints are checked when a database opens. The v0.2 database is refused; it
  stays a read-only archive.
- **Compatibility** (`avval/compat.py`): evidence from another release is combined only if a
  replay of every run under the target release reproduces every stored column. Findings,
  diagnostics, hold-out freezing and the clusters script refuse campaigns that are not
  COMPLETE under the current release and runtime with intact data.
- **Final evidence** (`--final`): a clean, committed tree (tracked changes outside results/
  and untracked code/config/scripts/requirements are refused), a valid commit and the
  locked environment; outputs go to `results/final_<release-id prefix>/` (a `RELEASE_ID`
  marker binds the directory to the release). Campaigns record `evidence_mode`; only `final`
  campaigns are release, confirmatory or package evidence. Development runs may be dirty
  and are labelled as such everywhere.
- **Evidence package** (`python -m avval.cli --final package`): selected by manifests and IDs:
  release manifest, configs, source, policy and metadata, runtime and lock; the estimation
  (records, Parquet runs, acceptance JSON, report); the frozen benchmark (manifest, all
  protocol campaigns, agent bundles, transcripts and usage, analysis JSON, report, figure);
  the frozen hold-out (predicate set, protocol, campaign, results); the frozen sensitivity
  study (manifest, every variant campaign, CSV/MD/figure); findings, diagnostics and the
  characterisation data. Every campaign must match the release and runtime; every artifact
  must carry the ID it belongs to. `verify-package` re-hashes files, recomputes the release
  and code hashes from the packaged source, reloads every campaign, recomputes acceptance,
  benchmark completeness and analysis, every evidence bundle on the packaged rows, hold-out
  scores and sensitivity statuses.

## Exposure and coverage

- `config/exposure.yaml` is a factor graph; the shipped model is **factorized** (independent
  factors except the scenario-dependent ones) with placeholder weights. Conditional factors
  (`given`) are supported without code changes. Validation: finite, non-negative weights
  summing to 1; strictly increasing bins spanning the **full** ODD range; every categorical
  value listed. Unvisited regions must be declared with weight 0 and are reported as
  zero-exposure subregions.
- Coverage cells are scenario × **driver state** × binned continuous parameters (216 cells);
  dropping a dimension requires a rationale and the report then says the coverage is not
  complete ODD coverage.

## Sensitivity (`config/sensitivity.yaml`)

Sixteen factors: attentive and distracted reaction-time mean and SD, brake onset delay,
brake demand, peak deceleration, brake jerk, **standstill brake hold**, distracted share of
exposure, both TOR thresholds, **monitor detection delay**, **actuator delay**, **required-
deceleration margin**, ACC authority. Excluded with reasons in the config: the hand-back
oracle capability and the ideal reference level (evaluation definitions, not system or world
properties; their immaturity is carried by requirement status), dt and horizon (numerical,
covered by convergence tests and the unresolved terminal state), exposure correlations and
speed-dependent reaction times (not parameterised). Designs: one-at-a-time (41 variants), a
2⁶ factorial (65; main effects and two-way interactions) and a 64-point Latin hypercube (65;
standardised regression coefficients with R²). Delay factors are snapped to the step grid.
`sensitivity-freeze` writes a manifest with the config, the concrete variant list of all
three designs, release, runtime and analysis version; every variant campaign and output file
records its protocol ID, and in the final study every variant's runs are persisted in the
results database (so the package can recompute every reported status). ACC authority above
the training authority uses a policy re-trained for it (`authority_mode: retrain`); the
hand-back population no longer moves with authority.

## Held-out evaluation of triggering conditions

Predicates (from verified evidence bundles, plus reference boxes derived from discovery data)
are frozen with a hash (`freeze-predicates`). The execution is then frozen too
(`holdout-freeze --n 100000 --seed 4242`): predicate-set hash, release, runtime, exposure
model, seed, planned size, region, target, analysis version and the exposure-mass
Monte-Carlo settings, hashed into the hold-out protocol ID. `holdout-run` takes seed and size
only from that file; `holdout-report` refuses any campaign, release or runtime that differs
from it. Exploratory hold-outs are a separate kind (`holdout-explore`) and are never scored as
the frozen one. Each condition is classified as an exact-point description, unsupported
(zero exposure measure), neighbourhood (measure < 0.1%) or exposure-supported. In v0.2 the
reference box was derived from and evaluated on the same estimation campaign.

## Commands

Development (dirty tree allowed; never evidence):

```bash
python -m avval.cli env-check
python -m avval.cli estimate --n 2000 --seed 0
python -m avval.cli baseline --method cem --budget 300 --seed 0
python -m avval.cli sensitivity --design oat --exploratory --n 200
python -m avval.cli holdout-explore --n 1000 --seed 99
pytest -q
```

Final evidence: every campaign command takes `--final`, from a clean, committed tree, in this
order: `release`; `characterise`; `estimate --n 100000 --seed 0`; `benchmark-freeze`,
`benchmark-run --strategy <s>` for each baseline, `agent --first-seed 0 --seeds 10`,
`benchmark-report`; `sensitivity-freeze`, `sensitivity --design oat|factorial2|lhs`;
`reference-boxes estimate`, `freeze-predicates --from-benchmark`,
`holdout-freeze --n 100000 --seed 4242`, `holdout-run`, `holdout-report`;
`diagnose estimate`, `findings --estimation estimate --from-benchmark`, `report estimate`;
`package`, then `verify-package results/final_<id>/package` (without `--final`).

`results/ac01_clusters.md` (the AC-01 event boxes) is written by
`python -m avval.cli --final reference-boxes estimate`; the same file can be regenerated
from an existing store with `PYTHONPATH=. python scripts/ac01_clusters.py estimate`.
