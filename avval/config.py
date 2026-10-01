"""Load the ODD and acceptance-criteria configuration."""
from __future__ import annotations

from functools import lru_cache

import yaml

from . import CONFIG_DIR

DRIVER_CATEGORIES = ("intended_use", "foreseeable_misuse")


@lru_cache
def load_odd() -> dict:
    with open(CONFIG_DIR / "odd.yaml", encoding="utf-8") as f:
        odd = yaml.safe_load(f)
    _check_driver_states(odd["parameters"]["driver_state"])
    return odd


def _check_driver_states(ds: dict) -> None:
    states = ds["states"]
    if list(states) != ds["values"]:
        raise ValueError("odd.yaml: driver_state.states must list exactly "
                         "driver_state.values, in order")
    for name, st in states.items():
        if st.get("category") not in DRIVER_CATEGORIES:
            raise ValueError(f"odd.yaml: driver state {name!r} has "
                             f"category={st.get('category')!r}, expected one of "
                             f"{DRIVER_CATEGORIES}")
        if not st.get("definition"):
            raise ValueError(f"odd.yaml: driver state {name!r} has no definition")


def driver_attributes(driver_state: str) -> dict:
    """Attributes of a driver state stored with every run, for grouping in SQL."""
    st = load_odd()["parameters"]["driver_state"]["states"][driver_state]
    return {"driver_category": st["category"]}


@lru_cache
def load_driver() -> dict:
    """Driver-model assumptions (config/driver.yaml): takeover times and braking response."""
    with open(CONFIG_DIR / "driver.yaml", encoding="utf-8") as f:
        drv = yaml.safe_load(f)
    if list(drv["states"]) != load_odd()["parameters"]["driver_state"]["values"]:
        raise ValueError("driver.yaml: states must list exactly the ODD driver states, in order")
    return drv


@lru_cache
def load_reference() -> dict:
    """Reference controllers for preventability (config/reference.yaml)."""
    with open(CONFIG_DIR / "reference.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def load_exposure() -> dict:
    """Exposure-weighted sampling distribution over the ODD (config/exposure.yaml)."""
    with open(CONFIG_DIR / "exposure.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def load_acceptance() -> dict:
    with open(CONFIG_DIR / "acceptance.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONTINUOUS = ("ego_speed", "headway", "friction")  # shared by every scenario
CATEGORICAL = ("scenario", "driver_state")
# Scenario-specific parameters, in the order they are stored and sampled.
SCENARIO_PARAMS = {"lead_brake": "lead_decel", "cut_in": "closing_speed"}


def param_range(key: str, scenario: str) -> list[float]:
    """ODD range of a continuous parameter; `headway` has one range per scenario."""
    spec = load_odd()["parameters"][key]
    return spec["ranges"][scenario] if "ranges" in spec else spec["range"]


def scenario_param(scenario: str) -> str:
    """The parameter that sets the severity of `scenario` (lead_decel or closing_speed)."""
    return SCENARIO_PARAMS[scenario]


def validate_case(case: dict) -> dict:
    """Check a scenario case lies inside the ODD. Returns a clean copy or raises ValueError.

    The clean copy always has both scenario-specific keys; the one that does not apply to
    the scenario is None (stored as NULL).
    """
    params = load_odd()["parameters"]
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
            raise ValueError(f"{key}={val!r} not in ODD values {params[key]['values']}")
        clean[key] = val
    own = scenario_param(clean["scenario"])
    for scen, key in SCENARIO_PARAMS.items():
        if key != own and case.get(key) is not None:
            raise ValueError(f"{key} applies only to scenario {scen!r}; omit it for "
                             f"{clean['scenario']!r}, which uses {own}")
    for key in (*CONTINUOUS, own):
        if case.get(key) is None:
            raise ValueError(f"missing parameter {key}")
        val = float(case[key])
        lo, hi = param_range(key, clean["scenario"])
        if not lo <= val <= hi:
            raise ValueError(f"{key}={val} outside ODD range [{lo}, {hi}]"
                             + (f" for {clean['scenario']}" if key == "headway" else ""))
        clean[key] = val
    for key in SCENARIO_PARAMS.values():
        clean.setdefault(key, None)
    return clean
