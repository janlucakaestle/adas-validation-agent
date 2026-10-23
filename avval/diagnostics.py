"""Hand-back diagnostics: why did hazardous runs get no takeover request?

A run is "hazardous without hand-back" if it had no TOR and either collided or its
stop-aware acceleration TTC fell below the monitor's own TTC threshold. Each such run is
replayed from its stored seed, and the critical instant (minimum acceleration TTC) is
decomposed into the monitor's two branches:

- the required-deceleration branch, which already uses the target's current acceleration:
  did it see the braking, and by how much did it stay below its threshold?
- the constant-speed TTC branch;
and into what drove the low acceleration TTC: the target braking, the ego's own
acceleration (a transient that the extrapolation treats as permanent), or both.

The reasons are mutually exclusive and assigned in the order listed in `REASONS`.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import RESULTS_DIR
from .config import Release
from .reference import References
from .replay import replay
from .sim import first_contact_vec

REASONS = {
    "collision_without_tor": "collided with no TOR",
    "ego_accel_driven": "low acceleration-TTC caused by the ego's own acceleration "
                        "(not lead braking)",
    "req_below_threshold_lead_braking": "target braking seen by the required-deceleration "
                                        "branch, but needed braking stayed below its threshold",
    "other": "other",
}


COLUMNS = ["run_idx", "scenario", "friction", "t", "min_ttc_accel", "ttc_if_ego_accel_were_zero",
           "a_ego", "a_lead", "required_decel", "max_required_decel", "req_threshold",
           "constant_speed_ttc", "reason"]


def hazardous_without_handback(store, campaign: str, ttc_threshold: float, limit: int):
    return store.query(
        f"SELECT * FROM runs WHERE NOT tor_issued AND (collision OR min_ttc_accel < "
        f"{float(ttc_threshold)}) ORDER BY run_idx LIMIT {int(limit)}", campaign, max_rows=limit)


def diagnose(store, campaign: str, policy, release: Release | None = None,
             limit: int = 2000, final: bool = False) -> pd.DataFrame:
    from .estimation import require_campaigns
    release = release or Release.build(policy)
    # lifecycle, release, runtime and data hash (replays need its release); final evidence
    # only from final campaigns
    require_campaigns(store, [campaign], release, full_plan=False, final=final)
    p = release.sim_params
    refs = References(release)
    df = hazardous_without_handback(store, campaign, p.tor_ttc_s, limit)
    out = []
    for row in df.replace({np.nan: None}).to_dict("records"):
        again, tr = replay(row, policy, release, refs)
        g = tr.gap - p.contact_gap_m
        ttc_acc = first_contact_vec(g, tr.v_ego, tr.a_ego, tr.v_lead, tr.a_lead)
        i = int(np.argmin(ttc_acc))
        ttc_lead_only = float(first_contact_vec(g[i], tr.v_ego[i], 0.0, tr.v_lead[i],
                                                tr.a_lead[i]))
        ttc_ego_only = float(first_contact_vec(g[i], tr.v_ego[i], tr.a_ego[i], tr.v_lead[i], 0.0))
        if row["collision"]:
            reason = "collision_without_tor"
        elif tr.a_lead[i] >= 0 or (ttc_lead_only >= p.tor_ttc_s > ttc_ego_only):
            reason = "ego_accel_driven"
        elif tr.req[i] <= p.tor_req_decel:
            reason = "req_below_threshold_lead_braking"
        else:
            reason = "other"
        out.append({"run_idx": row["run_idx"], "scenario": row["scenario"],
                    "friction": row["friction"], "t": float(tr.t[i]),
                    "min_ttc_accel": float(ttc_acc[i]),
                    "ttc_if_ego_accel_were_zero": ttc_lead_only,
                    "a_ego": float(tr.a_ego[i]), "a_lead": float(tr.a_lead[i]),
                    "required_decel": float(tr.req[i]),
                    "max_required_decel": float(np.max(tr.req)),
                    "req_threshold": p.tor_req_decel,
                    "constant_speed_ttc": float(g[i] / (tr.v_ego[i] - tr.v_lead[i]))
                    if tr.v_ego[i] - tr.v_lead[i] > p.near_closing else math.inf,
                    "reason": reason})
    return pd.DataFrame(out, columns=COLUMNS)


def write_diagnostics(store, campaign: str, policy, limit: int = 2000,
                      final: bool = False) -> str:
    from .report import _md_table
    release = Release.build(policy)
    d = diagnose(store, campaign, policy, release, limit, final=final)
    n_all = store.n_runs(campaign)
    lines = ["# Hand-back diagnostics", "",
             f"Campaign `{campaign}` ({n_all} runs). Hazardous runs without a TOR (collision, or "
             f"stop-aware acceleration TTC below the monitor's TTC threshold), replayed from "
             f"their seeds and decomposed at the critical instant. Release "
             f"`{release.release_id[:16]}…`.", ""]
    if d.empty:
        lines.append("_No hazardous run without a takeover request._")
    else:
        counts = d["reason"].value_counts()
        lines += [_md_table(pd.DataFrame({"reason": [REASONS[r] for r in counts.index],
                                          "runs": counts.values}), max_rows=10), "",
                  _md_table(d.groupby("reason")[["min_ttc_accel", "ttc_if_ego_accel_were_zero",
                                                 "a_ego", "a_lead", "required_decel",
                                                 "max_required_decel"]].median()
                            .reset_index(), max_rows=10), "",
                  "Medians per reason. `ttc_if_ego_accel_were_zero` repeats the TTC "
                  "extrapolation with the ego's acceleration set to zero.", ""]
    path = RESULTS_DIR / f"handback_diagnostics_{campaign}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    d.to_csv(RESULTS_DIR / f"handback_diagnostics_{campaign}.csv", index=False)
    return str(path)
