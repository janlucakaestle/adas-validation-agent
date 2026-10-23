"""Synthetic campaigns and rows for evaluation-level tests (no simulation)."""
from avval.config import driver_attributes
from avval.store import COLUMNS


def register(store, name, kind="search", planned=10_000, seed=0, release_id="r" * 64,
             runtime_id="t" * 64, **kw):
    store.create_campaign({"campaign_id": name, "kind": kind, "method": kw.pop("method", "test"),
                           "seed": seed, "planned_runs": planned, "release_id": release_id,
                           "runtime_id": runtime_id, "exposure_model_id": "e" * 64,
                           "case_source": "adaptive", "overrides": {}, "provenance": {}, **kw})


def row(campaign, i, **kw):
    base = dict(campaign=campaign, run_idx=i, seed=i, scenario="cut_in", ego_speed=30.0,
                headway=1.0, initial_gap_m=30.0, lead_decel=None, closing_speed=3.0,
                friction=1.0, driver_state="attentive", hazard_onset_s=0.0,
                avoidable_by_reference=True, handback_required=False,
                ccd_avoidable_by_reference=None, collision=False, impact_speed=0.0,
                collision_time=None, end_state="horizon_safe", min_ttc=5.0, min_ttc_accel=5.0,
                min_thw=1.0, min_gap=10.0, max_decel=1.0, max_jerk=1.0, max_jerk_automated=1.0,
                max_jerk_raw=2.0, max_required_decel=0.5, tor_issued=False, tor_time=None,
                tor_reason=None, takeover_time=None, duration=20.0)
    base.update(kw)
    if base["collision"]:
        base.update(end_state="collision", min_gap=None, collision_time=base.get("collision_time") or 3.0)
    out = {**base, **driver_attributes(base["driver_state"])}
    assert set(out) == set(COLUMNS)
    return out


def campaign_of(store, name, rows, **kw):
    register(store, name, **kw)
    store.insert([r if "campaign" in r and r["campaign"] == name else r for r in rows])
    return name
