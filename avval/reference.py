"""Reference responses replayed on every run's scenario (config/reference.yaml).

A reference is a fixed, brake-only, longitudinal ego response: hold the initial speed until
hazard onset (no pre-hazard intervention), wait a reaction time, build braking (instantly or
jerk-limited) to a deceleration level and hold it until stopped. It uses the simulator's
lead-vehicle model, exact piecewise kinematics and contact definition (avval/sim.py), with
perfect knowledge of the hazard at onset. Its result depends only on the scenario, never on
what the system under test did or on its design parameters, so it can define acceptance
populations without conditioning on the system.

Results stored per run:
- avoidable_by_reference: the ideal reference (0.9 mu g from hazard onset by default)
  avoids contact. FALSE means only that this particular response does not avoid it, not
  that the collision is physically unavoidable (earlier, harder or lateral responses may).
- handback_required: the hand-back oracle (braking at a FIXED deceleration, the nominal
  system's design authority frozen in reference.yaml handback_oracle.decel_mps2, from hazard
  onset) does NOT avoid contact. It depends neither on the system's actions nor on the
  configured design under test (e.g. a variant's authority), so the populations it defines
  stay comparable across design variants.
- ccd_avoidable_by_reference: the careful-competent-driver reference; NULL while disabled.
"""
from __future__ import annotations

import math

from .sim import SimParams, advance, first_contact, initial_conditions


def _segment(state, a_e: float, a_l: float, length: float):
    """Advance (gap, v_e, v_l) over `length` with constant accelerations (no reversing);
    None if contact happens within the segment."""
    g, v_e, v_l = state
    if length <= 0:
        return state
    if first_contact(g, v_e, a_e, v_l, a_l, length) is not None:
        return None
    if math.isinf(length):
        return state  # both stopped or diverging: nothing further can happen
    dx_e, v_e2 = advance(v_e, a_e, length)
    dx_l, v_l2 = advance(v_l, a_l, length)
    return g + dx_l - dx_e, v_e2, v_l2


def reference_collides(case: dict, params: SimParams, decel_mps2: float,
                       reaction_time_s: float = 0.0, jerk_mps3: float | None = None) -> bool:
    """Replay `case` with the reference ego response; True if contact occurs.

    The deceleration level is capped at the friction limit mu * g.
    """
    v_e, v_l, gap, lead_decel, a_fric = initial_conditions(case)
    decel = min(float(decel_mps2), a_fric)
    onset = params.hazard_onset(case["scenario"])
    a_lead_after = -lead_decel if case["scenario"] == "lead_brake" else 0.0
    start = onset + reaction_time_s
    state = (gap - params.contact_gap_m, v_e, v_l)
    # Constant speed until hazard onset, then (lead braking) until the reference reacts.
    state = _segment(state, 0.0, 0.0, onset)
    if state is not None:
        state = _segment(state, 0.0, a_lead_after, start - onset)
    if state is None:
        return True
    if jerk_mps3 is not None and jerk_mps3 > 0:  # jerk-limited build-up, step by step
        brake, dt = 0.0, params.dt
        while brake < decel - 1e-12:
            brake = min(decel, brake + jerk_mps3 * dt)
            state = _segment(state, -brake, a_lead_after, dt)
            if state is None:
                return True
    return _segment(state, -decel, a_lead_after, math.inf) is None


class References:
    """The reference responses of one release, evaluated per scenario case."""

    def __init__(self, release):
        self.params = release.sim_params
        ref = release.reference
        ideal = ref["ideal"]
        self.ideal = (float(ideal["decel_fraction_of_mu_g"]), float(ideal["reaction_time_s"]),
                      ideal["jerk_mps3"])
        ho = ref["handback_oracle"]
        cap = ho.get("decel_mps2")
        if not isinstance(cap, (int, float)) or cap <= 0:
            raise ValueError("reference.yaml: handback_oracle.decel_mps2 must be a positive "
                             "fixed capability (it must not depend on the system under test)")
        self.capability = float(cap)
        self.handback = (float(ho["reaction_time_s"]), ho["jerk_mps3"])
        ccd = ref["careful_competent_driver"]
        self.ccd = None
        if ccd.get("enabled"):
            missing = [k for k in ("decel_fraction_of_mu_g", "reaction_time_s")
                       if ccd.get(k) is None]
            if missing:
                raise ValueError(f"reference.yaml: careful_competent_driver is enabled but "
                                 f"{missing} are not set (TODO(data))")
            self.ccd = (float(ccd["decel_fraction_of_mu_g"]), float(ccd["reaction_time_s"]),
                        ccd["jerk_mps3"])

    def _mu_g(self, case: dict) -> float:
        return initial_conditions(case)[4]

    def ideal_avoids(self, case: dict) -> bool:
        frac, react, jerk = self.ideal
        return not reference_collides(case, self.params, frac * self._mu_g(case), react, jerk)

    def handback_required(self, case: dict) -> bool:
        react, jerk = self.handback
        return reference_collides(case, self.params, self.capability, react, jerk)

    def ccd_avoids(self, case: dict) -> bool | None:
        if self.ccd is None:
            return None
        frac, react, jerk = self.ccd
        return not reference_collides(case, self.params, frac * self._mu_g(case), react, jerk)

    def evaluate(self, case: dict) -> dict:
        return {"avoidable_by_reference": self.ideal_avoids(case),
                "handback_required": self.handback_required(case),
                "ccd_avoidable_by_reference": self.ccd_avoids(case)}
