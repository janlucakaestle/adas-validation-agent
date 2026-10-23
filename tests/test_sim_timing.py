"""Event ordering, contact roots, continuity and terminal states of the simulator."""
import math

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from avval.config import Release
from avval.sim import (first_contact, first_contact_vec, nominal_params, required_decel,
                       simulate)

P = nominal_params()


class ConstantPolicy:
    def __init__(self, accel):
        self.accel = accel

    def act(self, gap, v, rel_v, v_set, **_):
        return self.accel


def test_lead_braking_is_visible_to_the_monitor_at_its_onset_step():
    """The lead starts braking at t = 1.0 s. At that same step the monitor must already use
    the lead's deceleration: the required deceleration jumps at t = 1.0 (not 1.05) and the
    TOR is issued at t = 1.0."""
    case = dict(scenario="lead_brake", ego_speed=30.0, lead_decel=9.0, headway=1.0,
                friction=1.0, driver_state="attentive")
    m, tr = simulate(case, ConstantPolicy(0.0), seed=0)
    i = int(round(P.lead_brake_onset_s / P.dt))
    assert tr.a_lead[i] == -9.0 and tr.a_lead[i - 1] == 0.0
    assert tr.req[i - 1] == 0.0 and tr.req[i] > P.tor_req_decel  # same step, not one later
    assert m["tor_time"] == pytest.approx(P.lead_brake_onset_s, abs=1e-12)
    assert m["tor_reason"] == "required_decel"


def test_tor_timing_does_not_depend_on_dt_for_an_onset_event(policy):
    case = dict(scenario="lead_brake", ego_speed=30.0, lead_decel=9.0, headway=1.0,
                friction=1.0, driver_state="attentive")
    fine = Release.build(policy, overrides={"sim": {"time": {"dt_s": 0.025}}}).sim_params
    assert simulate(case, policy, 0)[0]["tor_time"] == simulate(case, policy, 0, fine)[0]["tor_time"] == 1.0


def test_monitor_detection_delay_is_applied(policy):
    case = dict(scenario="lead_brake", ego_speed=30.0, lead_decel=9.0, headway=1.0,
                friction=1.0, driver_state="attentive")
    slow = Release.build(policy, overrides={"sim": {"monitor": {"detection_delay_s": 0.3}}})
    assert simulate(case, policy, 0, slow.sim_params)[0]["tor_time"] == pytest.approx(1.3)


def test_actuator_delay_shifts_the_acc_command(policy):
    case = dict(scenario="cut_in", ego_speed=30.0, closing_speed=6.0, headway=1.2,
                friction=1.0, driver_state="attentive")
    lag = Release.build(policy, overrides={"sim": {"ego": {"actuator_delay_s": 0.2}}}).sim_params
    _, a = simulate(case, policy, 0)
    _, b = simulate(case, policy, 0, lag)
    k = int(round(0.2 / P.dt))
    assert np.all(b.a_ego[:k] == 0.0) and b.a_ego[k] == pytest.approx(a.a_ego[0])


def test_unresolved_horizon_is_not_reported_as_safe(policy):
    """Shorten the horizon so a hard lead-braking conflict is still running at the end."""
    case = dict(scenario="lead_brake", ego_speed=30.0, lead_decel=9.0, headway=1.0,
                friction=1.0, driver_state="distracted")
    short = Release.build(policy, overrides={"sim": {"time": {"horizon_s": 1.5}}}).sim_params
    m, _ = simulate(case, policy, 0, short)
    assert not m["collision"] and m["end_state"] == "horizon_unresolved"
    assert m["duration"] == pytest.approx(1.5)


# ---- required deceleration ---------------------------------------------------------------
def test_required_decel_reference_values():
    # constant-speed target, closing 10 m/s, usable space 23 m -> 100 / 46
    assert required_decel(25.0, 30.0, 20.0, 0.0) == pytest.approx(100 / 46)
    # stopped target: stop within the space
    assert required_decel(52.0, 20.0, 0.0, 0.0) == pytest.approx(400 / 100)
    # equal speeds, target braking at 6: stop behind its stopping point: v^2/(2(s + v^2/12))
    assert required_decel(32.0, 30.0, 30.0, -6.0) == pytest.approx(900 / (2 * (30 + 75)))
    assert required_decel(30.0, 20.0, 25.0, 0.0) == 0.0  # opening, no braking target


@given(gap=st.floats(0.0, 120.0), v_e=st.floats(0.0, 40.0), v_l=st.floats(0.01, 40.0),
       a_l=st.floats(-10.0, 0.0))
@settings(max_examples=300, deadline=None)
def test_required_decel_is_continuous_in_the_target_acceleration(gap, v_e, v_l, a_l):
    """No threshold switch: a tiny change in the target's acceleration gives a tiny change
    in the required deceleration (the old code jumped at a_lead = -0.5)."""
    eps = 1e-7
    a = required_decel(gap, v_e, v_l, a_l)
    b = required_decel(gap, v_e, v_l, a_l - eps)
    assert abs(a - b) <= 1e-3 * max(1.0, a)


@given(gap=st.floats(3.0, 120.0), v_e=st.floats(0.0, 40.0), v_l=st.floats(0.0, 40.0),
       a_l=st.floats(-10.0, 0.0))
