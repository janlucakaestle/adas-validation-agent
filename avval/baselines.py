"""Non-LLM search baselines. Every baseline obtains its search domain from
`SearchInterface.domain()` (the public spec in programmatic form) and simulates through
`SearchInterface.run()` (the same visible per-run fields and budget as the agent). No
baseline reads the release configuration directly.

`BASELINE_SPEC` is the single source of every behaviourally relevant setting; the classes
read their values from it, and the frozen benchmark manifest hashes it, so changing any one
of them changes the protocol ID.

Non-adaptive: `random` (uniform over the public ranges) and `grid` (one point per coverage
cell, including driver state, then uniform).
Adaptive (all minimise the robustness score defined in BASELINE_SPEC["robustness"]):
`cem` (cross-entropy method), `evolutionary` (steady-state genetic search), `boundary`
(boundary-seeking bisection and local perturbation) and `bayesopt` (Gaussian-process
regression with expected improvement). The robustness score uses only `collision`,
`end_state` and `min_ttc`; no baseline uses `avoidable_by_reference` or any other derived
label, although they are visible.
"""
from __future__ import annotations

import math

import numpy as np

from .campaign import Campaign
from .evaluation import all_cells, describe_cell
from .report import write_search_report
from .search import SearchInterface

BASELINE_SPEC = {
    "version": "baselines/v4",
    "information": "SearchInterface.domain() and SearchInterface.run() only",
    "robustness": {
        "definition": "0 if collision or end_state = 'horizon_unresolved'; else min(min_ttc, "
                      "cap); a run that never closes (min_ttc NULL) scores cap",
        "cap_s": 10.0, "inputs": ["collision", "end_state", "min_ttc"], "goal": "minimise"},
    "encoding": "per scenario, (ego_speed, headway, scenario parameter, friction) scaled to "
                "[0, 1] by the public ranges; scenario and driver_state categorical",
    "batch_size": 20,
    "random": {"distribution": "scenario and driver_state uniform; parameters uniform over "
                               "the public ranges", "chunk": 100},
    "grid": {"order": "coverage cells shuffled with stream (seed, 0, 'grid-order')",
             "point": "uniform within the cell (stream (seed, cell, 'grid-point'))",
             "then": "random"},
    "init_batches": 2,  # uniform batches before any adaptive proposal
    "cem": {"elite_fraction": 0.2, "smoothing": 0.7, "min_std": 0.05,
            "elite_pool": "all runs so far (score <= elite quantile)",
            "categorical": "smoothed elite frequency of (scenario, driver_state)",
            "continuous": "Gaussian per scenario from elite mean/std, clipped to [0, 1]"},
    "evolutionary": {"tournament": 3, "sigma": 0.1, "p_categorical": 0.1,
                     "crossover": "uniform, within one scenario"},
    "boundary": {"local_sigma": 0.05, "bisect_share": 0.5,
                 "target": "robustness == 0",
                 "bisection": "midpoint to the nearest non-target run of the same scenario "
                              "and driver state, jitter local_sigma / 4"},
    "bayesopt": {"candidates": 2000, "kernel": "Constant(1.0) * Matern(length_scale=0.3 per "
                                               "feature, nu=2.5) + White(0.1)",
                 "length_scale": 0.3, "nu": 2.5, "noise": 0.1, "normalize_y": True,
                 "gp_random_state": 0,
                 "features": "x in [0, 1]^4, is first scenario, is first driver state",
                 "acquisition": "expected improvement below the best observed robustness",
                 "diversity": "greedy by EI; squared feature distance > 0.01 between picks",
                 "ties": "numpy argsort order (stable for equal EI)"},
}


def random_case(rng: np.random.Generator, domain: dict) -> dict:
    """A case drawn uniformly over the public domain."""
    case = {"scenario": str(rng.choice(domain["scenarios"])),
            "driver_state": str(rng.choice(domain["driver_states"]))}
    for k, (lo, hi) in domain["ranges"][case["scenario"]].items():
        case[k] = float(rng.uniform(lo, hi))
    return case


def random_search(campaign: Campaign) -> None:
    iface = SearchInterface(campaign)
    domain = iface.domain()
    chunk = BASELINE_SPEC["random"]["chunk"]
    while iface.remaining > 0:
        start = campaign.used
        n = min(chunk, iface.remaining)
        iface.run([random_case(campaign.case_rng(i), domain) for i in range(start, start + n)])


