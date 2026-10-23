"""Verification of the simulator against closed-form results.

The integrator advances each vehicle exactly under piecewise-constant acceleration,
including a stop part-way through a step (no reversing), so positions, speeds and gaps are
exact between control decisions. The analytic checks below therefore hold to floating-point
round-off (TOL), not to an integration-error bound. Contact is the exact root of the
piecewise-quadratic gap inside the step.

To isolate the physics from the learned policy, most checks drive the ego vehicle with a
constant-acceleration stand-in for the ACC policy.
"""
import itertools

import numpy as np
import pytest

from avval.config import Release
from avval.sim import G, nominal_params, simulate

P = nominal_params()
DT = P.dt
ONSET = P.lead_brake_onset_s
TOL = 1e-9


class ConstantPolicy:
    """Stand-in for the learned ACC: always commands the same acceleration."""

    def __init__(self, accel: float):
        self.accel = accel

    def act(self, gap, v, rel_v, v_set, **_):
        return self.accel


def cut_in(v, closing, gap, driver="attentive", friction=1.0):
    return dict(scenario="cut_in", ego_speed=v, closing_speed=closing, headway=gap / v,
                friction=friction, driver_state=driver)


def lead_brake(v, decel, gap, driver="attentive", friction=1.0):
    return dict(scenario="lead_brake", ego_speed=v, lead_decel=decel, headway=gap / v,
                friction=friction, driver_state=driver)


def test_constant_deceleration_stops_in_v2_over_2a_exactly():
    v0, a = 31.0, 3.0
    # Lead drives away at constant speed, so the ego never needs a hand-back.
    m, tr = simulate(cut_in(v0, 1.0, 80.0), ConstantPolicy(-a), seed=0)
    assert not m["tor_issued"] and not m["collision"] and tr.v_ego[-1] == 0.0
    v_lead = v0 - 1.0
    ego_distance = v_lead * tr.t[-1] - (tr.gap[-1] - tr.gap[0])
    assert ego_distance == pytest.approx(v0 ** 2 / (2 * a), abs=1e-8)  # stop mid-step, exact


def test_lead_braking_above_friction_limit_is_capped_at_mu_g():
    v0, mu = 15.0, 0.5
    m, tr = simulate(lead_brake(v0, 9.0, 80.0, friction=mu), ConstantPolicy(-3.5), seed=0)
    braking = tr.a_lead != 0
    assert braking.any()
    assert np.allclose(tr.a_lead[braking], -mu * G, atol=TOL)  # 4.9 m/s^2, not 9
    expected_v = np.maximum(v0 - mu * G * np.maximum(tr.t - ONSET, 0.0), 0.0)
    assert np.allclose(tr.v_lead, expected_v, atol=1e-8)


def test_equal_speeds_without_braking_keep_the_gap_constant():
    # closing_speed = 0 is outside the ODD, so call simulate() directly (no validate_case).
    m, tr = simulate(cut_in(25.0, 0.0, 30.0), ConstantPolicy(0.0), seed=0)
    assert not m["tor_issued"] and m["min_ttc"] is None
    assert len(tr.t) == int(round(P.horizon_s / DT)) and m["end_state"] == "horizon_safe"
    assert m["duration"] == pytest.approx(P.horizon_s)
    assert np.max(np.abs(tr.gap - 30.0)) < TOL


def test_cut_in_gap_closes_at_closing_speed_before_any_ego_reaction():
    v0, closing, gap0 = 30.0, 5.0, 40.0
    m, tr = simulate(cut_in(v0, closing, gap0), ConstantPolicy(0.0), seed=0)
    assert m["tor_issued"]  # the driver does react eventually...
    before = np.arange(len(tr.t)) < np.argmax(tr.a_ego != 0)  # ...but check only before that
    assert before.sum() > 100
    assert np.allclose(tr.gap[before], gap0 - closing * tr.t[before], atol=1e-8)


def test_lead_brake_follows_analytic_lead_position():
    v0, a_lead, a_ego, gap0 = 20.0, 3.0, 2.0, 40.0
    m, tr = simulate(lead_brake(v0, a_lead, gap0), ConstantPolicy(-a_ego), seed=0)
    assert not m["tor_issued"] and not m["collision"]

    def position(t, v, a, t0=0.0):  # constant speed until t0, then brake at a to a stop
        tb = np.clip(t - t0, 0.0, v / a)
        return v * np.minimum(t, t0) + v * tb - 0.5 * a * tb ** 2

    x_ego = position(tr.t, v0, a_ego)
    x_lead = x_ego + tr.gap - gap0
    assert np.allclose(x_lead, position(tr.t, v0, a_lead, ONSET), atol=1e-8)
    assert tr.v_lead[-1] == 0.0  # the lead stop is inside the checked window