@settings(max_examples=300, deadline=None)
def test_required_decel_braking_is_sufficient_and_necessary(gap, v_e, v_l, a_l):
    """Braking at exactly the required deceleration keeps the gap above margin - 1 mm;
    braking 5% less does not (when anything at all is required)."""
    assume(v_e == 0 or v_e > 1e-3)  # below 1 mm/s the needed decel is physically zero
    d = required_decel(gap, v_e, v_l, a_l)
    margin = P.margin_m
    hit = first_contact(gap - margin + 1e-3, v_e, -d, v_l, a_l, math.inf)
    assert hit is None
    if d > 0.05:
        assert first_contact(gap - margin - 1e-3, v_e, -0.95 * d, v_l, a_l, math.inf) is not None


# ---- contact roots ------------------------------------------------------------------------
# Physically meaningful ranges, derived from the ODD (config/odd.yaml) with a generous margin:
# initial gaps up to 3.0 s x 36 m/s = 108 m (-> 160 m); speeds up to 36 m/s (-> 45 m/s);
# braking up to mu*g <= 9.81 m/s^2 (-> 12 m/s^2); ACC acceleration up to 2 m/s^2 (-> 3 m/s^2);
# contact times within three simulation horizons (20 s -> 60 s), so positions stay below
# 45 m/s x 60 s = 2.7 km. Contacts later than that never occur in a run; the old unbounded
# test met one after ~8e9 s at ~3e10 m, where double rounding alone exceeds any mm tolerance.
GAP_M, SPEED_MPS, BRAKE_MPS2, ACCEL_MPS2, T_PHYS_S = 160.0, 45.0, 12.0, 3.0, 60.0
# Absolute, not scaled with position: within these ranges a direct stress test of 900,000
# cases (uniform and edge values, incl. +-1e-9) gave a worst residual of 9e-13 m.
RESIDUAL_M = 1e-9


def _pos(v0, a, t):
    """Exact travelled distance, stopping (not reversing) at v = 0, under the model's
    convention that |x| <= 1e-9 is physically zero (without it, an acceleration of exactly
    1e-9 m/s^2 moves the oracle by 1.25 um after 50 s, which is the convention, not rounding)."""
    from avval.sim import _z
    v0, a = _z(v0), _z(a)
    ts = v0 / -a if a < 0 else math.inf
    tt = min(t, ts)
    return v0 * tt + 0.5 * a * tt * tt


@given(g=st.floats(0.01, GAP_M), v_e=st.floats(0.0, SPEED_MPS),
       a_e=st.floats(-BRAKE_MPS2, ACCEL_MPS2), v_l=st.floats(0.0, SPEED_MPS),
       a_l=st.floats(-BRAKE_MPS2, ACCEL_MPS2))
@settings(max_examples=400, deadline=None)
def test_scalar_and_vector_contact_roots_agree_and_are_roots(g, v_e, a_e, v_l, a_l):
    s = first_contact(g, v_e, a_e, v_l, a_l, T_PHYS_S)
    v = float(first_contact_vec(g, v_e, a_e, v_l, a_l))
    assume(abs(v - T_PHYS_S) > 1e-6)  # a contact exactly at the window edge is ambiguous
    if s is None:
        assert v > T_PHYS_S  # no contact in the window (inf = never)
        return
    assert v == pytest.approx(s, rel=1e-9, abs=1e-9)
    assert g + _pos(v_l, a_l, s) - _pos(v_e, a_e, s) == pytest.approx(0.0, abs=RESIDUAL_M)
    for frac in (0.25, 0.5, 0.9):  # no earlier contact
        t = frac * s
        assert g + _pos(v_l, a_l, t) - _pos(v_e, a_e, t) > -1e-9


# The 1e-9 "physically zero" threshold of avval/sim.py is INCLUSIVE (a model decision, see
# REMEDIATION_SUMMARY.md, v4 Part B): |x| <= 1e-9 is exactly zero, anything larger is not.
@pytest.mark.parametrize("a, zero", [(1e-9, True), (-1e-9, True), (0.0, True),
                                     (2e-9, False), (-2e-9, False), (1.0000001e-9, False)])
def test_zero_threshold_is_inclusive_on_each_side(a, zero):
    from avval.sim import _z, stop_time
    assert (_z(a) == 0.0) is zero
    # a speed of 1 m/s with a deceleration on either side of the threshold
    ts = stop_time(1.0, a)
    if zero or a > 0:
        assert ts == math.inf
    else:
        assert ts == pytest.approx(1.0 / -a)
    # speeds: 1e-9 m/s is standing still, 2e-9 m/s is not
    assert stop_time(1e-9, -1.0) == 0.0 and stop_time(2e-9, -1.0) == pytest.approx(2e-9)


def test_zero_threshold_contact_roots_on_each_side():
    """Closing at exactly 0 m/s: a lead acceleration of -1e-9 m/s^2 is zero (never touches);
    -2e-9 m/s^2 is a real (if absurdly slow) closing, found by scalar and vector roots alike;
    the threshold applies identically to both implementations."""
    g = 1.0
    assert first_contact(g, 10.0, 0.0, 10.0, -1e-9, math.inf) is None
    assert math.isinf(float(first_contact_vec(g, 10.0, 0.0, 10.0, -1e-9)))
    # lead speed 10 m/s decelerating at 2e-9 stops after 5e9 s, long after travelling > 1 m less
    t = first_contact(g, 10.0, 0.0, 10.0, -2e-9, math.inf)
    assert t == pytest.approx(math.sqrt(2 * g / 2e-9), rel=1e-6)
    assert float(first_contact_vec(g, 10.0, 0.0, 10.0, -2e-9)) == pytest.approx(t, rel=1e-9)
    # the same pair inside a physical window: no contact within 60 s either way
    assert first_contact(g, 10.0, 0.0, 10.0, -2e-9, T_PHYS_S) is None
