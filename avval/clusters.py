"""Characterise the attentive-driver collisions in scenarios avoidable by the ideal reference
(AC-01's events) of a DISCOVERY campaign, and derive reference predicates from them.

Every collision is replayed from its stored seed (the replay must reproduce the stored row
exactly), and the brake threat number (BTN) at hazard onset is computed from the replayed
trace: the monitor's required deceleration divided by mu*g. Writes `ac01_clusters.md` and
`reference_predicates.json` (the smallest box per scenario holding the collisions, labelled
with the campaign it was derived from). A box may only be scored on the frozen hold-out after
`freeze-predicates` (never on the campaign it came from).

    python -m avval.cli [--final] reference-boxes <campaign>
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from . import RESULTS_DIR
from .config import SCENARIO_PARAMS, Release
from .replay import replay, same_value
from .sim import G
from .store import COLUMNS


def collisions(store, policy, release, campaign: str) -> pd.DataFrame:
    coll = store.query("SELECT * FROM runs WHERE collision AND avoidable_by_reference AND "
                       "driver_state = 'attentive'", campaign, max_rows=10**9)
    rows = []
    for rec in coll.replace({np.nan: None}).to_dict("records"):
        again, tr = replay(rec, policy, release)
        if not all(same_value(rec[c], again[c]) for c in COLUMNS):
            raise SystemExit(f"replay does not reproduce stored run {rec['run_idx']}")
        i = int(round(rec["hazard_onset_s"] / release.sim_params.dt))
        rows.append({**rec, "btn_onset": float(tr.req[i]) / (rec["friction"] * G),
                     "tor_after_onset_s": rec["tor_time"] - rec["hazard_onset_s"]
                     if rec["tor_time"] is not None else None})
    return pd.DataFrame(rows)


def _range(s: pd.Series, digits: int = 2) -> str:
    return f"{s.min():.{digits}f}–{s.max():.{digits}f} (median {s.median():.{digits}f})"


def write_clusters(store, policy, campaign: str, final: bool = False) -> str:
    """Characterise AC-01's events in `campaign` and write the reference boxes."""
    from .estimation import require_campaigns
    release = Release.build(policy)
    require_campaigns(store, [campaign], release, full_plan=False, final=final)
    df = collisions(store, policy, release, campaign)
    if df.empty:
        raise SystemExit(f"no AC-01 events in {campaign}")
    preds, lines = [], []
    for scen, g in df.groupby("scenario"):
        own = SCENARIO_PARAMS[scen]
        h_max = math.ceil(g.headway.max() * 100) / 100
        s_min = math.floor(g[own].min() * 10) / 10
        pred = f"scenario = '{scen}' AND headway <= {h_max:.2f} AND {own} >= {s_min:.1f}"
        preds.append({"condition": f"box-{scen}", "predicate": pred, "derived_from": [campaign],
                      "release_id": release.release_id})
        lines += [f"## {scen}: {len(g)} collisions", "",
                  f"- headway {_range(g.headway)} s; {own} {_range(g[own], 1)}",
                  f"- ego speed {_range(g.ego_speed, 1)} m/s; friction {_range(g.friction)}",
                  f"- BTN at hazard onset {_range(g.btn_onset)}; above 1 in "
                  f"{int((g.btn_onset > 1).sum())}",
                  f"- TOR after hazard onset {_range(g.tor_after_onset_s.astype(float))} s; "
                  f"takeover time {_range(g.takeover_time.astype(float))} s",
                  f"- box (edges rounded outwards): `{pred}`", ""]
    text = "\n".join([f"# AC-01 events in `{campaign}` (discovery data)", "",
                      f"{len(df)} collisions with an attentive driver in scenarios avoidable by "
                      "the ideal reference, each replayed and reproduced exactly. Release "
                      f"`{release.release_id[:16]}…`. The boxes below are derived from this "
                      "campaign and are NOT validated by it; see the hold-out report.", "",
                      *lines])
    (RESULTS_DIR / "ac01_clusters.md").write_text(text, encoding="utf-8")
    (RESULTS_DIR / "reference_predicates.json").write_text(
        json.dumps({"derived_from": campaign, "predicates": preds}, indent=1), encoding="utf-8")
    return str(RESULTS_DIR / "ac01_clusters.md")
