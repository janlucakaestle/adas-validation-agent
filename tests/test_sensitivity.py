"""One-at-a-time sensitivity analysis."""
import pandas as pd
import pytest

from avval.config import load_driver
from avval.estimation import run_estimation
from avval.evaluation import evaluate_acceptance
from avval.sensitivity import (ASSUMPTIONS, nominal, run_sensitivity, run_variant, sim_kwargs,
                               variants, write_sensitivity)
from avval.sim import simulate


def test_variants_span_each_range_and_skip_the_nominal_point():
    vs = variants()
    assert vs[0] == (None, None)
    for name, spec in ASSUMPTIONS.items():
        values = [v for a, v in vs if a == name]
        assert min(values + [nominal()[name]]) == pytest.approx(spec["range"][0])
        assert max(values + [nominal()[name]]) == pytest.approx(spec["range"][1])
        assert all(v != pytest.approx(nominal()[name]) for v in values)


def test_driver_overrides_change_one_value_and_leave_the_config_alone():
    before = load_driver()["states"]["attentive"]["takeover_mean_s"]
    kw = sim_kwargs("attentive_takeover_mean_s", 1.8)["driver_cfg"]
    assert kw["states"]["attentive"]["takeover_mean_s"] == 1.8
    assert kw["states"]["attentive"]["takeover_sd_s"] == \
        load_driver()["states"]["attentive"]["takeover_sd_s"]
    assert load_driver()["states"]["attentive"]["takeover_mean_s"] == before  # not mutated
    sd = sim_kwargs("attentive_takeover_sd_s", 0.6)["driver_cfg"]["states"]["attentive"]
    assert sd["takeover_sd_s"] == 0.6 and sd["takeover_mean_s"] == before


CUT_IN = dict(scenario="cut_in", ego_speed=30.0, closing_speed=6.0, headway=20.0 / 30.0, friction=1.0,
              driver_state="attentive")


def test_acc_authority_override_limits_acc_braking(policy):
    m3, tr = simulate(CUT_IN, policy, 0, acc_authority=3.0)
    acc_phase = tr.mode == 0
    assert tr.a_ego[acc_phase].min() >= -3.0 - 1e-9
    assert simulate(CUT_IN, policy, 0, acc_authority=3.5)[0] == simulate(CUT_IN, policy, 0)[0]


def test_tor_threshold_override_changes_when_the_monitor_hands_back(policy):
    early = simulate(CUT_IN, policy, 0, tor_req_decel=0.5)[0]
    nominal_run = simulate(CUT_IN, policy, 0)[0]
    assert early["tor_issued"] and (not nominal_run["tor_issued"]
                                    or early["tor_time"] < nominal_run["tor_time"])


def test_baseline_variant_reproduces_the_estimation_campaign(store, policy):
    run_estimation(store, policy, n=40, seed=3)
    plain = evaluate_acceptance(store, "estimate")
    base = run_variant(policy, 40, 3, None, None)
    for a in plain:
        assert base[f"{a['id']}_status"] == a["status"]
        assert base[f"{a['id']}_value"] == a["value"]


def test_sensitivity_writes_table_figure_and_csv(policy, tmp_path):
    df = run_sensitivity(policy, n=30, seed=0, workers=1)
    assert len(df) == len(variants()) and (df["assumption"] == "baseline").sum() == 1
    md, png = write_sensitivity(df, 30, 0)
    text = open(md, encoding="utf-8").read()
    assert "baseline (nominal)" in text and "attentive_takeover_sd_s = 0.6 (nominal 0.5)" in text
    assert (tmp_path / "sensitivity.png").stat().st_size > 10_000
    assert len(pd.read_csv(tmp_path / "sensitivity.csv")) == len(df)
