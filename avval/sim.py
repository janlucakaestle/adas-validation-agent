"""Longitudinal scenario simulator for ACC with driver hand-back.

Scenario (one lane, ego follows one target vehicle):
  lead_brake - target starts at ego speed and, from `lead_brake_onset_s`, brakes with
               `lead_decel` m/s^2 (capped by friction) to a stop.
  cut_in     - target appears at t = 0 travelling `closing_speed` m/s slower, then holds speed.
The initial gap is `headway * ego_speed` in both scenarios.

Ego control stack:
  1. The learned ACC policy commands an acceleration within its authority (sim.yaml `ego`).
  2. A rule-based monitor issues a takeover request (TOR) when the required deceleration
     (`required_decel`) exceeds `tor_required_decel_mps2`, or its TTC drops below `tor_ttc_s`.
  3. After a sampled takeover time (to first input) the driver takes over. After a further
     `brake_onset_delay_s` the driver brakes towards
     min(peak_decel_fraction * mu * g, brake_demand_factor * required deceleration),
     building and releasing brake at `brake_jerk`, and holding at least
     `standstill_hold_decel_mps2` until standstill while a conflict remains. Until then the
     brake level inherited from the ACC is held. Driver parameters: config/driver.yaml.
Friction caps every achievable deceleration, for ego and target alike.

Step ordering (at each step time t, all quantities refer to t):
  1. exogenous current-step quantities: the target's acceleration over [t, t + dt);
  2. monitor state from the current gap, speeds and that acceleration (so a target that
     starts braking at t is visible to the monitor at t, not one step later);
  3. control decisions (TOR, driver, ACC);
  4. exact integration over the step with piecewise-constant accelerations;
  5. event detection inside the step (contact), then termination checks.

Event handling (numerical method). Within a step each vehicle has a constant acceleration
until it stops; a vehicle never reverses. Positions are therefore piecewise quadratic and
are integrated exactly, including a stop part-way through the step. Contact is the first
time in (t, t + dt] at which the gap reaches `contact_gap_m`; it is found as the smallest
root of the piecewise-quadratic gap (closed form per piece, `first_contact`). The collision
time, impact speed and run duration are evaluated at that instant, so a contact in the first
step has a positive duration and an impact speed that is not one step late. Exogenous events
must lie on the step grid (checked in `SimParams`).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from .driver import sample_takeover_time

G = 9.81
_EPS_T = 1e-9
# Speeds (m/s) and accelerations (m/s^2) smaller than this are physically zero. Treating
# them as exactly zero keeps stop times and contact roots finite and identical between the
# scalar and vectorised kinematics (otherwise 1e-40 m/s^2 means "stops after 1e40 s").
_ZERO = 1e-9

END_STATES = ("collision", "both_stopped", "horizon_safe", "horizon_unresolved")


@dataclass(frozen=True)
class SimParams:
    """Simulator parameters, read from a Release (never from module constants)."""
    dt: float
    horizon_s: float
    lead_brake_onset_s: float
    cut_in_onset_s: float
    accel_min: float
    accel_max: float
    actuator_delay_steps: int
    tor_req_decel: float
    tor_ttc_s: float
    ttc_model: str
    detection_delay_steps: int
    margin_m: float
    min_space_m: float
    contact_gap_m: float
    horizon_safe_req: float
    thw_settle_s: float
    jerk_window_s: float
    near_closing: float
    thw_min_speed: float
    driver: object  # frozen driver config

    @classmethod
    def from_release(cls, release) -> "SimParams":
        s = release.sim
        dt = float(s["time"]["dt_s"])
        if not (math.isfinite(dt) and dt > 0):
            raise ValueError("sim.yaml: time.dt_s must be positive")

        def steps(value: float, what: str) -> int:
            k = value / dt
            if value < 0 or abs(k - round(k)) > 1e-9:
                raise ValueError(f"sim.yaml: {what} = {value} must be a non-negative multiple "
                                 f"of dt = {dt} (events are not silently moved to the grid)")
            return int(round(k))

        horizon = float(s["time"]["horizon_s"])
        steps(horizon, "time.horizon_s")
        steps(float(s["scenario"]["lead_brake_onset_s"]), "scenario.lead_brake_onset_s")
        steps(float(s["scenario"]["cut_in_onset_s"]), "scenario.cut_in_onset_s")
        if s["monitor"]["ttc_model"] not in ("constant_speed", "constant_accel"):
            raise ValueError(f"sim.yaml: unknown monitor.ttc_model {s['monitor']['ttc_model']!r}")
        p = cls(
            dt=dt, horizon_s=horizon,
            lead_brake_onset_s=float(s["scenario"]["lead_brake_onset_s"]),
            cut_in_onset_s=float(s["scenario"]["cut_in_onset_s"]),
            accel_min=float(s["ego"]["accel_min_mps2"]),
            accel_max=float(s["ego"]["accel_max_mps2"]),
            actuator_delay_steps=steps(float(s["ego"]["actuator_delay_s"]), "ego.actuator_delay_s"),
            tor_req_decel=float(s["monitor"]["tor_required_decel_mps2"]),
            tor_ttc_s=float(s["monitor"]["tor_ttc_s"]),
            ttc_model=str(s["monitor"]["ttc_model"]),
            detection_delay_steps=steps(float(s["monitor"]["detection_delay_s"]),
                                        "monitor.detection_delay_s"),
            margin_m=float(s["required_decel"]["margin_m"]),
            min_space_m=float(s["required_decel"]["min_space_m"]),
            contact_gap_m=float(s["collision"]["contact_gap_m"]),
            horizon_safe_req=float(s["termination"]["horizon_safe_required_decel_mps2"]),
            thw_settle_s=float(s["metrics"]["thw_settle_s"]),
            jerk_window_s=float(s["metrics"]["jerk_window_s"]),
            near_closing=float(s["metrics"]["near_closing_mps"]),
            thw_min_speed=float(s["metrics"]["thw_min_speed_mps"]),
            driver=release.driver)
        if not p.accel_min < 0 < p.accel_max:
            raise ValueError("sim.yaml: ego authority must satisfy accel_min < 0 < accel_max")
        if p.min_space_m <= 0 or p.margin_m < 0 or p.contact_gap_m < 0:
            raise ValueError("sim.yaml: margins must be non-negative and min_space_m positive")
        return p

    def hazard_onset(self, scenario: str) -> float:
        """When the hazard appears: the lead's braking onset, or the cut-in itself."""
        return self.lead_brake_onset_s if scenario == "lead_brake" else self.cut_in_onset_s