def coverage_grid(campaign: Campaign) -> None:
    """One random point per public coverage cell (shuffled), then uniform sampling."""
    iface = SearchInterface(campaign)
    odd = iface.domain()["odd"]
    cells = all_cells(odd)
    campaign.case_rng(0, "grid-order").shuffle(cells)
    cases = []
    for j, cell in enumerate(cells):
        rng = campaign.case_rng(j, "grid-point")
        d = describe_cell(cell, odd)
        case = {"scenario": d["scenario"], "driver_state": d["driver_state"]}
        for k, rng_k in d.items():
            if k not in ("scenario", "driver_state"):
                case[k] = float(rng.uniform(*rng_k))
        cases.append(case)
    iface.run(cases)
    random_search(campaign)


# ---------------------------------------------------------------- adaptive searchers
def robustness(row: dict) -> float:
    cap = BASELINE_SPEC["robustness"]["cap_s"]
    if row["collision"] or row["end_state"] == "horizon_unresolved":
        return 0.0
    ttc = row["min_ttc"]
    return cap if ttc is None or not math.isfinite(ttc) else min(ttc, cap)


class _Space:
    """Encode cases as (scenario, driver_state, x in [0, 1]^4) and back, from the domain."""

    def __init__(self, domain: dict):
        self.ranges = domain["ranges"]
        self.scenarios = list(domain["scenarios"])
        self.drivers = list(domain["driver_states"])

    def decode(self, scen: str, drv: str, x) -> dict:
        case = {"scenario": scen, "driver_state": drv}
        for (k, (lo, hi)), xi in zip(self.ranges[scen].items(), np.clip(x, 0.0, 1.0)):
            case[k] = float(lo + xi * (hi - lo))
        return case

    def encode(self, row: dict) -> np.ndarray:
        return np.asarray([(row[k] - lo) / (hi - lo)
                           for k, (lo, hi) in self.ranges[row["scenario"]].items()])

    def uniform(self, rng) -> tuple[str, str, np.ndarray]:
        return (str(rng.choice(self.scenarios)), str(rng.choice(self.drivers)),
                rng.uniform(0, 1, 4))


class AdaptiveSearch:
    """Run loop shared by the adaptive baselines: propose a batch, run it, learn."""
    name = "adaptive"

    def __init__(self, campaign: Campaign):
        self.campaign = campaign
        self.iface = SearchInterface(campaign)
        self.space = _Space(self.iface.domain())
        self.history: list[tuple[str, str, np.ndarray, float, bool]] = []
        self.cfg = BASELINE_SPEC.get(self.name, {})

    def propose(self, rng: np.random.Generator, k: int) -> list[tuple]:
        raise NotImplementedError

    def run(self) -> None:
        it = 0
        while self.iface.remaining > 0:
            k = min(BASELINE_SPEC["batch_size"], self.iface.remaining)
            rng = self.campaign.case_rng(it, self.name)
            props = ([self.space.uniform(rng) for _ in range(k)]
                     if it < BASELINE_SPEC["init_batches"] else self.propose(rng, k))
            rows = self.iface.run([self.space.decode(s, d, x) for s, d, x in props])
            for r in rows:
                score = robustness(r)
                self.history.append((r["scenario"], r["driver_state"], self.space.encode(r),
                                     score, score == 0.0))
            it += 1
            if not rows:
                break


class CrossEntropySearch(AdaptiveSearch):
    name = "cem"

    def propose(self, rng, k):
        c = self.cfg
        scores = np.array([h[3] for h in self.history])
        cut = np.quantile(scores, c["elite_fraction"])
        elite = [h for h in self.history if h[3] <= cut]
        combos = [(s, d) for s in self.space.scenarios for d in self.space.drivers]
        freq = np.array([sum(1 for h in elite if (h[0], h[1]) == cb) for cb in combos], float)
        p = c["smoothing"] * freq / freq.sum() + (1 - c["smoothing"]) / len(combos)
        out = []
        for _ in range(k):
            s, d = combos[rng.choice(len(combos), p=p)]
            xs = np.array([h[2] for h in elite if h[0] == s]) if any(h[0] == s for h in elite) \
                else rng.uniform(0, 1, (2, 4))
            mu, sd = xs.mean(0), np.maximum(xs.std(0), c["min_std"])
            out.append((s, d, np.clip(rng.normal(mu, sd), 0, 1)))
        return out