def test_collision_time_and_impact_speed_are_at_the_exact_crossing():
    """A cut-in 2 m ahead closing at 9 m/s, with no ego reaction, makes contact at
    t = 2/9 s (inside the fifth step) with an impact speed of exactly 9 m/s."""
    m, tr = simulate(cut_in(20.0, 9.0, 2.0, driver="distracted"), ConstantPolicy(0.0), seed=0)
    assert m["collision"] and m["end_state"] == "collision"
    assert m["collision_time"] == pytest.approx(2 / 9, abs=1e-12)
    assert m["duration"] == m["collision_time"]
    assert m["impact_speed"] == pytest.approx(9.0, abs=1e-12)
    assert tr.t[-1] < m["collision_time"] <= tr.t[-1] + DT  # inside the last recorded step


def test_collision_in_the_first_step_has_a_positive_duration():
    m, tr = simulate(cut_in(20.0, 9.0, 0.3, driver="distracted"), ConstantPolicy(0.0), seed=0)
    assert m["collision"] and len(tr.t) == 1
    assert m["duration"] == pytest.approx(0.3 / 9) and m["duration"] > 0


def test_impact_speed_accounts_for_braking_inside_the_step():
    """Ego braking at 3.5 m/s^2 into a stationary-relative gap: the impact speed at the exact
    crossing is the analytic one, not the speed one step later."""
    v0, closing, gap0, a = 20.0, 9.0, 8.0, 3.5
    m, _ = simulate(cut_in(v0, closing, gap0, driver="distracted"), ConstantPolicy(-a), seed=0)
    # relative motion: gap0 - closing t + a t^2 / 2 = 0 (no stops before contact here)
    t = (closing - np.sqrt(closing ** 2 - 2 * a * gap0)) / a
    assert m["collision_time"] == pytest.approx(t, abs=1e-9)
    assert m["impact_speed"] == pytest.approx(closing - a * t, abs=1e-9)


# ---- Convergence: halve the step size on a fixed case set -------------------------------
# The full closed loop (learned policy, monitor, driver) runs here. Kinematics are exact, so
# the remaining dt-dependence comes from discrete control decisions (TOR, first driver
# input, policy and driver updates), which are quantised to the step and can move by up to
# one coarse step DT when dt halves. Bounds derived from that:
#   - TOR time: |change| <= DT;
#   - collision outcome and end state: at most 1 of 144 cases may differ (a case exactly on
#     a boundary can legitimately flip; more would mean outcomes depend on dt);
#   - min_ttc: |change| <= 2 DT for every collision-free case, median <= 0.01 s;
#   - collision time: |change| <= 2 DT; impact speed: |change| <= G * DT (one step of
#     braking at the friction limit).
CONVERGENCE_CASES = [
    (lead_brake if s == "lead_brake" else cut_in)(v, sev, g, drv, mu)
    for s, v, g, sev, mu, drv in itertools.product(
        ["lead_brake", "cut_in"], [20.0, 32.0], [10.0, 30.0, 60.0], [2.0, 5.0, 8.0],
        [0.5, 1.0], ["attentive", "distracted"])]


def test_halving_dt_changes_outcomes_within_tolerance(policy):
    fine = Release.build(policy, overrides={"sim": {"time": {"dt_s": DT / 2}}}).sim_params
    flips, ends, d_ttc, d_impact, d_tc, d_tor = 0, 0, [], [], [], []
    for seed, case in enumerate(CONVERGENCE_CASES):
        a, _ = simulate(case, policy, seed)
        b, _ = simulate(case, policy, seed, fine)
        ends += a["end_state"] != b["end_state"]
        if a["tor_issued"] and b["tor_issued"]:
            d_tor.append(abs(a["tor_time"] - b["tor_time"]))
        if a["collision"] != b["collision"]:
            flips += 1
        elif a["collision"]:
            d_impact.append(abs(a["impact_speed"] - b["impact_speed"]))
            d_tc.append(abs(a["collision_time"] - b["collision_time"]))
        elif a["min_ttc"] is not None:
            d_ttc.append(abs(a["min_ttc"] - b["min_ttc"]))
    assert len(CONVERGENCE_CASES) == 144
    assert flips <= 1 and ends <= 1
    assert max(d_tor) <= DT + 1e-9
    assert max(d_ttc) <= 2 * DT and np.median(d_ttc) <= 0.01
    assert d_tc and max(d_tc) <= 2 * DT
    assert all(d <= G * DT for d in d_impact)


def test_a_step_that_does_not_divide_the_event_times_is_rejected(policy):
    with pytest.raises(ValueError, match="multiple of dt"):
        Release.build(policy, overrides={"sim": {"time": {"dt_s": 0.03}}})
