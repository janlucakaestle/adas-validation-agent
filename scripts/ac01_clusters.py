"""Characterise the preventable attentive-driver collisions (AC-01) of the estimation campaign.

Every collision is replayed from its stored seed (the replay must reproduce the collision
and the takeover time), and the brake threat number (BTN) at hazard onset is computed from
the replayed trace: the deceleration needed to stop, or match speed, 2 m behind the target
(`avval.sim.required_decel`) divided by mu*g. Writes `results/ac01_clusters.md`.

    PYTHONPATH=. python scripts/ac01_clusters.py [estimation campaign, default: estimate]
"""
from __future__ import annotations

import math
import sys

import pandas as pd

from avval import RESULTS_DIR
from avval.policy import LearnedACC
from avval.sim import G, hazard_onset, required_decel, simulate
from avval.store import Store

OWN = {"lead_brake": "lead_decel", "cut_in": "closing_speed"}


def collisions(store, policy, campaign: str) -> pd.DataFrame:
    cols = ("scenario, ego_speed, headway, initial_gap_m, lead_decel, closing_speed, friction, "
            "driver_state, seed, tor_issued, tor_time, takeover_time, impact_speed")
    coll = store.query(f"SELECT {cols} FROM runs WHERE collision AND preventable AND "
                       "driver_state = 'attentive'", campaign, max_rows=10**9)
    rows = []
    for rec in coll.to_dict("records"):
        case = {k: rec[k] for k in ("scenario", "ego_speed", "headway", "friction",
                                    "driver_state")}
        case[OWN[rec["scenario"]]] = rec[OWN[rec["scenario"]]]
        m, tr = simulate(case, policy, int(rec["seed"]))
        if not (m["collision"] and abs(m["takeover_time"] - rec["takeover_time"]) < 1e-9):
            raise SystemExit(f"replay does not reproduce the stored run: {case}")
        i = int(round(hazard_onset(case) / (tr.t[1] - tr.t[0])))
        a_lead = tr.a_lead[i] if tr.a_lead is not None else 0.0
        btn = required_decel(tr.gap[i], tr.v_ego[i], tr.v_lead[i], a_lead) / (case["friction"] * G)
        rows.append({**rec, "btn_onset": btn,
                     "tor_after_onset_s": rec["tor_time"] - hazard_onset(case)})
    return pd.DataFrame(rows)


def _range(s: pd.Series, digits: int = 2) -> str:
    return f"{s.min():.{digits}f}–{s.max():.{digits}f} (median {s.median():.{digits}f})"


def main(campaign: str = "estimate") -> str:
    store, policy = Store(), LearnedACC.load()
    df = collisions(store, policy, campaign)
    att = store.query("SELECT scenario, ego_speed, headway, closing_speed, lead_decel FROM runs "
                      "WHERE driver_state = 'attentive'", campaign, max_rows=10**9)
    scen = [s for s in ("cut_in", "lead_brake") if (df.scenario == s).any()]
    labels = {"cut_in": "Cut-in", "lead_brake": "Lead braking"}
    table = {"Collisions / attentive runs": {}, "Headway (s)": {}, "Initial gap (m)": {},
             "Ego speed (m/s)": {}, "Severity": {}, "Friction": {}, "BTN at hazard onset": {},
             "Takeover request after hazard onset (s)": {}, "Reaction after the request (s)": {},
             "Impact speed (m/s)": {}, "Box holding them (edges rounded outwards)": {}}
    for s in scen:
        g, a = df[df.scenario == s], att[att.scenario == s]
        own = OWN[s]
        # The smallest box holding every collision, with its edges rounded outwards (headway
        # up to the next 0.01 s, severity down to the next 0.1), so it still holds them all.
        h_max = math.ceil(g.headway.max() * 100) / 100
        s_min = math.floor(g[own].min() * 10) / 10
        box = (a.headway <= h_max) & (a[own] >= s_min)
        unit = "closing speed, m/s" if s == "cut_in" else "lead deceleration, m/s²"
        col = labels[s]
        table["Collisions / attentive runs"][col] = f"{len(g)} / {len(a):,} ({len(g)/len(a):.3%})"
        table["Headway (s)"][col] = _range(g.headway)
        table["Initial gap (m)"][col] = _range(g.initial_gap_m, 1)
        table["Ego speed (m/s)"][col] = _range(g.ego_speed, 1)
        table["Severity"][col] = f"{unit}: {_range(g[own], 1)}"
        table["Friction"][col] = _range(g.friction)
        table["BTN at hazard onset"][col] = (f"{_range(g.btn_onset)}; above 1 in "
                                             f"{int((g.btn_onset > 1).sum())}")
        table["Takeover request after hazard onset (s)"][col] = _range(g.tor_after_onset_s)
        table["Reaction after the request (s)"][col] = _range(g.takeover_time)
        table["Impact speed (m/s)"][col] = _range(g.impact_speed, 1)
        table["Box holding them (edges rounded outwards)"][col] = (
            f"headway ≤ {h_max:.2f} s and {own} ≥ {s_min:.1f}: "
            f"{box.mean():.1%} of attentive {labels[s].lower()} runs, collision rate inside "
            f"{len(g)/box.sum():.1%}")
    rows = "\n".join(f"| {k} | " + " | ".join(v.get(labels[s], "") for s in scen) + " |"
                     for k, v in table.items())
    text = "\n".join([
        "# AC-01: where the attentive-driver collisions are", "",
        f"The preventable collisions with an attentive driver in `{campaign}` "
        f"({len(df)} runs), each replayed from its stored seed; every replay reproduced the "
        "stored collision and takeover time. Recomputed by `scripts/ac01_clusters.py`.", "",
        "| | " + " | ".join(labels[s] for s in scen) + " |",
        "| --- |" + " --- |" * len(scen), rows, "",
        "BTN (brake threat number) is the deceleration needed to stop, or match speed, 2 m "
        "behind the target, divided by μg. It can exceed 1 in a preventable run because "
        "preventability asks whether 0.9 μg braking avoids contact, not a 2 m stand-off.", ""])
    path = RESULTS_DIR / "ac01_clusters.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    print(main(*sys.argv[1:]))
