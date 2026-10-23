"""The secret boundary: what search strategies may see, and what they must never see.

Everything a search strategy (the LLM agent or a baseline) can observe goes through
avval/search.py, which exposes only:
- the public ODD (parameter meanings, ranges, driver-state definitions, coverage bins);
- the public discovery objectives (config/discovery.yaml);
- per-run columns in AGENT_COLUMNS, with the descriptions in COLUMN_DESCRIPTIONS;
- its own budget.

`protected_items(release)` enumerates, from the actual release configuration, everything
that must not reach a search strategy: acceptance criteria (IDs, names, populations,
events, metrics, quantiles, thresholds, min_n, confidence), reference-response parameters,
driver-model parameters and sources, monitor and actuator design values, exposure weights,
and how the policy was built. tests/test_agent_isolation.py builds the complete
agent-visible payload and checks it against this registry, so a new secret added to a
config file is protected without editing a vocabulary list.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# Per-run columns a search strategy may read (query_results, test_predicate, evidence SQL).
# Hidden: the per-run seed, monitor internals (required deceleration, TOR branch), the
# acceptance-only comfort metric and populations (handback_required), the
# careful-competent-driver reference, and the scenario timing constant.
AGENT_COLUMNS = ("run_idx", "scenario", "ego_speed", "headway", "initial_gap_m", "lead_decel",
                 "closing_speed", "friction", "driver_state", "driver_category",
                 "avoidable_by_reference", "collision", "impact_speed", "collision_time",
                 "end_state", "min_ttc", "min_ttc_accel", "min_thw", "min_gap", "max_decel",
                 "max_jerk", "max_jerk_raw", "tor_issued", "tor_time", "takeover_time",
                 "duration")

COLUMN_DESCRIPTIONS = {
    "run_idx": "run number within this campaign (0-based)",
    "scenario": "lead_brake | cut_in",
    "ego_speed": "initial ego speed, m/s (also the cruise set speed)",
    "headway": "initial time headway, s",
    "initial_gap_m": "initial gap, m (headway * ego_speed)",
    "lead_decel": "lead deceleration, m/s^2 (NULL for cut_in)",
    "closing_speed": "closing speed at cut-in, m/s (NULL for lead_brake)",
    "friction": "tyre-road friction coefficient",
    "driver_state": "attentive | distracted",
    "driver_category": "intended_use | foreseeable_misuse",
    "avoidable_by_reference": ("TRUE if a fixed, brake-only reference response that starts at "
                               "hazard onset avoids contact in this scenario. A property of the "
                               "scenario, not of the system's run; its parameters are not "
                               "disclosed, and FALSE does not mean the collision is physically "
                               "unavoidable"),
    "collision": "the run ended in contact",
    "impact_speed": "relative speed at contact, m/s (0 without contact)",
    "collision_time": "time of contact, s (NULL without contact)",
    "end_state": "collision | both_stopped | horizon_safe | horizon_unresolved",
    "min_ttc": "minimum constant-speed time-to-collision before contact, s; NULL = never closing",
    "min_ttc_accel": ("minimum time-to-collision extrapolating both vehicles' current "
                      "accelerations until they stop, s; NULL = gap never closes"),
    "min_thw": "minimum time headway after the first seconds of the run, s",
    "min_gap": "minimum gap, m; NULL for a collision",
    "max_decel": "maximum ego deceleration, m/s^2",
    "max_jerk": "maximum jerk of the smoothed ego acceleration, m/s^3",
    "max_jerk_raw": "maximum jerk from raw sample differences, m/s^3",
    "tor_issued": "the system issued a takeover request",
    "tor_time": "time of the takeover request, s (NULL if none)",
    "takeover_time": "time from the takeover request to the driver's first input, s",
    "duration": "simulated duration, s (time of contact for a collision)",
}

# Words and phrases that describe protected design or evaluation content. They must not
# appear in any agent-visible text, whatever the configuration values are.
PROTECTED_TERMS = (
    "acceptance", "threshold", "verdict", "estimation", "exposure", "release decision",
    "min_n", "AC-0", "percentile", "quantile", "handback_required", "hand-back oracle",
    "required deceleration", "required_decel", "max_required_decel", "tor_reason",
    "max_jerk_automated", "authority", "accel_min", "accel_max", "takeover_mean",
    "takeover_sd", "floor_s", "peak_decel", "brake_jerk", "brake_demand", "brake_onset",
    "decel_fraction", "reaction_time_s", "mu*g", "mu * g", "μg", "μ g", "friction limit",
    "training", "trained", "behaviour-cloned", "behavior-cloned", "behaviour cloning",
    "behavior cloning", "intelligent driver model", "IDM", "MLP", "ground truth",
    "out-of-distribution", "fault", "weak", "Green", "Summala", "Johansson", "Magister",
    "Kaestle", "Kästle", "careful_competent", "careful and competent")


@dataclass(frozen=True)
class ProtectedItem:
    category: str
    label: str
    value: object  # float for numbers, str for formulas / identifiers


def _numbers(category: str, label: str, obj) -> list[ProtectedItem]:
    out = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)) and math.isfinite(obj):
        return [ProtectedItem(category, label, float(obj))]
    if hasattr(obj, "items"):
        for k, v in obj.items():
            out += _numbers(category, f"{label}.{k}", v)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            out += _numbers(category, f"{label}[{i}]", v)
    return out


def protected_items(release) -> list[ProtectedItem]:
    """Every protected number, formula and identifier of this release."""
    items: list[ProtectedItem] = []
    acc = release.acceptance
    items += [ProtectedItem("acceptance", "confidence", float(acc["confidence"]))]
    for c in acc["criteria"]:
        cid = c["id"]
        items.append(ProtectedItem("acceptance", f"{cid}.id", cid))
        items.append(ProtectedItem("acceptance", f"{cid}.name", c["name"]))
        for key in ("event", "metric", "where"):
            if c.get(key):
                items.append(ProtectedItem("acceptance", f"{cid}.{key}", c[key]))
        for key in ("threshold", "q", "min_n"):
            if c.get(key) is not None:
                items.append(ProtectedItem("acceptance", f"{cid}.{key}", float(c[key])))
        for name, v in dict(c.get("params") or {}).items():
            items.append(ProtectedItem("acceptance", f"{cid}.params.{name}", float(v)))
            items.append(ProtectedItem("acceptance", f"{cid}.params.{name}:name", name))
        # numbers inside the SQL (e.g. a latency limit)
        for key in ("event", "metric", "where"):
            for tok in re.findall(r"(?<![\w.])\d+\.?\d*(?:e-?\d+)?", c.get(key) or ""):
                items.append(ProtectedItem("acceptance", f"{cid}.{key}:{tok}", float(tok)))
    items += _numbers("reference", "reference", release.reference)
    items += _numbers("driver", "driver", release.driver)
    sim = release.sim
    for block in ("ego", "monitor", "required_decel", "termination"):
        items += _numbers("design", f"sim.{block}", sim[block])
    items.append(ProtectedItem("design", "sim.monitor.ttc_model", sim["monitor"]["ttc_model"]))
    items += _numbers("exposure", "exposure", release.exposure["factors"])
    for st in release.driver["states"].values():
        items.append(ProtectedItem("driver", "source", st["source"]))
    return items


def public_numbers(release, budget: int | None = None) -> set[float]:
    """Numbers that are legitimately public: ODD ranges and coverage bins, the discovery
    objectives, tool limits and the budget. A protected value equal to one of these cannot
    be hidden by omission; the isolation test then checks it never appears in a protected
    context instead."""
    from .config import load_discovery
    from .agent import MAX_CASES_PER_CALL, QUERY_ROWS
    nums: set[float] = set()
    nums |= {i.value for i in _numbers("odd", "odd", release.odd)}
    for t in load_discovery()["targets"].values():
        nums |= {float(x) for x in re.findall(r"(?<![\w.])\d+\.?\d*", t["predicate"])}
    nums |= {float(MAX_CASES_PER_CALL), float(QUERY_ROWS), 0.0, 1.0}
    if budget is not None:
        nums.add(float(budget))
    return nums
