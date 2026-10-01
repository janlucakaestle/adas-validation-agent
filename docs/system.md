# System under test and simulation

## System definition

- **Function:** Adaptive Cruise Control with a driver-intervention request, called a
  takeover request (TOR) in the code (e.g. `tor_issued`).
- **Automation level:** SAE Level 2. Reference framework: UNECE R171 (DCAS).
- **Driver responsibility:** the driver supervises at all times and is the fallback. The
  system never performs a minimal-risk manoeuvre; it hands back by requesting intervention.
- **System under test:** a learned longitudinal policy, treated as a black box. The ODD,
  criteria, campaigns and agent run unchanged against any policy with the same interface:
  gap, speed, relative speed and set speed in; acceleration out.
- **Not included:** AEB, lateral control, minimal-risk manoeuvre, driver monitoring. So the
  distracted-driver state represents misuse that driver monitoring didn't prevent.
- **Perception:** ideal. The controller sees the true gap, speeds and lead deceleration.
- **UN R157** (Level 3) appears only as the source of an optional *careful and competent
  human driver* benchmark (`config/reference.yaml`).

## Scenarios and ODD

- **Scenarios:** single-lane longitudinal dynamics. `lead_brake`: the lead brakes to a
  stop at `lead_decel` m/s². `cut_in`: a vehicle appears ahead, closing at
  `closing_speed` m/s. Both range 1–9. Each scenario takes only its own parameter; the
  other is rejected and stored as NULL. Coverage bins each scenario on its own parameter.
- **Initial gap as time headway:** 0.8–3.0 s for `lead_brake`, 0.3–2.0 s for `cut_in`
  (placeholders, `TODO(data)`). Initial gap = `headway × ego_speed`; both are stored. This
  excludes impossible starts (5 m at 36 m/s) while allowing short gaps at low speed.
- **Friction:** 0.5 (wet) to 1.0 (dry); ice and snow are outside the ODD. Friction caps
  all achievable deceleration, for ego and lead.

## Design values of the function

- **Policy:** a 32×32 MLP behaviour-cloned from the Intelligent Driver Model on nominal
  driving logs. Its error is larger on harsh, out-of-distribution states (`train` prints
  both). Actuator authority −3.5 to +2.0 m/s², deliberately no AEB.
- **Hand-back monitor:** issues a TOR when the braking needed to stop behind the target
  (including the target's own deceleration) exceeds 3.0 m/s², or TTC < 2 s.

## Metrics

Computed in `avval/sim.py::compute_metrics` from the trace up to the last sample before
impact. Collision is its own column and is never encoded in another metric.

- `min_gap`: minimum gap in metres; NULL for a collision.
- `min_ttc`: minimum gap ÷ closing speed before impact; NULL (not a sentinel) when the
  vehicles never close.
- `min_ttc_accel`: TTC with both vehicles' current accelerations, the smallest positive
  root of gap + Δv·τ + ½Δa·τ² = 0 (Δv = v_lead − v_ego, Δa = a_lead − a_ego). It sees a
  braking lead before speeds diverge. Like the usual "enhanced TTC" it ignores vehicles
  coming to a stop, which is conservative there.
- `min_thw`: minimum time headway from t = 2 s on, so a 0.3 s cut-in doesn't fail headway
  by construction.
- `max_jerk`: largest change in 0.5 s trailing-average acceleration over any 0.5 s,
  divided by 0.5 s; independent of the 20 Hz step. `max_jerk_raw` keeps the raw
  sample-difference value.
- AC-02 is evaluated on collision-free runs only (AC-01 and AC-03 own collisions). Runs that
  never close count as infinite TTC.

## Preventability

Some collisions can't be avoided by any system, e.g. a cut-in 5 m ahead closing at 9 m/s
on a wet road. Every colliding run is replayed with an **ideal reference** (`avval/reference.py`)
using the same lead model and integrator, braking at 0.9 μg the moment the hazard appears,
with no authority limit and no hand-back. If the reference also collides, the run is
`preventable = FALSE`. A run the system avoided is always preventable, since a system can
brake *before* the hazard when headway is already short, and the reference doesn't.

- AC-01 and AC-03 count preventable runs only.
- AC-06 reports the unpreventable share as information.
- The optional careful-competent-driver reference (UN R157 style) is disabled; its
  parameters are `TODO(data)`.

In the seed-0 300-run random and grid campaigns, none of the 13 and 16 collisions was
unpreventable. In the 100,000-run estimation, 1 of 486 was.

## Driver model

Two states, parameters in `config/driver.yaml`. Each state has a `category`
(`intended_use` or `foreseeable_misuse`), stored per run as `driver_category`.

| State | Mean | SD | Floor | Source | What the source measured |
| --- | --- | --- | --- | --- | --- |
| `attentive` (intended use) | 1.3 s | 0.5 s | 0.5 s | Mean: Green (2000), consistent with Summala (2000). SD: CV ≈ 0.35–0.37 (Johansson & Rumar, 1971; Magister et al., 2005). | Brake reaction time to an unexpected event, eyes on the road |
| `distracted` (foreseeable misuse) | 4.59 s | 1.33 s | 1.77 s (`TODO(data)`) | Kästle, Anvari, Peters, Krol & Wurdemann (2025), IEEE Transactions on Haptics (visual and audio TOR) | Urgent takeovers after a reading task: stationary obstacle at ≈ 7 s TTC, 70 mph, time to first meaningful input |

- **Sampling:** log-normal matched to mean and SD. Draws below the floor are redrawn, not
  clipped. The redraw is capped, and hitting the cap raises an error.
- **Timing:** both states start reacting at the TOR. An attentive L2 driver would often
  react at hazard onset, before the TOR, so attentive-driver results (AC-01) are
  **pessimistic** (see the roadmap).
- **Distracted-source caveats:** the study was a Level 3 setting where reading was
  permitted, used here as Level 2 misuse; n = 19, reading task only; reaction times capped
  at 7 s (biases the mean slightly low); hazard first seen at ≈ 7 s TTC, whereas the
  simulator's TOR usually fires closer.
- **Assumption:** reaction times are independent of speed across 15–36 m/s; the source
  was measured at 70 mph.
- **Still placeholders:** distracted floor, `brake_onset_delay_s` (0 s),
  `brake_demand_factor` (1.5 × needed braking), and per state `peak_decel_fraction`
  (0.9 μg) and `brake_jerk` (25 m/s³).

## Simulator verification

`tests/test_sim_verification.py` checks the physics against closed-form results, mostly with
a constant-acceleration stand-in for the policy. Speed uses explicit Euler and the gap the
trapezoidal rule; with piecewise-constant acceleration this is exact between events, so the
only error comes from a vehicle stopping mid-step, bounded by a·dt²/8 (≈ 0.001 m at
3 m/s², 20 Hz).

- Constant deceleration from v stops in v²/2a.
- A lead braking harder than μg is capped at μg and follows the analytic ramp.
- Equal speeds with no braking keep the gap constant (to 1e-9 m).
- A cut-in gap closes at exactly closing speed × t until the ego reacts.
- A lead braking from t = 1 s follows the analytic position curve to its stop.

A convergence check runs the full closed loop on 144 fixed cases at dt and dt/2: `min_ttc`
moves by at most 0.1 s (median ≤ 0.01 s), at most one collision outcome flips, and impact
speed changes by at most g·dt. Deliberate one-line integrator bugs (Euler gap, no friction
cap, lead braking one step late, 2% closing-speed error) are each caught.
