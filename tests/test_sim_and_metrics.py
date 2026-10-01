import numpy as np
import pytest

from avval.config import validate_case
from avval.sim import DT, Trace, compute_metrics, simulate, ttc_with_accel

BASE = dict(scenario="lead_brake", ego_speed=30.0, headway=40.0 / 30.0, lead_decel=2.0, friction=1.0,
            driver_state="attentive")


def test_gentle_braking_is_handled_without_handback(policy):
    m, _ = simulate(BASE, policy, seed=0)
    assert not m["collision"] and not m["tor_issued"]


def test_harsh_braking_triggers_handback(policy):
    m, _ = simulate({**BASE, "headway": 10.0 / 30.0, "lead_decel": 8.0}, policy, seed=0)
    assert m["tor_issued"]


def test_distraction_is_worse_than_attention(policy):
    case = {**BASE, "headway": 1.0, "lead_decel": 6.0}
    att = np.mean([simulate(case, policy, s)[0]["collision"] for s in range(20)])
    dis = np.mean([simulate({**case, "driver_state": "distracted"}, policy, s)[0]["collision"]
                   for s in range(20)])
    assert dis > att


def test_simulation_is_deterministic_given_seed(policy):
    assert simulate(BASE, policy, 7)[0] == simulate(BASE, policy, 7)[0]


def _trace(gap, v_ego, v_lead, a_ego, a_lead=None):
    n = len(gap)
    return Trace(t=np.arange(n) * DT, gap=np.asarray(gap, float), v_ego=np.asarray(v_ego, float),
                 v_lead=np.asarray(v_lead, float), a_ego=np.asarray(a_ego, float),
                 mode=np.zeros(n), a_lead=None if a_lead is None else np.asarray(a_lead, float))


def test_metrics_on_hand_built_trace():
    tr = _trace([20.0, 15.0, 10.0, 12.0], [20.0] * 4, [10.0, 10.0, 10.0, 25.0],
                [0.0, -1.0, -1.0, 0.0])
    m = compute_metrics(tr, False, 0.0, None, 1.0)
    assert m["min_ttc"] == pytest.approx(1.0)       # 10 m / 10 m/s
    # sample 2: 10 - 10 tau + 0.5 tau^2 = 0 (ego braking at 1 m/s^2 buys time)
    assert m["min_ttc_accel"] == pytest.approx(10 - np.sqrt(80))
    assert m["max_jerk_raw"] == pytest.approx(1.0 / DT)
    assert m["max_decel"] == pytest.approx(1.0)
    assert m["min_gap"] == pytest.approx(10.0)
    assert m["min_thw"] is None and m["max_jerk"] is None  # run shorter than 2 s / 0.5 s


def test_min_ttc_is_null_when_never_closing():
    tr = _trace([30.0] * 5, [20.0] * 5, [22.0] * 5, [0.0] * 5)
    m = compute_metrics(tr, False, 0.0, None, 1.0)
    assert m["min_ttc"] is None and m["min_ttc_accel"] is None


def test_min_ttc_is_taken_before_impact(policy):
    m, tr = simulate({**BASE, "headway": 6.0 / 30.0, "lead_decel": 9.0, "driver_state": "distracted"},
                     policy, seed=0)
    assert m["collision"]
    closing = tr.v_ego - tr.v_lead
    assert m["min_ttc"] == pytest.approx(np.min(tr.gap[closing > 0] / closing[closing > 0]))
    assert 0 < m["min_ttc"] < 1.5
    assert m["min_gap"] is None  # collision is in its own column, not encoded as a 0 gap


@pytest.mark.parametrize("gap, v_ego, v_lead, a_ego, a_lead, expected", [
    (20.0, 20.0, 20.0, 0.0, -5.0, np.sqrt(8.0)),   # equal speeds, lead brakes: 2.5 tau^2 = 20
    (12.0, 25.0, 20.0, 1.0, -1.0, (-5 + np.sqrt(73)) / 2),  # 12 - 5 tau - tau^2 = 0
    (30.0, 30.0, 20.0, -1.0, 1.0, np.inf),          # 30 - 10 tau + tau^2 has no real root
    (20.0, 30.0, 20.0, 0.0, 0.0, 2.0),              # no relative accel: gap / closing speed
    (20.0, 20.0, 30.0, 0.0, 0.0, np.inf),           # opening, no accel
])
def test_ttc_with_accel_matches_analytic(gap, v_ego, v_lead, a_ego, a_lead, expected):
    got = ttc_with_accel(np.array([gap]), np.array([v_ego]), np.array([v_lead]),
                         np.array([a_ego]), np.array([a_lead]))[0]
    assert got == pytest.approx(expected)


