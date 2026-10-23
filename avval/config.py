"""Configuration: parsing, validation and the immutable release configuration.

Every YAML file is parsed once and frozen (avval/frozen.py), so no caller can change the
cached configuration in memory. The configuration a simulation actually uses is carried by
a `Release`: the frozen parsed configs (after any explicit overrides), the policy hash and
the source-code hash. Its `release_id` is the content hash of exactly those objects, so
the identity recorded as provenance is computed from what is executed, never by re-reading
files that might differ from it.

Release files (part of the release ID): odd, driver, reference, exposure, acceptance, sim.
Protocol files (separate IDs, not part of a release): discovery, benchmark, sensitivity.
In rehearsal mode (AVVAL_REHEARSAL=1, `--rehearsal`) the sizes in config/rehearsal.yaml are
patched onto the benchmark and sensitivity protocols only; release files never change.
"""
from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property, lru_cache
from typing import Any

import yaml

from . import CONFIG_DIR
from .frozen import canonical_json, content_hash, deep_merge, freeze, thaw

DRIVER_CATEGORIES = ("intended_use", "foreseeable_misuse")
RELEASE_FILES = ("odd", "driver", "reference", "exposure", "acceptance", "sim")
PROTOCOL_FILES = ("discovery", "benchmark", "sensitivity")
SCHEMAS = {"odd": None, "driver": "driver/v3", "reference": "reference/v4",
           "exposure": "exposure/v3", "acceptance": "acceptance/v4", "sim": "sim/v3",
           "discovery": "discovery/v3", "benchmark": "benchmark/v3",
           "sensitivity": "sensitivity/v5", "rehearsal": "rehearsal/v1"}
REHEARSAL_PATCHED = ("benchmark", "sensitivity")


def rehearsal_active() -> bool:
    return os.environ.get("AVVAL_REHEARSAL") == "1"
# Bumped whenever the meaning of a stored metric or of the release identity changes, so
# results computed under an older meaning can never match a newer release.
RELEASE_SCHEMA = "release/v4"

CONTINUOUS = ("ego_speed", "headway", "friction")  # shared by every scenario
CATEGORICAL = ("scenario", "driver_state")
# Scenario-specific parameters, in the order they are stored and sampled.
SCENARIO_PARAMS = {"lead_brake": "lead_decel", "cut_in": "closing_speed"}