class EvolutionarySearch(AdaptiveSearch):
    name = "evolutionary"

    def _pick(self, rng):
        idx = rng.choice(len(self.history), size=min(self.cfg["tournament"], len(self.history)),
                         replace=False)
        return min((self.history[i] for i in idx), key=lambda h: h[3])

    def propose(self, rng, k):
        c = self.cfg
        out = []
        for _ in range(k):
            a, b = self._pick(rng), self._pick(rng)
            if b[0] != a[0]:
                b = a
            mask = rng.uniform(size=4) < 0.5
            x = np.where(mask, a[2], b[2]) + rng.normal(0, c["sigma"], 4)
            s, d = a[0], (a[1] if rng.uniform() > c["p_categorical"]
                          else str(rng.choice(self.space.drivers)))
            if rng.uniform() < c["p_categorical"]:
                s = str(rng.choice(self.space.scenarios))
            out.append((s, d, np.clip(x, 0, 1)))
        return out


class BoundarySearch(AdaptiveSearch):
    name = "boundary"

    def propose(self, rng, k):
        sig = self.cfg["local_sigma"]
        every = max(1, int(round(1 / self.cfg["bisect_share"])))
        out = []
        fails = [h for h in self.history if h[4]]
        if not fails:
            return [self.space.uniform(rng) for _ in range(k)]
        for j in range(k):
            f = fails[rng.integers(len(fails))]
            passes = [h for h in self.history if not h[4] and h[0] == f[0] and h[1] == f[1]]
            if passes and j % every == 0:  # bisect towards the nearest non-target run
                near = min(passes, key=lambda h: float(np.sum((h[2] - f[2]) ** 2)))
                x = (f[2] + near[2]) / 2 + rng.normal(0, sig / 4, 4)
            else:  # perturb around a target run
                x = f[2] + rng.normal(0, sig, 4)
            out.append((f[0], f[1], np.clip(x, 0, 1)))
        return out


class BayesOptSearch(AdaptiveSearch):
    name = "bayesopt"

    def _features(self, s, d, x):
        return np.r_[x, float(s == self.space.scenarios[0]), float(d == self.space.drivers[0])]

    def propose(self, rng, k):
        import warnings

        from scipy.stats import norm
        from sklearn.exceptions import ConvergenceWarning
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
        c = self.cfg
        X = np.array([self._features(*h[:3]) for h in self.history])
        y = np.array([h[3] for h in self.history])
        gp = GaussianProcessRegressor(
            ConstantKernel(1.0) * Matern(length_scale=np.full(X.shape[1], c["length_scale"]),
                                         nu=c["nu"]) + WhiteKernel(c["noise"]),
            normalize_y=c["normalize_y"], random_state=c["gp_random_state"])
        with warnings.catch_warnings():  # hyper-parameters at a bound are expected here
            warnings.simplefilter("ignore", ConvergenceWarning)
            gp.fit(X, y)
        cands = [self.space.uniform(rng) for _ in range(c["candidates"])]
        Xc = np.array([self._features(*cd) for cd in cands])
        mu, sd = gp.predict(Xc, return_std=True)
        best = y.min()
        z = (best - mu) / np.maximum(sd, 1e-9)
        ei = (best - mu) * norm.cdf(z) + sd * norm.pdf(z)
        chosen: list[int] = []
        for i in np.argsort(-ei, kind="stable"):
            if all(np.sum((Xc[i] - Xc[j]) ** 2) > 0.01 for j in chosen):
                chosen.append(int(i))
            if len(chosen) == k:
                break
        return [cands[i] for i in chosen]


ADAPTIVE = {c.name: c for c in (CrossEntropySearch, EvolutionarySearch, BoundarySearch,
                                BayesOptSearch)}
STRATEGIES = ("random", "grid", *ADAPTIVE)


def run_strategy(method: str, campaign: Campaign) -> None:
    if method == "random":
        random_search(campaign)
    elif method == "grid":
        coverage_grid(campaign)
    elif method in ADAPTIVE:
        ADAPTIVE[method](campaign).run()
    else:
        raise ValueError(f"unknown strategy {method!r}; available: {list(STRATEGIES)}")
    campaign.finish(stop_reason="budget spent")


def auto_report(campaign: Campaign, method: str) -> str:
    """Search report for a baseline campaign: discovery metrics only, no verdict."""
    summary = (f"A **{method}** baseline search campaign. It reports what it found (discovery "
               "metrics, coverage cells with target runs) but no release verdict: verdicts "
               "come only from a nominal exposure-weighted estimation campaign. No "
               "triggering-condition analysis is performed by the baseline.")
    return str(write_search_report(campaign.store, campaign.name, summary,
                                   author=f"baseline ({method})"))
