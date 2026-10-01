"""Driver reaction-time model: two states, each from a named published source.

Evidence statement (parameters live in `config/driver.yaml`):
- attentive: an SAE L2 driver supervising with eyes on the road, so the relevant measure is
  the brake reaction time to an unexpected event. Mean 1.3 s (Green, 2000, between his
  "unexpected" and "surprise" categories; consistent with Summala, 2000, 1.0-1.3 s for
  unalerted drivers). SD 0.5 s from a coefficient of variation of about 0.35-0.37 (Johansson
  & Rumar, 1971; Magister et al., 2005). Floor 0.5 s, near the fastest reactions observed.
- distracted: reasonably foreseeable misuse at L2. Mean 4.59 s, SD 1.33 s: urgent takeovers
  after a reading task, measured to the first meaningful input (Kaestle et al., 2025, IEEE
  Transactions on Haptics). Floor 1.77 s is a placeholder for the fastest takeover observed.
- Times are assumed independent of speed across the ODD (the distracted source was measured
  at a constant 70 mph).

Times are drawn from a log-normal matched to each mean and SD. Draws below the state's floor
are redrawn, not clipped, so the distribution has no spike at the floor.
"""
from __future__ import annotations

import math

import numpy as np

from .config import load_driver

MAX_REDRAWS = 100


def lognormal_params(mean: float, sd: float) -> tuple[float, float]:
    sigma2 = math.log(1.0 + (sd / mean) ** 2)
    return math.log(mean) - sigma2 / 2.0, math.sqrt(sigma2)


def sample_takeover_time(driver_state: str, rng: np.random.Generator,
                         driver_cfg: dict | None = None) -> float:
    st = (driver_cfg or load_driver())["states"][driver_state]
    mu, sigma = lognormal_params(st["takeover_mean_s"], st["takeover_sd_s"])
    for _ in range(MAX_REDRAWS):
        t = float(rng.lognormal(mu, sigma))
        if t >= st["floor_s"]:
            return t
    raise RuntimeError(f"{driver_state}: no takeover time above the floor {st['floor_s']} s in "
                       f"{MAX_REDRAWS} draws; check the state's mean, SD and floor")
