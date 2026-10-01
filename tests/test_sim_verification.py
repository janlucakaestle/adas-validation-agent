"""Verification of the simulator against closed-form results.

The integrator updates speed with explicit Euler (v += a * dt) and the gap with the
trapezoidal rule on speed. With piecewise-constant acceleration this is *exact* between
events, so on the analytic cases below the only error comes from events that fall inside
a step. The one such event here is a vehicle coming to a stop mid-step, where the speed
clamp at zero over-counts distance by at most a * dt^2 / 8 per stop (worst case: the stop
falls mid-step). Tolerances are stated from that bound, plus 1e-9 for floating-point
round-off.

To isolate the physics from the learned policy, most checks drive the ego vehicle with a
constant-acceleration stand-in for the ACC policy.
"""
import itertools

import numpy as np
import pytest

from avval.sim import DT, G, LEAD_BRAKE_ONSET_S, simulate

EPS = 1e-9


class ConstantPolicy:
    """Stand-in for the learned ACC: always commands the same acceleration."""

    def __init__(self, accel: float):
        self.accel = accel

    def act(self, gap, v, rel_v, v_set):
        return self.accel


def stop_tol(*decels, dt=DT):
    """Worst-case distance error from vehicles stopping mid-step: sum of a * dt^2 / 8."""
    return sum(a * dt ** 2 / 8 for a in decels) + EPS


def cut_in(v, closing, gap, driver="attentive", friction=1.0):
    return dict(scenario="cut_in", ego_speed=v, closing_speed=closing, headway=gap / v,
                friction=friction, driver_state=driver)


def lead_brake(v, decel, gap, driver="attentive", friction=1.0):
    return dict(scenario="lead_brake", ego_speed=v, lead_decel=decel, headway=gap / v,
                friction=friction, driver_state=driver)


def test_constant_deceleration_stops_in_v2_over_2a():
    v0, a = 31.0, 3.0
    # Lead drives away at constant speed, so the ego never needs a hand-back.
    m, tr = simulate(cut_in(v0, 1.0, 80.0), ConstantPolicy(-a), seed=0)
    assert not m["tor_issued"] and not m["collision"] and tr.v_ego[-1] == 0.0
    v_lead = v0 - 1.0
    ego_distance = v_lead * tr.t[-1] - (tr.gap[-1] - tr.gap[0])  # lead distance minus gap change
    assert ego_distance == pytest.approx(v0 ** 2 / (2 * a), abs=stop_tol(a))


def test_lead_braking_above_friction_limit_is_capped_at_mu_g():
    v0, mu = 15.0, 0.5
    m, tr = simulate(lead_brake(v0, 9.0, 80.0, friction=mu), ConstantPolicy(-3.5), seed=0)
    braking = tr.a_lead != 0
    assert braking.any()
    assert np.allclose(tr.a_lead[braking], -mu * G, atol=EPS)  # 3.92 m/s^2, not 9
    expected_v = np.maximum(v0 - mu * G * np.maximum(tr.t - LEAD_BRAKE_ONSET_S, 0.0), 0.0)
    assert np.allclose(tr.v_lead, expected_v, atol=EPS)


def test_equal_speeds_without_braking_keep_the_gap_constant():
    # closing_speed = 0 is outside the ODD, so call simulate() directly (no validate_case).
    m, tr = simulate(cut_in(25.0, 0.0, 30.0), ConstantPolicy(0.0), seed=0)
    assert not m["tor_issued"] and m["min_ttc"] is None
    assert len(tr.t) == 400  # ran to the 20 s horizon
    assert np.max(np.abs(tr.gap - 30.0)) < EPS


def test_cut_in_gap_closes_at_closing_speed_before_any_ego_reaction():
    v0, closing, gap0 = 30.0, 5.0, 40.0
    m, tr = simulate(cut_in(v0, closing, gap0), ConstantPolicy(0.0), seed=0)
    assert m["tor_issued"]  # the driver does react eventually...
    before = np.arange(len(tr.t)) < np.argmax(tr.a_ego != 0)  # ...but check only before that
    assert before.sum() > 100
    assert np.allclose(tr.gap[before], gap0 - closing * tr.t[before], atol=EPS)


def test_lead_brake_follows_analytic_lead_position():
    v0, a_lead, a_ego, gap0 = 20.0, 3.0, 2.0, 40.0
    m, tr = simulate(lead_brake(v0, a_lead, gap0), ConstantPolicy(-a_ego), seed=0)
    assert not m["tor_issued"] and not m["collision"]

    def position(t, v, a, t0=0.0):  # constant speed until t0, then brake at a to a stop
        tb = np.clip(t - t0, 0.0, v / a)
        return v * np.minimum(t, t0) + v * tb - 0.5 * a * tb ** 2

    x_ego = position(tr.t, v0, a_ego)
    x_lead = x_ego + tr.gap - gap0
    assert np.allclose(x_lead, position(tr.t, v0, a_lead, LEAD_BRAKE_ONSET_S),
                       atol=stop_tol(a_lead, a_ego))
    assert tr.v_lead[-1] == 0.0  # the lead stop is inside the checked window


# ---- Convergence: halve the step size on a fixed case set -------------------------------
# The full closed loop (learned policy, hand-back monitor, driver) runs here. Discrete events
# (TOR, first driver input, policy updates) are quantised to the step, so they can move by up
# to one step when dt halves. Tolerances:
#   - min_ttc: |change| <= 2 * DT = 0.1 s for every collision-free case (an event shift of one
#     step changes the minimum by at most about that much), and median |change| <= 0.01 s;
#   - collision outcome: at most 1 of the 144 cases may flip (a case that sits exactly on the
#     collision boundary can legitimately flip; more would mean the outcome depends on dt);
#   - impact speed, where both collide: |change| <= G * DT, about 0.5 m/s, i.e. one step of
#     braking at the friction limit.
CONVERGENCE_CASES = [
    (lead_brake if s == "lead_brake" else cut_in)(v, sev, g, drv, mu)
    for s, v, g, sev, mu, drv in itertools.product(
        ["lead_brake", "cut_in"], [20.0, 32.0], [10.0, 30.0, 60.0], [2.0, 5.0, 8.0],
        [0.5, 1.0], ["attentive", "distracted"])]


def test_halving_dt_changes_outcomes_within_tolerance(policy):
    flips, d_ttc, d_impact = 0, [], []
    for seed, case in enumerate(CONVERGENCE_CASES):
        a, _ = simulate(case, policy, seed)
        b, _ = simulate(case, policy, seed, dt=DT / 2)
        if a["collision"] != b["collision"]:
            flips += 1
        elif a["collision"]:
            d_impact.append(abs(a["impact_speed"] - b["impact_speed"]))
        else:
            d_ttc.append(abs(a["min_ttc"] - b["min_ttc"]))
    assert len(CONVERGENCE_CASES) == 144
    assert flips <= 1
    assert max(d_ttc) <= 2 * DT and np.median(d_ttc) <= 0.01
    assert all(d <= G * DT for d in d_impact)