def nominal_params() -> SimParams:
    """Simulator parameters of the nominal configuration (no policy needed)."""
    from .config import Release
    return Release.build(policy_sha256="none").sim_params


@dataclass
class Trace:
    t: np.ndarray
    gap: np.ndarray
    v_ego: np.ndarray
    v_lead: np.ndarray
    a_ego: np.ndarray
    mode: np.ndarray  # 0 = ACC, 1 = TOR pending (ACC still in control), 2 = driver
    a_lead: np.ndarray | None = None  # applied over the same step as a_ego; None = zeros
    req: np.ndarray | None = None     # monitor's required deceleration at each step


# ---------------------------------------------------------------- kinematics
def _z(x: float) -> float:
    return 0.0 if -_ZERO <= x <= _ZERO else x


def stop_time(v: float, a: float) -> float:
    """Time until a vehicle at speed v >= 0 with constant acceleration a stops (inf if never)."""
    v, a = _z(v), _z(a)
    if a < 0.0:
        return v / -a
    return math.inf


def advance(v: float, a: float, dt: float) -> tuple[float, float]:
    """Exact (distance, new speed) over dt with constant a and no reversing."""
    ts = stop_time(v, a)
    if ts >= dt:
        return v * dt + 0.5 * a * dt * dt, max(v + a * dt, 0.0)
    return v * ts + 0.5 * a * ts * ts, 0.0


def _quad_first_root(g0: float, dv: float, da: float, length: float) -> float:
    """Smallest u in (0, length] with g0 + dv*u + da*u^2/2 = 0, given g0 > 0; inf if none."""
    if abs(da) < 1e-12:
        if dv < 0.0:
            u = -g0 / dv
            return u if u <= length else math.inf
        return math.inf
    disc = dv * dv - 2.0 * da * g0
    if disc < 0.0:
        return math.inf
    sq = math.sqrt(disc)
    q = -0.5 * (dv + (sq if dv >= 0.0 else -sq))
    best = math.inf
    for r in ((q / (0.5 * da)), (g0 / q if q != 0.0 else math.inf)):
        if 0.0 < r <= length and r < best:
            best = r
    return best


