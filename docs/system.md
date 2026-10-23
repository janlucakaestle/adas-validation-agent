# System under test and simulation

## System definition

- **Function:** Adaptive Cruise Control with a driver-intervention request, called a
  takeover request (TOR) in the code (e.g. `tor_issued`).
- **Automation level:** SAE Level 2. Reference framework: UNECE R171 (DCAS).
- **Driver responsibility:** the driver supervises at all times and is the fallback. The
  system never performs a minimal-risk manoeuvre; it hands back by requesting intervention.
- **System under test:** a 32×32 MLP behaviour-cloned from a synthetic expert (the
  Intelligent Driver Model) on synthetic nominal-following states. It takes four
  ground-truth scalars (gap, speed, relative speed, set speed) and outputs an acceleration.
  It has **no** perception, sensor noise, temporal model, uncertainty estimate, lateral
  behaviour or runtime out-of-distribution handling. It is a **demonstrator and testbed for
  the validation method**; results obtained with it do not transfer to production learned
  ADAS stacks. The ODD, criteria, campaigns and searchers run unchanged against any policy
  with the same interface.
- **Not included:** AEB, lateral control, minimal-risk manoeuvre, driver monitoring. The
  distracted-driver state represents misuse that driver monitoring didn't prevent.
- **UN R157** (Level 3) appears only as the source of an optional *careful and competent
  human driver* reference (`config/reference.yaml`, disabled).

## Scenarios and ODD (`config/odd.yaml`)

- `lead_brake`: the lead brakes from `lead_brake_onset_s` (sim.yaml, 1.0 s) at `lead_decel`
  (capped by μg) to a stop. `cut_in`: a vehicle is present from t = 0, `closing_speed` m/s
  slower. Each scenario takes only its own parameter.
- Initial gap = `headway × ego_speed`; headway 0.8–3.0 s (lead_brake), 0.3–2.0 s (cut_in).
- Friction 0.5 (wet) to 1.0 (dry). Friction caps every deceleration, ego and lead.

## Design values of the function (`config/sim.yaml`)

All semantically relevant constants are release configuration, not literals:

| Parameter | Value | Meaning |
| --- | --- | --- |
| `ego.accel_min_mps2`, `accel_max_mps2` | −3.5, +2.0 | ACC actuator authority |
| `ego.actuator_delay_s` | 0 | command-to-effect delay (TODO(data)) |
| `monitor.tor_required_decel_mps2` | 3.0 | TOR when required deceleration exceeds it |
| `monitor.tor_ttc_s`, `ttc_model` | 2.0, constant_speed | TOR when monitor TTC falls below it |
| `monitor.detection_delay_s` | 0 | monitor latency (TODO(data)) |
| `required_decel.margin_m`, `min_space_m` | 2.0, 0.1 | residual gap and usable-space floor |
| `collision.contact_gap_m` | 0 | contact definition |
| `termination.horizon_safe_required_decel_mps2` | 3.5 | classifies runs that reach the horizon |
| `time.dt_s`, `horizon_s` | 0.05, 20 | step and horizon |

## Simulator method (`avval/sim.py`)

**Step ordering.** At each step time t: (1) exogenous quantities for [t, t+dt), i.e. the
lead's acceleration; (2) monitor quantities from the current gap, speeds and that
acceleration; (3) control decisions (TOR, driver, ACC); (4) exact integration; (5) contact
detection and termination. A lead that starts braking at t is visible to the monitor at t
(v0.2 used the previous step's lead acceleration, one step late).

**Integration.** Accelerations are constant within a step; each vehicle moves exactly
(piecewise quadratic, stopping without reversing part-way through the step). Positions,
speeds and gaps are exact between control decisions.

**Contact.** Contact is the first root in (t, t+dt] of the piecewise-quadratic gap, solved
in closed form per piece (`first_contact`). Collision time, impact speed and duration are
evaluated at that instant; a contact in the first step has a positive duration. Exogenous
events must lie on the step grid (a dt that does not divide them is rejected). Speeds and
accelerations below 1e-9 are treated as exactly zero, to keep stop times finite.

**Required deceleration.** The constant ego deceleration that ends `margin_m` behind the
target, given the target's current deceleration b (kept until it stops): with usable space
s and closing speed c, `b + c²/2s` if the speeds match before the target stops, else
`v_ego²/2(s + v_lead²/2b)`; for b = 0, `c²/2s`. The branches agree on their boundary and tend
to the b = 0 formula, so the quantity is continuous in the target's acceleration (v0.2
switched formulas at a_lead = −0.5 m/s²). Property-tested for continuity, sufficiency and
necessity.

**Terminal states** (`end_state`): `collision`; `both_stopped`; `horizon_safe` (at the
horizon the ACC alone could still resolve the conflict); `horizon_unresolved` (it could not).
Acceptance criteria treat `horizon_unresolved` as adverse, never as safe.

## Metrics

Computed from the trace before contact; collision is its own column.

- `min_gap`; `min_ttc` (constant-speed); `min_ttc_accel`: TTC extrapolating both vehicles'
  current accelerations **until they stop** (v0.2's version let a stopping lead reverse,
  which produced spurious low values).
