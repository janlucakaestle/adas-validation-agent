"""The driver's standstill brake hold is a behavioural assumption (TODO(data)), not a
numerical fix: these tests show what it changes, that the kinematics never reverse
independently of it, and that it is covered by the sensitivity protocol."""
import numpy as np
import pytest

from avval.config import Release, load_driver
from avval.sensitivity import design, load_protocol

# Distracted driver, hard lead braking on a wet road: the driver takes over late and brakes
# towards a stopped lead. Seed 14 is a run in which, without a hold, the car creeps on.
CASE = dict(scenario="lead_brake", ego_speed=32.0, lead_decel=8.0, headway=1.875,
            friction=0.5, driver_state="distracted")
SEED = 14


def _run(policy, hold, dt=0.05):
    from avval.sim import simulate
    p = Release.build(policy, overrides={"driver": {"standstill_hold_decel_mps2": hold},
                                         "sim": {"time": {"dt_s": dt}}}).sim_params
    return simulate(CASE, policy, SEED, p)


def test_nominal_value_is_a_documented_placeholder():
    from avval import CONFIG_DIR
    assert load_driver()["standstill_hold_decel_mps2"] == 2.0
    line = next(ln for ln in (CONFIG_DIR / "driver.yaml").read_text().splitlines()
                if ln.startswith("standstill_hold_decel_mps2"))
    assert "TODO(data)" in line


def test_without_a_hold_the_driver_never_stops_and_creeps_into_contact(policy):
    m, tr = _run(policy, 0.0)
    assert m["collision"] and m["impact_speed"] < 0.1 and m["collision_time"] > 10.0
    # the contact time depends on the step: the artefact the hold removes
    m2, _ = _run(policy, 0.0, dt=0.025)
    assert not m2["collision"] or abs(m2["collision_time"] - m["collision_time"]) > 0.5


@pytest.mark.parametrize("hold", [2.0, 4.0])
def test_with_a_hold_the_driver_stops_in_finite_time_without_contact(policy, hold):
    m, tr = _run(policy, hold)
    assert not m["collision"] and m["end_state"] == "both_stopped"
    assert tr.v_ego[-1] < 0.5 and m["duration"] < 15.0


@pytest.mark.parametrize("hold", [2.0, 4.0])
def test_stopping_converges_with_the_timestep(policy, hold):
    a, _ = _run(policy, hold)
    b, _ = _run(policy, hold, dt=0.025)
    assert a["end_state"] == b["end_state"] and a["collision"] == b["collision"]
    assert abs(a["duration"] - b["duration"]) <= 2 * 0.05


def test_a_firmer_hold_stops_sooner(policy):
    assert _run(policy, 4.0)[0]["duration"] <= _run(policy, 2.0)[0]["duration"]


@pytest.mark.parametrize("hold", [0.0, 2.0, 4.0])
def test_no_vehicle_ever_reverses(policy, hold):
    m, tr = _run(policy, hold)
    assert (tr.v_ego >= 0).all() and (tr.v_lead >= 0).all()
    stopped = np.flatnonzero((tr.v_lead == 0) & (tr.v_ego == 0))
    if len(stopped):
        assert np.all(np.diff(tr.gap[stopped[0]:]) >= -1e-12)


def test_the_hold_changes_collision_classification(policy):
    """Exactly why it must be in the sensitivity analysis: the same scenario and seed is a
    collision without the hold and not with it."""
    assert _run(policy, 0.0)[0]["collision"] != _run(policy, 2.0)[0]["collision"]


def test_the_hold_is_covered_by_every_sensitivity_design(policy):
    proto = load_protocol()
    f = proto["factors"]["standstill_hold_decel_mps2"]
    assert f["path"] == ["driver", "standstill_hold_decel_mps2"]
    assert f["range"][0] > 0 < f["range"][1]  # 0 is the non-terminating model, see above
    assert "standstill_hold_decel_mps2" in proto["designs"]["factorial2"]["factors"]
    rel = Release.build(policy)
    for kind in ("oat", "factorial2", "lhs"):
        assert any("standstill_hold_decel_mps2" in v for v in design(kind, rel)), kind
