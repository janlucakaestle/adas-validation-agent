"""The driver model is configured in config/driver.yaml, per state where it matters."""
import copy

from avval.config import load_driver, load_odd
from avval.provenance import provenance
from avval.sim import simulate

STATES = load_odd()["parameters"]["driver_state"]["values"]
# Hand-back cases (harsh lead braking), plus one gentle case with no hand-back.
CASES = [dict(scenario="lead_brake", ego_speed=30.0, headway=g / 30.0, lead_decel=d, friction=1.0)
         for g, d in ((10.0, 8.0), (25.0, 6.0), (40.0, 5.0), (40.0, 2.0))]


def _metrics(policy, driver_cfg=None):
    return {(s, i, seed): simulate({**c, "driver_state": s}, policy, seed, driver_cfg)[0]
            for s in STATES for i, c in enumerate(CASES) for seed in range(3)}


def test_per_state_change_affects_only_that_state(policy):
    base = _metrics(policy)
    cfg = copy.deepcopy(load_driver())
    cfg["states"]["distracted"].update(takeover_mean_s=3.0, brake_jerk=5.0,
                                         peak_decel_fraction=0.5)
    changed = _metrics(policy, cfg)
    for key in base:
        if key[0] == "distracted":
            continue
        assert changed[key] == base[key], key
    phone = [k for k in base if k[0] == "distracted"]
    assert any(changed[k] != base[k] for k in phone)


def test_brake_onset_delay_postpones_braking_not_first_input(policy):
    case = {**CASES[1], "driver_state": "attentive"}
    cfg = copy.deepcopy(load_driver())
    cfg["brake_onset_delay_s"] = 0.5
    base, delayed = simulate(case, policy, 0)[0], simulate(case, policy, 0, cfg)[0]
    assert base["tor_issued"] and delayed["takeover_time"] == base["takeover_time"]
    assert delayed != base
    gentle = {**CASES[3], "driver_state": "attentive"}  # no hand-back -> unaffected
    assert simulate(gentle, policy, 0, cfg)[0] == simulate(gentle, policy, 0)[0]


def test_driver_config_is_in_provenance():
    assert "driver.yaml" in provenance()["config_sha256"]


def test_assumed_values_carry_todo_markers():
    from avval import CONFIG_DIR
    lines = (CONFIG_DIR / "driver.yaml").read_text(encoding="utf-8").splitlines()
    for key in ("brake_onset_delay_s", "brake_demand_factor",
                "peak_decel_fraction", "brake_jerk"):
        assert all("TODO(data)" in ln for ln in lines if ln.strip().startswith(key + ":")), key