def first_contact(g: float, v_e: float, a_e: float, v_l: float, a_l: float,
                  t_max: float) -> float | None:
    """First time in (0, t_max] at which the gap reaches 0, or None.

    `g` is the gap above the contact level. Each vehicle keeps its acceleration until it
    stops and then stands still; the gap is piecewise quadratic between the stop times, and
    each piece is solved in closed form.
    """
    if g <= 0.0:
        return 0.0
    v_e, a_e, v_l, a_l = _z(v_e), _z(a_e), _z(v_l), _z(a_l)
    ts_e, ts_l = stop_time(v_e, a_e), stop_time(v_l, a_l)
    breaks = sorted({b for b in (ts_e, ts_l, t_max) if 0.0 < b <= t_max} | {t_max})
    s0, g0 = 0.0, g
    for s1 in breaks:
        length = s1 - s0
        if length <= 0.0:
            continue
        ae = a_e if s0 < ts_e else 0.0
        al = a_l if s0 < ts_l else 0.0
        ve = v_e + a_e * s0 if s0 < ts_e else 0.0
        vl = v_l + a_l * s0 if s0 < ts_l else 0.0
        dv, da = vl - ve, al - ae
        u = _quad_first_root(g0, dv, da, length)
        if u < math.inf:
            return s0 + u
        g0 = g0 + dv * length + 0.5 * da * length * length
        if g0 <= 0.0:  # rounding at a breakpoint
            return s1
        s0 = s1
    return None


def first_contact_vec(g, v_e, a_e, v_l, a_l) -> np.ndarray:
    """Vectorised `first_contact` with t_max = inf; inf where the gap never reaches 0."""
    g, v_e, a_e, v_l, a_l = np.broadcast_arrays(*(np.asarray(x, dtype=float)
                                                  for x in (g, v_e, a_e, v_l, a_l)))
    v_e, a_e, v_l, a_l = (np.where(np.abs(x) <= _ZERO, 0.0, x) for x in (v_e, a_e, v_l, a_l))
    with np.errstate(divide="ignore", invalid="ignore"):
        ts_e = np.where(a_e < 0, v_e / -a_e, np.inf)
        ts_l = np.where(a_l < 0, v_l / -a_l, np.inf)
    t1, t2 = np.minimum(ts_e, ts_l), np.maximum(ts_e, ts_l)
    out = np.full(g.shape, np.inf)
    out[g <= 0] = 0.0
    todo = g > 0
    s0 = np.zeros(g.shape)
    g0 = g.copy()
    for s1 in (t1, t2, np.full(g.shape, np.inf)):
        length = s1 - s0
        moving_e, moving_l = s0 < ts_e, s0 < ts_l
        ae = np.where(moving_e, a_e, 0.0)
        al = np.where(moving_l, a_l, 0.0)
        ve = np.where(moving_e, v_e + a_e * s0, 0.0)
        vl = np.where(moving_l, v_l + a_l * s0, 0.0)
        dv, da = vl - ve, al - ae
        u = _quad_first_root_vec(g0, dv, da, length)
        hit = todo & (length > 0) & np.isfinite(u)
        out[hit] = (s0 + u)[hit]
        todo &= ~hit
        finite = np.isfinite(length)
        with np.errstate(invalid="ignore"):
            g0 = np.where(finite, g0 + dv * length + 0.5 * da * length ** 2, g0)
        s0 = np.where(finite, s1, s0)
    return out


def _quad_first_root_vec(g0, dv, da, length) -> np.ndarray:
    out = np.full(g0.shape, np.inf)
    lin = np.abs(da) < 1e-12
    with np.errstate(divide="ignore", invalid="ignore"):
        u_lin = np.where(dv < 0, -g0 / dv, np.inf)
        out = np.where(lin & (u_lin <= length), u_lin, out)
        disc = dv * dv - 2.0 * da * g0
        ok = ~lin & (disc >= 0)
        sq = np.sqrt(np.where(ok, disc, 0.0))
        q = -0.5 * (dv + np.where(dv >= 0, sq, -sq))
        r1 = np.where(ok, q / (0.5 * da), np.inf)
        r2 = np.where(ok & (q != 0), g0 / np.where(q != 0, q, 1.0), np.inf)
    for r in (r1, r2):
        good = ok & (r > 0) & (r <= length)
        out = np.where(good & (r < out), r, out)
    return out


