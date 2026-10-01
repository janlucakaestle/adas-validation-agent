"""Longitudinal scenario simulator for ACC with driver hand-back.

Scenario (one lane, ego follows one target vehicle):
  lead_brake - target starts at ego speed, brakes at t = 1 s with `lead_decel` m/s^2 to a stop.
  cut_in     - target appears travelling `closing_speed` m/s slower, then holds speed.
The initial gap is `headway * ego_speed` in both scenarios.

Ego control stack:
  1. The learned ACC policy commands acceleration within its authority [-3.5, +2.0] m/s^2.
  2. A rule-based monitor issues a takeover request (TOR) when the braking needed to stop
     behind the target (accounting for the target's own deceleration, as a radar would
     estimate it) exceeds 3.0 m/s^2, or TTC drops below 2.0 s.
  3. After a sampled takeover time (to first input) the driver takes over. After a further
     `brake_onset_delay_s` (default 0) the driver brakes towards
     min(peak_decel_fraction * mu * g, brake_demand_factor x needed braking), building and
     releasing brake at `brake_jerk`. Until then the brake level inherited from the ACC is held.
     All driver parameters come from config/driver.yaml (per state where it matters).
Friction caps every achievable deceleration, for ego and target alike.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import load_driver
from .driver import sample_takeover_time
from .policy import ACCEL_MAX, ACCEL_MIN, LearnedACC

G = 9.81
DT = 0.05
HORIZON_S = 20.0
TOR_REQ_DECEL = 3.0     # m/s^2: needed braking above this -> hand back
TOR_TTC_S = 2.0
LEAD_BRAKE_ONSET_S = 1.0
THW_SETTLE_S = 2.0       # min_thw ignores the first 2 s (see compute_metrics)
JERK_WINDOW_S = 0.5      # moving-average window for the filtered jerk metric


@dataclass
class Trace:
    t: np.ndarray
    gap: np.ndarray
    v_ego: np.ndarray
    v_lead: np.ndarray
    a_ego: np.ndarray
    mode: np.ndarray  # 0 = ACC, 1 = TOR pending, 2 = driver
    a_lead: np.ndarray | None = None  # applied over the same step as a_ego; None = zeros


def required_decel(gap: float, v_ego: float, v_lead: float, a_lead: float) -> float:
    """Constant ego deceleration needed to end up stopped/matched 2 m behind the target."""
    space = gap - 2.0
    if a_lead < -0.5:  # target braking: compare stopping distances
        space += v_lead ** 2 / (2 * -a_lead)
        return v_ego ** 2 / (2 * max(space, 0.1))
    closing = v_ego - v_lead
    return closing ** 2 / (2 * max(space, 0.1)) if closing > 0 else 0.0


def initial_conditions(case: dict) -> tuple[float, float, float, float, float]:
    """(v_ego, v_lead, gap, lead_decel, a_fric) at t = 0; lead_decel is already friction-capped.
    The initial gap is the case's time headway times ego speed."""
    a_fric = case["friction"] * G
    v_ego = case["ego_speed"]
    gap = case["headway"] * v_ego
    if case["scenario"] == "lead_brake":
        return v_ego, v_ego, gap, min(case["lead_decel"], a_fric), a_fric
    return v_ego, max(v_ego - case["closing_speed"], 0.0), gap, 0.0, a_fric


def hazard_onset(case: dict) -> float:
    """When the hazard appears: cut-in at t = 0, lead braking at its braking onset."""
    return LEAD_BRAKE_ONSET_S if case["scenario"] == "lead_brake" else 0.0


def lead_accel(case: dict, t: float, v_lead: float, lead_decel: float) -> float:
    braking = case["scenario"] == "lead_brake" and t >= LEAD_BRAKE_ONSET_S and v_lead > 0
    return -lead_decel if braking else 0.0


def integrate(gap: float, v_ego: float, v_lead: float, a_ego: float, a_lead: float,
              dt: float) -> tuple[float, float, float]:
    """One step: Euler on speed (clamped at 0), trapezoidal rule on the gap."""
    v_ego_new = max(v_ego + a_ego * dt, 0.0)
    v_lead_new = max(v_lead + a_lead * dt, 0.0)
    gap += (v_lead + v_lead_new) / 2 * dt - (v_ego + v_ego_new) / 2 * dt
    return gap, v_ego_new, v_lead_new