- `min_thw` from t = 2 s; `max_jerk` (0.5 s moving average, whole run); `max_jerk_automated`
  (same, only over windows in automated control, i.e. before the driver's first input; used
  by AC-04); `max_jerk_raw`.
- `max_required_decel` (before the TOR) and `tor_reason` (which monitor branch fired), for
  diagnostics only (hidden from search strategies).
- `collision_time`, `impact_speed` (at the crossing), `duration`, `hazard_onset_s`.

## Reference responses (`config/reference.yaml`, `avval/reference.py`)

Each run's **scenario** is replayed, using the simulator's kinematics and contact
definition, with a fixed ego response: hold speed until hazard onset (no pre-hazard
intervention), wait the reaction time, brake (instantly or jerk-limited) to the deceleration
level and hold it to standstill; brake-only and longitudinal (no steering); perfect
knowledge of the hazard at onset. Results are scenario properties, computed for **every**
run, independent of the system under test's actions and of its design parameters. Each
definition carries a maturity `status` (reference.yaml); a criterion that uses it is at most
as mature (see evaluation.md):

- `avoidable_by_reference` — the ideal reference (0.9 μg, no reaction time; status
  illustrative) avoids contact. FALSE does **not** mean the collision is physically
  unavoidable: earlier, harder (up to μg) or lateral responses may avoid it. Scopes AC-01
  and AC-03; AC-09/AC-10 gate the same driver populations without it.
- `handback_required` — braking **fixed at the nominal system's design authority**
  (3.5 m/s², status provisional, TODO(data)) from hazard onset does **not** avoid contact.
  3.5 m/s² is the demonstrator policy's training authority (`avval/policy.py`, since v0.1),
  frozen in `reference.yaml`; it is not an external, programme-level capability. It was
  chosen as a typical ACC braking limit and has not been verified against any published ACC
  deceleration envelope (such as ISO 15622), so no standard is cited — **provisional, source
  to be confirmed**. Being frozen, it is not read from the configuration under test: an
  authority variant changes the system, not this population, so AC-03 strata, AC-07 and
  AC-08 stay comparable across design variants. The same 3.5 m/s² is also the sensitivity
  study's required-deceleration exceedance level (a deliberate, documented coupling).
  (An earlier development version used the configured authority, which confounded the
  authority sensitivity.)
- `ccd_avoidable_by_reference` — the careful-competent-driver reference; NULL while disabled.

v0.2 called these "preventable/unpreventable", replayed only collisions, and counted every
avoided run as preventable, which made the AC-01 population depend on the system's actions.

## Driver model (`config/driver.yaml`)

| State | Mean | SD | Floor | Source |
| --- | --- | --- | --- | --- |
| `attentive` (intended use) | 1.3 s | 0.5 s | 0.5 s | Green (2000), Summala (2000); CV from Johansson & Rumar (1971), Magister et al. (2005) |
| `distracted` (foreseeable misuse) | 4.59 s | 1.33 s | 1.77 s (placeholder, `TODO(data)`) | Kästle et al. (2025), IEEE Transactions on Haptics |

- Log-normal matched to mean and SD; draws below the floor are redrawn (capped).
- Both states start reacting at the TOR, which is pessimistic for the attentive driver.
- After the first input and `brake_onset_delay_s`, the driver brakes towards
  min(peak · μg, `brake_demand_factor` × required deceleration), at `brake_jerk`, and holds
  at least `standstill_hold_decel_mps2` (2.0, TODO(data)) until standstill while a conflict
  remains. Without that hold, braking proportional to the required deceleration (∝ v²
  near standstill) never stops the car: it crept on and touched a stopped lead at a few
  cm/s, seconds later, at a time that depended on dt (`tests/test_standstill_hold.py`). The
  2.0 m/s² is a behavioural **placeholder**, not validated; it is a sensitivity factor
  (1–4 m/s²) in every design. Vehicle reversal is prevented by the kinematics independently
  of it.
- Placeholders: distracted floor, `brake_onset_delay_s`, `brake_demand_factor`,
  `standstill_hold_decel_mps2`, `peak_decel_fraction`, `brake_jerk`.

## Simulator verification (`tests/test_sim_verification.py`, `tests/test_sim_timing.py`)

- Closed-form checks to floating-point round-off (exact integration): stopping distance
  v²/2a including a mid-step stop; friction-capped lead braking; constant gap at equal
  speeds; cut-in gap closing at the closing speed; analytic lead position through its stop.
- Contact at the exact crossing: a 2 m cut-in closing at 9 m/s collides at 2/9 s with
  9 m/s; a 0.3 m cut-in has duration 0.3/9 s; braking inside the step gives the analytic
  impact speed.
- Event ordering: the TOR fires at exactly the lead's onset, identically at dt and dt/2.
- Convergence on 144 closed-loop cases at dt and dt/2: TOR time within one step, at most one
  outcome/end-state flip, `min_ttc` within 2·dt (median ≤ 0.01 s), collision time within
  2·dt, impact speed within g·dt. (Measured: 0 flips, collision time ≤ 0.015 s, impact
  speed ≤ 0.23 m/s, median `min_ttc` change 0.0003 s.)
- Property tests: scalar and vectorised contact roots agree and are roots; required
  deceleration is continuous, sufficient and necessary.