# ---------------------------------------------------------------- monitor quantities
def required_decel(gap: float, v_ego: float, v_lead: float, a_lead: float,
                   margin_m: float = 2.0, min_space_m: float = 0.1) -> float:
    """Constant ego deceleration needed to end up `margin_m` behind the target.

    The target keeps its current deceleration b = max(-a_lead, 0) until it stops (a positive
    target acceleration counts as 0, which is conservative). With usable space
    s = max(gap - margin, min_space) and closing speed c = v_ego - v_lead:

      b = 0:  c^2 / (2 s) if c > 0, else 0                  (match the target's speed)
      b > 0:  b + c^2 / (2 s) if c > 0 and the speeds match before the target stops
              (2 s / c <= v_lead / b); otherwise v_ego^2 / (2 (s + v_lead^2 / (2 b)))
              (stop behind the target's stopping point).

    The two b > 0 branches agree on their boundary and tend to the b = 0 formula as b -> 0,
    so the result is continuous in the target's acceleration (no threshold switch).
    """
    s = max(gap - margin_m, min_space_m)
    v_ego, v_lead, a_lead = _z(v_ego), _z(v_lead), _z(a_lead)
    b = max(-a_lead, 0.0) if v_lead > 0.0 else 0.0
    c = v_ego - v_lead
    if b > 0.0:
        if c > 0.0 and 2.0 * s / c <= v_lead / b:
            return b + c * c / (2.0 * s)
        return v_ego * v_ego / (2.0 * (s + v_lead * v_lead / (2.0 * b)))
    return c * c / (2.0 * s) if c > 0.0 else 0.0


def initial_conditions(case: dict, g: float = G) -> tuple[float, float, float, float, float]:
    """(v_ego, v_lead, gap, lead_decel, a_fric) at t = 0; lead_decel is already friction-capped."""
    a_fric = case["friction"] * g
    v_ego = case["ego_speed"]
    gap = case["headway"] * v_ego
    if case["scenario"] == "lead_brake":
        return v_ego, v_ego, gap, min(case["lead_decel"], a_fric), a_fric
    return v_ego, max(v_ego - case["closing_speed"], 0.0), gap, 0.0, a_fric


def lead_accel(scenario: str, t: float, v_lead: float, lead_decel: float,
               onset: float) -> float:
    """Target acceleration over [t, t + dt): braking from its onset until it stops."""
    braking = scenario == "lead_brake" and t >= onset - _EPS_T and v_lead > 0.0
    return -lead_decel if braking else 0.0


def _monitor_ttc(p: SimParams, gap, v_ego, v_lead, a_ego_meas, a_lead) -> float:
    if p.ttc_model == "constant_speed":
        closing = v_ego - v_lead
        return gap / closing if closing > p.near_closing else math.inf
    t = first_contact(gap - p.contact_gap_m, v_ego, a_ego_meas, v_lead, a_lead, math.inf)
    return math.inf if t is None else t


