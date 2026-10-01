"""Reference controllers: would an idealised response have avoided the collision?

A collision that even an ideal system braking at the friction limit from the moment the
hazard appears cannot avoid (e.g. a cut-in 5 m ahead closing at 9 m/s on a wet road) says
nothing about the function under test. Such runs are marked unpreventable and excluded
from the collision criteria, and their share is reported separately (AC-06).

The references reuse the simulator's lead-vehicle model and integrator, so a difference in
outcome can only come from the ego response. Parameters live in config/reference.yaml.

The ideal reference is the best case among ego responses that start braking at the hazard.
It is not a bound on responses that brake *earlier*: when a lead_brake case starts at a
headway that is already short, the ACC brakes from t = 0 and can avoid a collision that
the reference (waiting for the lead's braking onset at t = 1 s) does not. A run is
therefore preventable if the system avoided the collision OR the reference does; only
collisions are replayed.
"""
from __future__ import annotations

from .config import load_reference
from .sim import DT, HORIZON_S, hazard_onset, initial_conditions, integrate, lead_accel


def reference_collides(case: dict, decel_fraction_of_mu_g: float, reaction_time_s: float = 0.0,
                       jerk_mps3: float | None = None, dt: float = DT) -> bool:
    """Replay `case` with an ego that holds speed until hazard onset + reaction time, then
    brakes (jerk-limited, or instantly if jerk is None) to decel_fraction * mu * g until it
    stops. Returns True if the gap reaches zero."""
    v_ego, v_lead, gap, lead_decel, a_fric = initial_conditions(case)
    decel = decel_fraction_of_mu_g * a_fric
    start = hazard_onset(case) + reaction_time_s
    brake = 0.0
    for i in range(int(round(HORIZON_S / dt))):
        t = i * dt
        if t >= start - 1e-9:
            brake = decel if jerk_mps3 is None else min(decel, brake + jerk_mps3 * dt)
        a_ego = -brake if v_ego > 0 else 0.0
        a_lead = lead_accel(case, t, v_lead, lead_decel)
        gap, v_ego, v_lead = integrate(gap, v_ego, v_lead, a_ego, a_lead, dt)
        if gap <= 0.0:
            return True
        if v_ego == 0.0:  # stopped: the lead only moves forward, so the gap cannot shrink
            return False
    return False


def _params(block: dict) -> dict:
    return {k: block[k] for k in ("decel_fraction_of_mu_g", "reaction_time_s", "jerk_mps3")}


def ideal_preventable(case: dict) -> bool:
    """True unless the ideal friction-limited reference also collides."""
    return not reference_collides(case, **_params(load_reference()["ideal"]))


def ccd_preventable(case: dict, avoided: bool = False) -> bool | None:
    """Careful-competent-driver reference, or None while it is disabled (the default).
    `avoided=True` (the system itself avoided the collision) short-circuits to True."""
    ccd = load_reference()["careful_competent_driver"]
    if not ccd.get("enabled"):
        return None
    params = _params(ccd)
    missing = [k for k in ("decel_fraction_of_mu_g", "reaction_time_s") if params[k] is None]
    if missing:
        raise ValueError(f"reference.yaml: careful_competent_driver is enabled but {missing} "
                         "are not set (TODO(data))")
    return avoided or not reference_collides(case, **params)