def simulate(case: dict, policy: LearnedACC, seed: int,
             driver_cfg: dict | None = None, dt: float = DT,
             acc_authority: float | None = None,
             tor_req_decel: float = TOR_REQ_DECEL) -> tuple[dict, Trace]:
    """Simulate one case. The keyword arguments override modelling assumptions, for
    sensitivity analysis and verification; their defaults are the nominal model:
      driver_cfg     config/driver.yaml contents;
      dt             integration step;
      acc_authority  ACC braking authority in m/s^2 (default -ACCEL_MIN = 3.5);
      tor_req_decel  needed braking above which the monitor hands back (m/s^2).
    """
    accel_min = ACCEL_MIN if acc_authority is None else -acc_authority
    rng = np.random.default_rng(seed)
    drv = driver_cfg or load_driver()
    dstate = drv["states"][case["driver_state"]]
    v_ego, v_lead, gap, lead_decel, a_fric = initial_conditions(case)
    v_set = v_ego

    takeover_time = sample_takeover_time(case["driver_state"], rng, drv)
    brake_onset = drv["brake_onset_delay_s"]
    tor_t = None
    a_ego = 0.0
    a_lead = 0.0
    driver_brake = 0.0
    collision, impact_speed = False, 0.0

    n = int(round(HORIZON_S / dt))
    rec = {k: [] for k in ("t", "gap", "v_ego", "v_lead", "a_ego", "mode", "a_lead")}
    for i in range(n):
        t = i * dt
        closing = v_ego - v_lead
        ttc = gap / closing if closing > 1e-3 else np.inf
        req = required_decel(gap, v_ego, v_lead, a_lead)

        # --- hand-back monitor ---
        if tor_t is None and (req > tor_req_decel or ttc < TOR_TTC_S):
            tor_t = t
        driver_in = tor_t is not None and t >= tor_t + takeover_time
        mode = 2 if driver_in else (1 if tor_t is not None else 0)

        # --- control ---
        if driver_in:
            if t >= tor_t + takeover_time + brake_onset:  # effective braking
                target = (min(dstate["peak_decel_fraction"] * a_fric,
                              drv["brake_demand_factor"] * req)
                          if (closing > 0 or a_lead < -0.5) else 0.0)
                step = dstate["brake_jerk"] * dt
                driver_brake += float(np.clip(target - driver_brake, -step, step))
            a_new = -driver_brake
        else:
            cmd = (policy.act(gap, v_ego, v_lead - v_ego, v_set) if acc_authority is None
                   else policy.act(gap, v_ego, v_lead - v_ego, v_set, accel_min=accel_min))
            a_new = float(np.clip(cmd, max(accel_min, -a_fric), ACCEL_MAX))
            driver_brake = max(-a_new, 0.0)  # driver inherits the current brake level
        if v_ego <= 0 and a_new < 0:
            a_new = 0.0
        a_ego = a_new

        for k, val in zip(rec, (t, gap, v_ego, v_lead, a_ego, mode)):
            rec[k].append(val)

        # --- integrate ---
        a_lead = lead_accel(case, t, v_lead, lead_decel)
        rec["a_lead"].append(a_lead)
        gap, v_ego, v_lead = integrate(gap, v_ego, v_lead, a_ego, a_lead, dt)

        if gap <= 0.0:
            collision, impact_speed = True, v_ego - v_lead
            break
        if v_ego == 0.0 and v_lead == 0.0:
            break

    trace = Trace(**{k: np.array(v) for k, v in rec.items()})
    return compute_metrics(trace, collision, impact_speed, tor_t, takeover_time, dt), trace


