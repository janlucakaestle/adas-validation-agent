"""Exposure model: fail-closed validation, explicit support and conditional structure."""
from collections import Counter

import numpy as np
import pytest

from avval.config import load_exposure, load_odd, validate_case
from avval.exposure import ExposureModel
from avval.frozen import freeze, thaw


def _model(mutate):
    cfg = thaw(load_exposure())
    mutate(cfg)
    return ExposureModel(freeze(cfg), load_odd())


def test_shipped_model_is_valid_factorized_and_labelled():
    m = ExposureModel(load_exposure(), load_odd())
    d = m.describe()
    assert d["structure"] == "factorized" and d["status"] == "placeholder"
    assert "conditional" in d["assumption"].lower()


def test_samples_lie_in_the_odd_and_follow_the_weights():
    m = ExposureModel(load_exposure(), load_odd())
    rng = np.random.default_rng(0)
    cases = [m.sample(rng) for _ in range(4000)]
    for c in cases:
        validate_case(c)
    share = Counter(c["driver_state"] for c in cases)["attentive"] / len(cases)
    assert share == pytest.approx(0.8, abs=0.02)
    frame = m.sample_frame(20_000, np.random.default_rng(1))
    assert frame["driver_state"].eq("attentive").mean() == pytest.approx(0.8, abs=0.01)
    assert frame.loc[frame.scenario == "lead_brake", "closing_speed"].isna().all()


@pytest.mark.parametrize("bad, match", [
    ([0.2, -0.1, 0.9], "non-negative"),
    ([0.2, float("nan"), 0.8], "finite"),
    ([0.2, float("inf"), 0.8], "finite"),
    ([0.2, 0.4, 0.5], "sum"),
])
def test_invalid_weights_fail(bad, match):
    def mut(cfg):
        cfg["factors"]["ego_speed"]["weights"] = bad
    with pytest.raises(ValueError, match=match):
        _model(mut)


def test_bins_must_be_ordered():
    def mut(cfg):
        cfg["factors"]["ego_speed"]["bins"] = [15.0, 29.0, 22.0, 36.0]
    with pytest.raises(ValueError, match="increasing"):
        _model(mut)


def test_partial_odd_support_is_rejected():
    """Histogram support covering only part of the ODD silently dropped the rest from
    validation concern. It is now an error."""
    def mut(cfg):
        cfg["factors"]["friction"] = {"type": "histogram", "bins": [0.6, 0.75, 1.0],
                                      "weights": [0.2, 0.8]}
    with pytest.raises(ValueError, match="full ODD"):
        _model(mut)


def test_unvisited_regions_must_be_explicit_and_are_reported():
    def mut(cfg):
        cfg["factors"]["friction"] = {"type": "histogram", "bins": [0.5, 0.6, 0.75, 1.0],
                                      "weights": [0.0, 0.2, 0.8]}
        cfg["factors"]["driver_state"]["weights"] = {"attentive": 1.0, "distracted": 0.0}
    m = _model(mut)
    assert "friction in [0.5, 0.6)" in m.zero_exposure_regions()
    assert "driver_state = distracted" in m.zero_exposure_regions()


def test_categorical_must_list_every_odd_value():
    def mut(cfg):
        cfg["factors"]["driver_state"]["weights"] = {"attentive": 1.0}
    with pytest.raises(ValueError, match="cover exactly"):
        _model(mut)


def test_conditional_factors_are_supported():
    """A factor may depend on earlier categorical factors (here friction on the driver state)."""
    def mut(cfg):
        cfg["factors"]["friction"] = {
            "type": "histogram", "given": ["driver_state"], "table": {
                "attentive": {"bins": [0.5, 0.75, 1.0], "weights": [0.0, 1.0]},
                "distracted": {"bins": [0.5, 0.75, 1.0], "weights": [1.0, 0.0]}}}
    m = _model(mut)
    df = m.sample_frame(5000, np.random.default_rng(2))
    assert (df.loc[df.driver_state == "attentive", "friction"] >= 0.75).all()
    assert (df.loc[df.driver_state == "distracted", "friction"] < 0.75).all()


def test_scenario_dependent_factors_must_be_conditioned():
    def mut(cfg):
        cfg["factors"]["headway"] = {"type": "histogram", "bins": [0.3, 1.0, 3.0],
                                     "weights": [0.5, 0.5]}
    with pytest.raises(ValueError, match="given"):
        _model(mut)