# ---------------------------------------------------------------- simulation
def simulate(case: dict, policy, seed: int, params: SimParams | None = None
             ) -> tuple[dict, Trace]:
    """Simulate one case with the given parameters (default: the nominal release).

    Every modelling assumption comes from `params`, which a Campaign takes from its Release;
    there are no keyword overrides that bypass the release identity.
    """
    p = params or nominal_params()
    dt = p.dt
    rng = np.random.default_rng(seed)
    drv = p.driver
    dstate = drv["states"][case["driver_state"]]
    v_ego, v_lead, gap, lead_decel, a_fric = initial_conditions(case)
    v_set = v_ego
    onset = p.hazard_onset(case["scenario"])

    takeover_time = sample_takeover_time(case["driver_state"], rng, drv)
    brake_onset = float(drv["brake_onset_delay_s"])
    peak, demand = float(dstate["peak_decel_fraction"]), float(drv["brake_demand_factor"])
    hold = float(drv["standstill_hold_decel_mps2"])
    brake_step = float(dstate["brake_jerk"]) * dt
    acc_lo, acc_hi = max(p.accel_min, -a_fric), min(p.accel_max, a_fric)

    tor_t, tor_reason, cond_since = None, None, None
    a_ego = 0.0
    driver_brake = 0.0
    pending = deque([0.0] * p.actuator_delay_steps)
    collision, impact_speed, end_state, t_end = False, 0.0, None, None

    n = int(round(p.horizon_s / dt))
    rec = {k: [] for k in ("t", "gap", "v_ego", "v_lead", "a_ego", "mode", "a_lead", "req")}
    a_lead = 0.0
    for i in range(n):
        t = i * dt
        # 1. exogenous, current step
        a_lead = lead_accel(case["scenario"], t, v_lead, lead_decel, onset)
        # 2. monitor, from the current state and the current target acceleration
        req = required_decel(gap, v_ego, v_lead, a_lead, p.margin_m, p.min_space_m)
        ttc = _monitor_ttc(p, gap, v_ego, v_lead, a_ego, a_lead)
        by_req, by_ttc = req > p.tor_req_decel, ttc < p.tor_ttc_s
        if cond_since is None and (by_req or by_ttc):
            cond_since = (i, "both" if by_req and by_ttc else
                          ("required_decel" if by_req else "ttc"))
        # 3. control
        if tor_t is None and cond_since is not None and i >= cond_since[0] + p.detection_delay_steps:
            tor_t, tor_reason = t, cond_since[1]
        driver_in = tor_t is not None and t >= tor_t + takeover_time - _EPS_T
        mode = 2 if driver_in else (1 if tor_t is not None else 0)
        if driver_in:
            if t >= tor_t + takeover_time + brake_onset - _EPS_T:  # effective braking
                target = min(peak * a_fric, demand * req)
                if req > 0.0 and v_ego > 0.0:  # hold the brake until standstill
                    target = max(target, min(hold, peak * a_fric))
                driver_brake += min(max(target - driver_brake, -brake_step), brake_step)
            a_new = -driver_brake
        else:
            cmd = policy.act(gap, v_ego, v_lead - v_ego, v_set,
                             accel_min=acc_lo, accel_max=acc_hi)
            cmd = min(max(float(cmd), acc_lo), acc_hi)
            if p.actuator_delay_steps:
                pending.append(cmd)
                cmd = pending.popleft()
            a_new = cmd
            driver_brake = max(-a_new, 0.0)  # the driver inherits the current brake level
        if v_ego <= 0.0 and a_new < 0.0:
            a_new = 0.0
        a_ego = a_new
        for k, val in zip(rec, (t, gap, v_ego, v_lead, a_ego, mode, a_lead, req)):
            rec[k].append(val)

        # 4-5. exact integration with contact detection inside the step
        g_rel = gap - p.contact_gap_m
        if g_rel <= (v_ego + max(a_ego, 0.0) * dt) * dt:  # contact is possible this step
            tau = first_contact(g_rel, v_ego, a_ego, v_lead, a_lead, dt)
            if tau is not None:
                collision = True
                ve_c = max(v_ego + a_ego * tau, 0.0)
                vl_c = max(v_lead + a_lead * tau, 0.0)
                impact_speed, t_end, end_state = ve_c - vl_c, t + tau, "collision"
                break
        dx_e, v_ego = advance(v_ego, a_ego, dt)
        dx_l, v_lead = advance(v_lead, a_lead, dt)
        gap += dx_l - dx_e
        if v_ego == 0.0 and v_lead == 0.0:
            t_end, end_state = t + dt, "both_stopped"
            break
    if end_state is None:
        t_end = n * dt
        a_end = lead_accel(case["scenario"], t_end, v_lead, lead_decel, onset)
        req_end = required_decel(gap, v_ego, v_lead, a_end, p.margin_m, p.min_space_m)
        end_state = "horizon_safe" if req_end <= p.horizon_safe_req else "horizon_unresolved"

    trace = Trace(**{k: np.array(v, dtype=float) for k, v in rec.items()})
    outcome = {"collision": collision, "impact_speed": impact_speed, "end_state": end_state,
               "t_end": t_end, "tor_t": tor_t, "tor_reason": tor_reason,
               "takeover_time": takeover_time, "hazard_onset_s": onset}
    return compute_metrics(trace, outcome, p), trace


def ttc_with_accel(gap, v_ego, v_lead, a_ego, a_lead) -> np.ndarray:
    """Time to contact if both vehicles keep their current accelerations until they stop
    (vectorised). Unlike the classic constant-acceleration "enhanced TTC", a vehicle that
    would stop before contact stays stopped instead of reversing, so the extrapolated
    contact is physically consistent. inf where the gap never closes."""
    return first_contact_vec(gap, v_ego, a_ego, v_lead, a_lead)


def _finite_min(x: np.ndarray) -> float | None:
    x = x[np.isfinite(x)]
    return float(np.min(x)) if len(x) else None


