"""Two-state driver model: log-normal reaction times, redrawn (not clipped) below a floor."""
import math

import numpy as np
import pytest
from scipy import stats

from avval.config import load_driver, validate_case
from avval.driver import MAX_REDRAWS, lognormal_params, sample_takeover_time

N = 100_000


def truncated_moments(mean: float, sd: float, floor: float) -> tuple[float, float]:
    """Mean and SD of a log-normal (matched to mean/sd) conditioned on X >= floor.

    For ln X ~ N(mu, s^2): E[X^k | X >= f] = exp(k mu + k^2 s^2 / 2) * Phi(k s - a) / Phi(-a),
    with a = (ln f - mu) / s. This is the small shift that redrawing below the floor causes.
    """
    mu, s = lognormal_params(mean, sd)
    a = (math.log(floor) - mu) / s
    tail = stats.norm.cdf(-a)
    m1 = math.exp(mu + s ** 2 / 2) * stats.norm.cdf(s - a) / tail
    m2 = math.exp(2 * mu + 2 * s ** 2) * stats.norm.cdf(2 * s - a) / tail
    return m1, math.sqrt(m2 - m1 ** 2)


def _draws(state: str) -> np.ndarray:
    rng = np.random.default_rng(0)
    return np.array([sample_takeover_time(state, rng) for _ in range(N)])


def test_only_two_states_with_named_sources():
    states = load_driver()["states"]
    assert set(states) == {"attentive", "distracted"}
    assert all(st["source"] and st["floor_s"] > 0 for st in states.values())
    assert {k for k in load_driver() if k != "states"} == {
        "schema", "brake_onset_delay_s", "brake_demand_factor", "standstill_hold_decel_mps2"}


@pytest.mark.parametrize("state", ["attentive", "distracted"])
def test_sample_moments_match_targets_after_the_redraw_shift(state):
    st = load_driver()["states"][state]
    x = _draws(state)
    want_mean, want_sd = truncated_moments(st["takeover_mean_s"], st["takeover_sd_s"],
                                           st["floor_s"])
    assert x.mean() == pytest.approx(want_mean, rel=0.02)
    assert x.std() == pytest.approx(want_sd, rel=0.02)
    # and the shift itself is small: within 2% of the published mean
    assert x.mean() == pytest.approx(st["takeover_mean_s"], rel=0.02)


@pytest.mark.parametrize("state", ["attentive", "distracted"])
def test_no_draw_below_the_floor_and_no_spike_at_it(state):
    st = load_driver()["states"][state]
    x = _draws(state)
    floor = st["floor_s"]
    assert x.min() >= floor
    assert not np.any(x == floor)
    # Mass just above the floor matches the truncated density: no pile-up from clipping.
    mu, s = lognormal_params(st["takeover_mean_s"], st["takeover_sd_s"])
    dist = stats.lognorm(s, scale=math.exp(mu))
    width = 0.05
    expected = (dist.cdf(floor + width) - dist.cdf(floor)) / dist.sf(floor)
    observed = np.mean(x < floor + width)
    assert observed <= expected + 5 * math.sqrt(expected / N) + 1e-4


def test_impossible_floor_raises_after_the_redraw_cap():
    cfg = load_driver()
    bad = {**cfg, "states": {**cfg["states"], "attentive": {
        **cfg["states"]["attentive"], "floor_s": 1_000.0}}}
    with pytest.raises(RuntimeError, match=f"{MAX_REDRAWS} draws"):
        sample_takeover_time("attentive", np.random.default_rng(0), bad)


@pytest.mark.parametrize("removed", ["occluded", "phone_user", "asleep"])
def test_other_driver_states_are_rejected_with_a_reason(removed):
    # Only attentive and distracted exist; any other state, including those removed from
    # the driver model, is rejected like an unknown one.
    case = dict(scenario="lead_brake", ego_speed=30.0, headway=1.2, lead_decel=2.0, friction=1.0,
                driver_state=removed)
    with pytest.raises(ValueError, match="not in ODD values"):
        validate_case(case)
