"""Exposure model: the distribution of situations inside the ODD used for estimation.

The model is a factor graph (config/exposure.yaml): factors are sampled in order, each from
its own distribution or, with `given`, from one distribution per combination of earlier
categorical factors. The shipped model is factorized (independent factors apart from the
scenario-dependent ones) with placeholder weights. That is an assumption, stated in every
report: all exposure-weighted numbers are conditional on it.

Validation is fail-closed: weights must be finite, non-negative and sum to 1; bins must be
strictly increasing and span the full ODD range; every categorical ODD value must be listed.
Regions that real driving does not visit must be declared with weight 0 and are reported
as zero-exposure subregions; they are never dropped from the ODD silently.
"""
from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

from .config import CATEGORICAL, CONTINUOUS, SCENARIO_PARAMS, param_range
from .frozen import thaw

FACTORS = (*CATEGORICAL, *CONTINUOUS, *SCENARIO_PARAMS.values())
NA = "not_applicable"
_SUM_TOL = 1e-9


def _check_weights(name: str, weights) -> None:
    w = list(weights)
    if not w or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in w):
        raise ValueError(f"exposure.yaml: {name}: weights must be finite numbers")
    if any(x < 0 for x in w):
        raise ValueError(f"exposure.yaml: {name}: weights must be non-negative")
    if abs(sum(w) - 1.0) > _SUM_TOL:
        raise ValueError(f"exposure.yaml: {name}: weights sum to {sum(w)!r}, not 1")