# ---------------------------------------------------------------- raw, frozen files
@lru_cache(maxsize=None)
def load_file(name: str):
    """The parsed, frozen contents of config/<name>.yaml (cached; immutable)."""
    with open(CONFIG_DIR / f"{name}.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    want = SCHEMAS.get(name)
    if want is not None and raw.get("schema") != want:
        raise ValueError(f"config/{name}.yaml: schema {raw.get('schema')!r}, expected {want!r}. "
                         "Old configuration formats are not migrated silently; see "
                         "REMEDIATION_SUMMARY.md, 'Breaking changes and migrations'.")
    if name in REHEARSAL_PATCHED and rehearsal_active():
        raw = deep_merge(raw, thaw(load_file("rehearsal"))[name])
    return freeze(raw)


def load_odd():
    odd = load_file("odd")
    _check_odd(odd)
    return odd


def load_driver():
    """Driver-model assumptions (config/driver.yaml): takeover times and braking response."""
    drv = load_file("driver")
    _check_driver(drv, load_odd())
    return drv


def load_reference():
    return load_file("reference")


def load_exposure():
    return load_file("exposure")


def load_acceptance():
    return load_file("acceptance")


def load_sim():
    return load_file("sim")


def load_discovery():
    return load_file("discovery")


# ---------------------------------------------------------------- validation
def _check_odd(odd) -> None:
    ds = odd["parameters"]["driver_state"]
    states = ds["states"]
    if list(states) != list(ds["values"]):
        raise ValueError("odd.yaml: driver_state.states must list exactly "
                         "driver_state.values, in order")
    for name, st in states.items():
        if st.get("category") not in DRIVER_CATEGORIES:
            raise ValueError(f"odd.yaml: driver state {name!r} has "
                             f"category={st.get('category')!r}, expected one of "
                             f"{DRIVER_CATEGORIES}")
        if not st.get("definition"):
            raise ValueError(f"odd.yaml: driver state {name!r} has no definition")
    cov = odd["coverage"]
    dims = list(cov["categorical_dimensions"])
    if "scenario" not in dims:
        raise ValueError("odd.yaml: coverage.categorical_dimensions must include scenario")
    for d in CATEGORICAL:
        if d not in dims and d not in cov.get("excluded_dimensions", {}):
            raise ValueError(f"odd.yaml: coverage dimension {d!r} is neither covered nor "
                             "excluded with a rationale (coverage.excluded_dimensions)")
    for scen, bins in cov["bins"].items():
        for key, edges in bins.items():
            lo, hi = param_range(key, scen, odd)
            if (edges[0] != lo or edges[-1] != hi
                    or any(b <= a for a, b in zip(edges, edges[1:]))):
                raise ValueError(f"odd.yaml: coverage bins of {key} ({scen}) must be "
                                 f"increasing and span exactly the ODD range [{lo}, {hi}]")


def _check_driver(drv, odd) -> None:
    if list(drv["states"]) != list(odd["parameters"]["driver_state"]["values"]):
        raise ValueError("driver.yaml: states must list exactly the ODD driver states, in order")
    for name, st in drv["states"].items():
        for k in ("takeover_mean_s", "takeover_sd_s", "floor_s", "peak_decel_fraction",
                  "brake_jerk"):
            v = st[k]
            if not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
                raise ValueError(f"driver.yaml: {name}.{k} must be a positive finite number")
    for k in ("brake_onset_delay_s", "brake_demand_factor", "standstill_hold_decel_mps2"):
        v = drv[k]
        if not (isinstance(v, (int, float)) and math.isfinite(v) and v >= 0):
            raise ValueError(f"driver.yaml: {k} must be a non-negative finite number")


def driver_attributes(driver_state: str, odd=None) -> dict:
    """Attributes of a driver state stored with every run, for grouping in SQL."""
    st = (odd or load_odd())["parameters"]["driver_state"]["states"][driver_state]
    return {"driver_category": st["category"]}


def param_range(key: str, scenario: str, odd=None) -> list[float]:
    """ODD range of a continuous parameter; `headway` has one range per scenario."""
    spec = (odd or load_file("odd"))["parameters"][key]
    return list(spec["ranges"][scenario] if "ranges" in spec else spec["range"])


def scenario_param(scenario: str) -> str:
    """The parameter that sets the severity of `scenario` (lead_decel or closing_speed)."""
    return SCENARIO_PARAMS[scenario]


def validate_case(case: dict, odd=None) -> dict:
    """Check a scenario case lies inside the ODD. Returns a clean copy or raises ValueError.

    The clean copy always has both scenario-specific keys; the one that does not apply to
    the scenario is None (stored as NULL). Non-finite numbers are rejected.
    """
    odd = odd or load_odd()
    params = odd["parameters"]
    if "severity" in case:
        raise ValueError("'severity' was replaced by 'lead_decel' (m/s^2, lead_brake) and "
                         "'closing_speed' (m/s, cut_in)")
    if "gap" in case:
        raise ValueError("'gap' (m) was replaced by 'headway' (s): the initial gap is "
                         "headway * ego_speed")
    clean = {}
    for key in CATEGORICAL:
        val = case.get(key)
        if val not in params[key]["values"]:
            raise ValueError(f"{key}={val!r} not in ODD values {list(params[key]['values'])}")
        clean[key] = val
    own = scenario_param(clean["scenario"])
    for scen, key in SCENARIO_PARAMS.items():
        if key != own and case.get(key) is not None:
            raise ValueError(f"{key} applies only to scenario {scen!r}; omit it for "
                             f"{clean['scenario']!r}, which uses {own}")
    for key in (*CONTINUOUS, own):
        if case.get(key) is None:
            raise ValueError(f"missing parameter {key}")
        try:
            val = float(case[key])
        except (TypeError, ValueError):
            raise ValueError(f"{key}={case[key]!r} is not a number") from None
        if not math.isfinite(val):
            raise ValueError(f"{key}={val} is not finite")
        lo, hi = param_range(key, clean["scenario"], odd)
        if not lo <= val <= hi:
            raise ValueError(f"{key}={val} outside ODD range [{lo}, {hi}]"
                             + (f" for {clean['scenario']}" if key == "headway" else ""))
        clean[key] = val
    for key in SCENARIO_PARAMS.values():
        clean.setdefault(key, None)
    return clean


# ---------------------------------------------------------------- the release
@dataclass(frozen=True)
class Release:
    """Everything that determines a simulated result and its evaluation.

    `configs` holds the frozen, parsed (and, for variants, overridden) configurations that
    the simulation and evaluation use; `release_id` hashes exactly these objects plus the
    policy and code hashes. Build with `Release.build`; derive variants with
    `with_overrides`, which yields a different release ID for any semantic change.
    """
    configs: Mapping[str, Any]
    policy_sha256: str | None
    code_sha256: str
    overrides: Mapping[str, Any] = field(default_factory=lambda: freeze({}))

    @classmethod
    def build(cls, policy=None, overrides: Mapping | None = None,
              policy_sha256: str | None = None) -> "Release":
        from .provenance import code_hash, policy_hash
        base = {name: load_file(name) for name in RELEASE_FILES}
        rel = cls(freeze(base), policy_sha256 or policy_hash(policy), code_hash())
        if overrides:
            return rel.with_overrides(overrides)  # validates the variant
        rel.validate()
        return rel

    def with_overrides(self, overrides: Mapping) -> "Release":
        """A variant release: `overrides` maps a config name to a nested patch, e.g.
        {"sim": {"ego": {"accel_min_mps2": -3.0}}}. Unknown keys are rejected."""
        unknown = set(overrides) - set(RELEASE_FILES)
        if unknown:
            raise KeyError(f"overrides for unknown config(s) {sorted(unknown)}; "
                           f"allowed: {list(RELEASE_FILES)}")
        configs = {k: thaw(v) for k, v in self.configs.items()}
        merged_overrides = thaw(self.overrides)
        for name, patch in overrides.items():
            configs[name] = deep_merge(configs[name], patch)
            merged_overrides[name] = _merge_patch(merged_overrides.get(name, {}), patch)
        rel = Release(freeze(configs), self.policy_sha256, self.code_sha256,
                      freeze(merged_overrides))
        rel.validate()
        return rel

    def with_policy(self, policy) -> "Release":
        from .provenance import policy_hash
        return Release(self.configs, policy_hash(policy), self.code_sha256, self.overrides)

    def validate(self) -> None:
        """Validate every config of this release (nominal or variant); raises ValueError."""
        from .evaluation import check_acceptance
        from .exposure import ExposureModel
        _check_odd(self.odd)
        _check_driver(self.driver, self.odd)
        self.sim_params  # noqa: B018 - builds and validates the simulator parameters
        ExposureModel(self.exposure, self.odd)
        check_acceptance(self.acceptance)

    # accessors
    @property
    def odd(self):
        return self.configs["odd"]

    @property
    def driver(self):
        return self.configs["driver"]

    @property
    def reference(self):
        return self.configs["reference"]

    @property
    def exposure(self):
        return self.configs["exposure"]

    @property
    def acceptance(self):
        return self.configs["acceptance"]

    @property
    def sim(self):
        return self.configs["sim"]

    @cached_property
    def sim_params(self):
        from .sim import SimParams
        return SimParams.from_release(self)

    @cached_property
    def exposure_model(self):
        from .exposure import ExposureModel
        return ExposureModel(self.exposure, self.odd)

    @cached_property
    def config_sha256(self) -> dict[str, str]:
        """Content hash of each parsed (canonical) config actually used."""
        return {name: content_hash(cfg) for name, cfg in self.configs.items()}

    @property
    def exposure_model_id(self) -> str:
        return self.config_sha256["exposure"]

    @property
    def is_nominal(self) -> bool:
        return not self.overrides

    @cached_property
    def release_id(self) -> str:
        return content_hash({"schema": RELEASE_SCHEMA, "configs": self.config_sha256,
                             "policy_sha256": self.policy_sha256,
                             "code_sha256": self.code_sha256})

    def manifest(self) -> dict:
        """Machine-readable release manifest (JSON-serialisable)."""
        return {"schema": RELEASE_SCHEMA, "release_id": self.release_id,
                "policy_sha256": self.policy_sha256, "code_sha256": self.code_sha256,
                "config_sha256": self.config_sha256, "overrides": thaw(self.overrides),
                "nominal": self.is_nominal, "exposure_model_id": self.exposure_model_id,
                "configs": thaw(self.configs)}

    def canonical(self) -> str:
        return canonical_json(self.manifest())


def _merge_patch(a: Mapping, b: Mapping) -> dict:
    """Union of two override patches (b wins), for recording cumulative overrides."""
    out = thaw(a)
    for k, v in b.items():
        out[k] = _merge_patch(out.get(k, {}), v) if isinstance(v, Mapping) and isinstance(
            out.get(k), Mapping) else thaw(v)
    return out


def protocol_id(name: str) -> str:
    """Content hash of a protocol config (discovery objective, benchmark)."""
    return content_hash(load_file(name))