def ttc_with_accel(gap, v_ego, v_lead, a_ego, a_lead) -> np.ndarray:
    """Time to collision assuming both vehicles keep their current accelerations (vectorised).

    The gap evolves as  d(tau) = gap + dv * tau + 0.5 * da * tau^2,  with
    dv = v_lead - v_ego and da = a_lead - a_ego. TTC is the smallest tau > 0 with d(tau) = 0:

      da = 0:  tau = gap / -dv                      if dv < 0, else no collision (inf)
      da != 0: tau = (-dv -/+ sqrt(dv^2 - 2 * da * gap)) / da, smallest positive root;
               no real root (dv^2 < 2 * da * gap) means the gap never closes (inf).

    Like the usual "enhanced TTC", it extrapolates constant acceleration and ignores that a
    vehicle stops rather than reversing. When the lead would stop before contact this
    underestimates TTC (conservative).
    """
    gap, dv, da = (np.asarray(x, dtype=float) for x in (gap, np.subtract(v_lead, v_ego),
                                                       np.subtract(a_lead, a_ego)))
    gap, dv, da = np.broadcast_arrays(gap, dv, da)
    out = np.full(gap.shape, np.inf)
    lin = np.abs(da) < 1e-9
    closing = lin & (dv < 0)
    out[closing] = gap[closing] / -dv[closing]
    quad = ~lin
    disc = dv ** 2 - 2 * da * gap
    ok = quad & (disc >= 0)
    root = np.sqrt(np.where(ok, disc, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        r1 = np.where(ok, (-dv - root) / da, np.inf)
        r2 = np.where(ok, (-dv + root) / da, np.inf)
    r1 = np.where(r1 > 0, r1, np.inf)
    r2 = np.where(r2 > 0, r2, np.inf)
    out[quad] = np.minimum(r1, r2)[quad]
    return out


def _finite_min(x: np.ndarray) -> float | None:
    x = x[np.isfinite(x)]
    return float(np.min(x)) if len(x) else None


def compute_metrics(tr: Trace, collision: bool, impact_speed: float,
                    tor_t: float | None, takeover_time: float, dt: float = DT) -> dict:
    """General-purpose longitudinal driving metrics, computed from a trace.

    The trace ends at the last sample before impact, so every minimum below is taken
    *before* impact. Collision is reported in its own column, never encoded in another metric.

    - min_gap: minimum gap (m); NULL for a collision rather than 0.
    - min_ttc: minimum constant-speed TTC (gap / closing speed). NULL if the vehicles never close.
    - min_ttc_accel: minimum TTC with both vehicles' current accelerations (`ttc_with_accel`).
      NULL if the gap never closes under that extrapolation.
    - min_thw: minimum time headway (gap / ego speed, ego speed > 1 m/s) from t = THW_SETTLE_S
      on. The initial gap is a test input (a cut-in can start at 0.3 s), not something the
      system chose, so headway is only judged after the ACC has had 2 s to respond. NULL if
      no sample qualifies (short run, or ego below 1 m/s throughout).
    - max_jerk: max |d/dt| of acceleration after a trailing JERK_WINDOW_S moving average.
      That equals the largest change of acceleration over any 0.5 s window divided by 0.5 s,
      so it does not depend on the step size dt. NULL for runs shorter than the window.
    - max_jerk_raw: max |da/dt| from differencing raw samples, i.e. step / dt (kept for comparison).
    """
    a_lead = tr.a_lead if tr.a_lead is not None else np.zeros_like(tr.a_ego)
    closing = tr.v_ego - tr.v_lead
    with np.errstate(divide="ignore", invalid="ignore"):
        ttc = np.where(closing > 1e-3, tr.gap / closing, np.inf)
        thw = np.where(tr.v_ego > 1.0, tr.gap / tr.v_ego, np.inf)
    ttc_acc = ttc_with_accel(tr.gap, tr.v_ego, tr.v_lead, tr.a_ego, a_lead)
    thw = thw[tr.t >= THW_SETTLE_S - 1e-9]
    jerk_raw = np.abs(np.diff(tr.a_ego)) / dt if len(tr.a_ego) > 1 else np.array([0.0])
    w = int(round(JERK_WINDOW_S / dt))
    if len(tr.a_ego) > w:
        a_filt = np.convolve(tr.a_ego, np.ones(w) / w, mode="valid")
        max_jerk = float(np.max(np.abs(np.diff(a_filt)) / dt))
    else:
        max_jerk = None
    return {
        "collision": bool(collision),
        "impact_speed": float(impact_speed),
        "min_ttc": _finite_min(ttc),
        "min_ttc_accel": _finite_min(ttc_acc),
        "min_thw": _finite_min(thw),
        "min_gap": None if collision else float(np.min(tr.gap)),  # collision has its own column
        "max_decel": float(max(-np.min(tr.a_ego), 0.0)),
        "max_jerk": max_jerk,
        "max_jerk_raw": float(np.max(jerk_raw)),
        "tor_issued": tor_t is not None,
        "tor_time": float(tor_t) if tor_t is not None else None,
        "takeover_time": float(takeover_time) if tor_t is not None else None,
        "duration": float(tr.t[-1]) if len(tr.t) else 0.0,
    }
