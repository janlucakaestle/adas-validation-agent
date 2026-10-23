"""The driver model is release configuration: per-state changes affect only that state, and
any change is a different release."""
from avval.config import Release, load_driver, load_odd
from avval.sim import simulate

STATES = load_odd()["parameters"]["driver_state"]["values"]
# Hand-back cases (harsh lead braking), plus one gentle case with no hand-back.
CASES = [dict(scenario="lead_brake", ego_speed=30.0, headway=g / 30.0, lead_decel=d, friction=1.0)
         for g, d in ((25.0, 8.0), (30.0, 6.0), (40.0, 5.0), (40.0, 2.0))]


def _metrics(policy, params=None):
    return {(s, i, seed): simulate({**c, "driver_state": s}, policy, seed, params)[0]
            for s in STATES for i, c in enumerate(CASES) for seed in range(3)}


def test_per_state_change_affects_only_that_state(policy):
    base = _metrics(policy)
    var = Release.build(policy, overrides={"driver": {"states": {"distracted": {
        "takeover_mean_s": 3.0, "brake_jerk": 5.0, "peak_decel_fraction": 0.5}}}})
    changed = _metrics(policy, var.sim_params)
    for key in base:
        if key[0] != "distracted":
            assert changed[key] == base[key], key
    assert any(changed[k] != base[k] for k in base if k[0] == "distracted")


def test_brake_onset_delay_postpones_braking_not_first_input(policy):
    case = {**CASES[1], "driver_state": "attentive"}
    var = Release.build(policy, overrides={"driver": {"brake_onset_delay_s": 0.5}}).sim_params
    base, delayed = simulate(case, policy, 0)[0], simulate(case, policy, 0, var)[0]
    assert base["tor_issued"] and delayed["takeover_time"] == base["takeover_time"]
    assert delayed != base
    gentle = {**CASES[3], "driver_state": "attentive"}  # no hand-back -> unaffected
    assert simulate(gentle, policy, 0, var)[0] == simulate(gentle, policy, 0)[0]


def test_driver_config_is_part_of_the_release_identity(policy):
    base = Release.build(policy)
    var = base.with_overrides({"driver": {"brake_demand_factor": 1.6}})
    assert "driver" in base.config_sha256 and var.release_id != base.release_id


def test_assumed_values_carry_todo_markers():
    from avval import CONFIG_DIR
    lines = (CONFIG_DIR / "driver.yaml").read_text(encoding="utf-8").splitlines()
    for key in ("brake_onset_delay_s", "brake_demand_factor", "standstill_hold_decel_mps2",
                "peak_decel_fraction", "brake_jerk"):
        assert all("TODO(data)" in ln for ln in lines if ln.strip().startswith(key + ":")), key


def test_loaded_driver_config_is_immutable():
    import pytest
    with pytest.raises(TypeError):
        load_driver()["states"]["attentive"]["takeover_mean_s"] = 99.0