def _filtered_jerk(a: np.ndarray, w: int, dt: float, valid: np.ndarray | None = None
                   ) -> float | None:
    """Max |d/dt| of the trailing w-sample moving average of a, over windows whose w + 1
    samples are all `valid` (default: all). None if no window qualifies."""
    if len(a) <= w:
        return None
    a_filt = np.convolve(a, np.ones(w) / w, mode="valid")
    jerk = np.abs(np.diff(a_filt)) / dt  # jerk[k] uses samples k .. k + w
    if valid is not None:
        ok = np.convolve(valid.astype(float), np.ones(w + 1), mode="valid") >= w + 1 - 1e-9
        jerk = jerk[ok]
    return float(np.max(jerk)) if len(jerk) else None


def compute_metrics(tr: Trace, outcome: dict, p: SimParams | None = None) -> dict:
    """General-purpose longitudinal driving metrics, computed from a trace.

    The trace holds the state at every step start before contact, so every minimum below
    is taken *before* impact. Collision is reported in its own column, never encoded in
    another metric.

    - min_gap: minimum gap (m); NULL for a collision rather than 0.
    - min_ttc: minimum constant-speed TTC (gap / closing speed). NULL if never closing.
    - min_ttc_accel: minimum stop-aware TTC with current accelerations (`ttc_with_accel`).
    - min_thw: minimum time headway (ego speed above thw_min_speed) from thw_settle_s on.
    - max_jerk: max |d/dt| of the jerk_window_s moving-average acceleration (whole run).
    - max_jerk_automated: the same, over windows lying entirely in automated control
      (ACC commanding: before the driver's first input). NULL if no window qualifies.
    - max_jerk_raw: max |da/dt| from differencing raw samples.
    - max_required_decel: the monitor's largest required deceleration before the TOR (or
      over the whole run without one), for hand-back diagnostics.
    """
    p = p or nominal_params()
    dt = p.dt
    a_lead = tr.a_lead if tr.a_lead is not None else np.zeros_like(tr.a_ego)
    closing = tr.v_ego - tr.v_lead
    with np.errstate(divide="ignore", invalid="ignore"):
        ttc = np.where(closing > p.near_closing, tr.gap / closing, np.inf)
        thw = np.where(tr.v_ego > p.thw_min_speed, tr.gap / tr.v_ego, np.inf)
    ttc_acc = ttc_with_accel(tr.gap - p.contact_gap_m, tr.v_ego, tr.v_lead, tr.a_ego, a_lead)
    thw = thw[tr.t >= p.thw_settle_s - 1e-9]
    jerk_raw = np.abs(np.diff(tr.a_ego)) / dt if len(tr.a_ego) > 1 else np.array([0.0])
    w = int(round(p.jerk_window_s / dt))
    automated = tr.mode < 2
    tor_t = outcome["tor_t"]
    if tr.req is not None and len(tr.req):
        # up to and including the sample that triggered the TOR
        pre = tr.t <= tor_t + 1e-9 if tor_t is not None else np.ones(len(tr.t), bool)
        max_req = float(np.max(tr.req[pre]))
    else:
        max_req = None
    collision = outcome["collision"]
    return {
        "collision": bool(collision),
        "impact_speed": float(outcome["impact_speed"]),
        "collision_time": float(outcome["t_end"]) if collision else None,
        "end_state": outcome["end_state"],
        "hazard_onset_s": float(outcome["hazard_onset_s"]),
        "min_ttc": _finite_min(ttc),
        "min_ttc_accel": _finite_min(ttc_acc),
        "min_thw": _finite_min(thw),
        "min_gap": None if collision else float(np.min(tr.gap)),
        "max_decel": float(max(-np.min(tr.a_ego), 0.0)) if len(tr.a_ego) else 0.0,
        "max_jerk": _filtered_jerk(tr.a_ego, w, dt),
        "max_jerk_automated": _filtered_jerk(tr.a_ego, w, dt, automated),
        "max_jerk_raw": float(np.max(jerk_raw)),
        "max_required_decel": max_req,
        "tor_issued": tor_t is not None,
        "tor_time": float(tor_t) if tor_t is not None else None,
        "tor_reason": outcome["tor_reason"],
        "takeover_time": float(outcome["takeover_time"]) if tor_t is not None else None,
        "duration": float(outcome["t_end"]),
    }