class ExposureModel:
    """Validated, sampleable exposure model built from a frozen exposure config and ODD."""

    def __init__(self, cfg, odd):
        self.cfg, self.odd = cfg, odd
        self.factors = dict(cfg["factors"])
        self.meta = dict(cfg["model"])
        self._validate()

    # ------------------------------------------------------------ validation
    def _validate(self) -> None:
        params = self.odd["parameters"]
        if set(self.factors) != set(FACTORS):
            raise ValueError(f"exposure.yaml: factors must be exactly {sorted(FACTORS)}; "
                             f"got {sorted(self.factors)}")
        for k in ("label", "structure", "status", "assumption"):
            if not self.meta.get(k):
                raise ValueError(f"exposure.yaml: model.{k} must be set (state the "
                                 "structure and status of the exposure model explicitly)")
        seen: list[str] = []
        for name, f in self.factors.items():
            parents = list(f.get("given", []))
            for par in parents:
                if par not in seen or par not in CATEGORICAL:
                    raise ValueError(f"exposure.yaml: {name}: parent {par!r} must be an "
                                     "earlier categorical factor")
            if f["type"] == "categorical":
                if name not in CATEGORICAL:
                    raise ValueError(f"exposure.yaml: {name} must be a histogram")
                for key, dist in self._tables(name, f):
                    w = dict(dist["weights"] if "weights" in dist else dist)
                    if set(w) != set(params[name]["values"]):
                        raise ValueError(f"exposure.yaml: {name}{key}: weights must cover "
                                         f"exactly the ODD values {list(params[name]['values'])}")
                    _check_weights(f"{name}{key}", w.values())
            elif f["type"] == "histogram":
                if name in CATEGORICAL:
                    raise ValueError(f"exposure.yaml: {name} must be categorical")
                per_scenario = "ranges" in params[name] or name in SCENARIO_PARAMS.values()
                if per_scenario and "scenario" not in parents:
                    raise ValueError(f"exposure.yaml: {name} depends on the scenario and must "
                                     "be `given: [scenario]`")
                for key, dist in self._tables(name, f):
                    scen = self._scenario_of(parents, key)
                    applicable = (name not in SCENARIO_PARAMS.values()
                                  or SCENARIO_PARAMS[scen] == name)
                    if dist == NA:
                        if applicable:
                            raise ValueError(f"exposure.yaml: {name}{key} is required for "
                                             f"scenario {scen!r}")
                        continue
                    if not applicable:
                        raise ValueError(f"exposure.yaml: {name}{key} must be "
                                         f"'{NA}' (it does not apply to {scen!r})")
                    self._check_hist(f"{name}{key}", dist, *param_range(name, scen, self.odd))
            else:
                raise ValueError(f"exposure.yaml: {name}: unknown type {f['type']!r}")
            seen.append(name)

    @staticmethod
    def _check_hist(name: str, h, lo: float, hi: float) -> None:
        bins, weights = list(h["bins"]), list(h["weights"])
        if not all(isinstance(b, (int, float)) and math.isfinite(b) for b in bins):
            raise ValueError(f"exposure.yaml: {name}: bins must be finite numbers")
        if any(b <= a for a, b in zip(bins, bins[1:])):
            raise ValueError(f"exposure.yaml: {name}: bins must be strictly increasing")
        if len(weights) != len(bins) - 1:
            raise ValueError(f"exposure.yaml: {name}: needs one weight per bin")
        if abs(bins[0] - lo) > 1e-9 or abs(bins[-1] - hi) > 1e-9:
            raise ValueError(f"exposure.yaml: {name}: bins span [{bins[0]}, {bins[-1]}] but the "
                             f"ODD range is [{lo}, {hi}]. The histogram must cover the full ODD; "
                             "declare unvisited regions explicitly as bins with weight 0")
        _check_weights(name, weights)

    def _parent_values(self, parents):
        params = self.odd["parameters"]
        return [list(params[p]["values"]) for p in parents]

    def _tables(self, name, f):
        """(label, distribution) for every parent combination (one entry if unconditioned)."""
        parents = list(f.get("given", []))
        if not parents:
            yield "", f
            return
        table = f["table"]
        combos = ["|".join(c) for c in itertools.product(*self._parent_values(parents))]
        if set(table) != set(combos):
            raise ValueError(f"exposure.yaml: {name}: table keys must be exactly {combos}")
        for key in combos:
            yield f"[{key}]", table[key]

    @staticmethod
    def _scenario_of(parents, key: str) -> str:
        if "scenario" not in parents:
            return "lead_brake"  # shared range: identical for every scenario
        return key.strip("[]").split("|")[parents.index("scenario")]

    def _dist(self, name: str, case: dict):
        f = self.factors[name]
        parents = list(f.get("given", []))
        if not parents:
            return f
        return f["table"]["|".join(case[p] for p in parents)]

    # ------------------------------------------------------------ sampling
    def sample(self, rng: np.random.Generator) -> dict:
        """One case drawn from the exposure distribution (factors in config order)."""
        case: dict = {}
        for name, f in self.factors.items():
            dist = self._dist(name, case)
            if f["type"] == "categorical":
                w = dict(dist["weights"])
                case[name] = str(rng.choice(list(w), p=list(w.values())))
            elif dist == NA:
                case[name] = None
            else:
                i = rng.choice(len(dist["weights"]), p=list(dist["weights"]))
                case[name] = float(rng.uniform(dist["bins"][i], dist["bins"][i + 1]))
        return {k: v for k, v in case.items() if v is not None}

    def sample_frame(self, n: int, rng: np.random.Generator) -> pd.DataFrame:
        """n cases as a DataFrame of scenario inputs (vectorised; for measure estimates)."""
        out: dict[str, np.ndarray] = {}
        for name, f in self.factors.items():
            parents = list(f.get("given", []))
            col = np.full(n, None, dtype=object) if f["type"] == "categorical" \
                else np.full(n, np.nan)
            groups = ([((), np.ones(n, bool))] if not parents else
                      [(combo, np.logical_and.reduce([out[p] == v for p, v in zip(parents, combo)]))
                       for combo in itertools.product(*self._parent_values(parents))])
            for combo, mask in groups:
                m = int(mask.sum())
                if not m:
                    continue
                dist = f if not parents else f["table"]["|".join(combo)]
                if f["type"] == "categorical":
                    w = dict(dist["weights"])
                    col[mask] = rng.choice(list(w), size=m, p=list(w.values()))
                elif dist != NA:
                    w = list(dist["weights"])
                    i = rng.choice(len(w), size=m, p=w)
                    b = np.asarray(dist["bins"], float)
                    col[mask] = rng.uniform(b[i], b[i + 1])
            out[name] = col
        df = pd.DataFrame(out)
        df["initial_gap_m"] = df["headway"] * df["ego_speed"]
        states = self.odd["parameters"]["driver_state"]["states"]
        df["driver_category"] = df["driver_state"].map({k: v["category"]
                                                        for k, v in states.items()})
        return df

    # ------------------------------------------------------------ reporting
    def zero_exposure_regions(self) -> list[str]:
        """Human-readable list of ODD subregions declared with zero exposure weight."""
        out = []
        for name, f in self.factors.items():
            for key, dist in self._tables(name, f):
                if dist == NA:
                    continue
                if f["type"] == "categorical":
                    w = dict(dist["weights"] if "weights" in dist else dist)
                    out += [f"{name}{key} = {v}" for v, x in w.items() if x == 0]
                else:
                    b = list(dist["bins"])
                    out += [f"{name}{key} in [{b[i]:g}, {b[i + 1]:g})"
                            for i, x in enumerate(dist["weights"]) if x == 0]
        return out

    def describe(self) -> dict:
        return {**thaw(self.meta), "zero_exposure_regions": self.zero_exposure_regions()}