def test_ttc_with_accel_flags_braking_lead_that_plain_ttc_misses():
    n = 5
    tr = _trace([20.0] * n, [20.0] * n, [20.0] * n, [0.0] * n, a_lead=[-5.0] * n)
    m = compute_metrics(tr, False, 0.0, None, 1.0)
    assert m["min_ttc"] is None                      # equal speeds: plain TTC sees no danger
    assert m["min_ttc_accel"] == pytest.approx(np.sqrt(8.0))


def test_min_thw_ignores_the_first_two_seconds():
    n = int(4.0 / DT)
    gap = np.where(np.arange(n) * DT < 2.0, 5.0, 30.0)  # close cut-in, then opened up
    tr = _trace(gap, [20.0] * n, [20.0] * n, [0.0] * n)
    assert compute_metrics(tr, False, 0.0, None, 1.0)["min_thw"] == pytest.approx(1.5)


def test_filtered_jerk_measures_change_over_half_a_second():
    n = 60
    a = np.where(np.arange(n) >= 30, -3.0, 0.0)  # instant 3 m/s^2 brake step
    m = compute_metrics(_trace([30.0] * n, [20.0] * n, [20.0] * n, a), False, 0.0, None, 1.0)
    assert m["max_jerk_raw"] == pytest.approx(3.0 / DT)  # 60 m/s^3: depends on DT
    assert m["max_jerk"] == pytest.approx(3.0 / 0.5)     # 6 m/s^3: step spread over 0.5 s
    ramp = np.clip(-np.arange(n) * DT * 2.0, -3.0, 0.0)  # smooth 2 m/s^3 ramp
    m = compute_metrics(_trace([30.0] * n, [20.0] * n, [20.0] * n, ramp), False, 0.0, None, 1.0)
    assert m["max_jerk"] == pytest.approx(2.0) and m["max_jerk_raw"] == pytest.approx(2.0)


def test_odd_validation_rejects_out_of_range():
    with pytest.raises(ValueError):
        validate_case({**BASE, "friction": 0.2})
    with pytest.raises(ValueError):
        validate_case({**BASE, "driver_state": "asleep"})


def test_scenario_parameters_are_not_interchangeable():
    cut_in = {**BASE, "scenario": "cut_in", "closing_speed": 5.0}
    del cut_in["lead_decel"]
    assert validate_case(BASE)["closing_speed"] is None
    assert validate_case(cut_in)["lead_decel"] is None
    with pytest.raises(ValueError, match="closing_speed applies only to scenario 'cut_in'"):
        validate_case({**BASE, "closing_speed": 5.0})
    with pytest.raises(ValueError, match="lead_decel applies only to scenario 'lead_brake'"):
        validate_case({**cut_in, "lead_decel": 5.0})
    with pytest.raises(ValueError, match="missing parameter closing_speed"):
        validate_case({**cut_in, "closing_speed": None})
    with pytest.raises(ValueError, match="replaced"):
        validate_case({**BASE, "severity": 2.0})


def test_friction_below_the_wet_road_floor_is_rejected():
    with pytest.raises(ValueError, match=r"friction=0.45 outside ODD range \[0.5, 1.0\]"):
        validate_case({**BASE, "friction": 0.45})
    assert validate_case({**BASE, "friction": 0.5})["friction"] == 0.5


def test_headway_ranges_are_per_scenario_and_gap_is_rejected():
    with pytest.raises(ValueError, match="'gap' .* was replaced by 'headway'"):
        validate_case({**BASE, "gap": 40.0})
    with pytest.raises(ValueError, match=r"headway=0.3 outside ODD range \[0.8, 3.0\] for lead_brake"):
        validate_case({**BASE, "headway": 0.3})
    cut_in = {**BASE, "scenario": "cut_in", "closing_speed": 5.0, "headway": 0.3}
    del cut_in["lead_decel"]
    assert validate_case(cut_in)["headway"] == 0.3


def test_sampled_start_states_respect_the_headway(store, policy):
    from avval.campaign import Campaign, random_case
    camp = Campaign("h", store, policy, 200)
    camp.run([random_case(camp.rng) for _ in range(200)])
    df = store.query("SELECT scenario, ego_speed, headway, initial_gap_m FROM runs", "h",
                     max_rows=10**9)
    assert np.allclose(df.initial_gap_m, df.headway * df.ego_speed)
    lb = df[df.scenario == "lead_brake"]
    assert len(lb) and (lb.initial_gap_m >= 0.8 * lb.ego_speed - 1e-9).all()
