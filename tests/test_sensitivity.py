"""Sensitivity designs: every variant is its own release; claims are scoped to the factors."""
import numpy as np
import pandas as pd
import pytest

from avval.config import Release
from avval.sensitivity import (design, effects, load_protocol, nominal_values, overrides_for,
                               run_sensitivity, run_variant, src, write_sensitivity)


def test_factors_cover_the_driver_and_design_assumptions():
    names = set(load_protocol()["factors"])
    assert {"distracted_takeover_mean_s", "attentive_takeover_mean_s", "brake_onset_delay_s",
            "brake_demand_factor", "peak_decel_fraction", "brake_jerk_mps3", "distracted_share",
            "tor_required_decel_mps2", "acc_authority_mps2"} <= names


def test_overrides_map_to_paths_and_change_the_release(policy):
    base = Release.build(policy)
    nom = nominal_values(base)
    patch = overrides_for({"peak_decel_fraction": 0.8, "distracted_share": 0.3,
                           "acc_authority_mps2": 3.0}, base)
    var = base.with_overrides(patch)
    assert var.driver["states"]["attentive"]["peak_decel_fraction"] == 0.8
    assert var.driver["states"]["distracted"]["peak_decel_fraction"] == 0.8  # "*" path
    w = var.exposure["factors"]["driver_state"]["weights"]
    assert w["distracted"] == 0.3 and w["attentive"] == pytest.approx(0.7)
    assert var.sim["ego"]["accel_min_mps2"] == -3.0 and nom["acc_authority_mps2"] == 3.5
    assert var.release_id != base.release_id


@pytest.mark.parametrize("kind, n_extra", [("oat", None), ("factorial2", 64), ("lhs", 64)])
def test_designs_have_the_expected_shape(policy, kind, n_extra):
    base = Release.build(policy)
    d = design(kind, base)
    assert d[0] == {}
    if kind == "oat":
        nom = nominal_values(base)
        assert all(len(v) == 1 and not np.isclose(list(v.values())[0], nom[list(v)[0]])
                   for v in d[1:])
    else:
        assert len(d) - 1 == n_extra
    if kind == "lhs":  # one sample per stratum of each factor's range
        proto = load_protocol()
        f = "tor_ttc_s"
        lo, hi = proto["factors"][f]["range"]
        bins = np.floor((np.array([v[f] for v in d[1:]]) - lo) / (hi - lo) * 64).clip(0, 63)
        assert len(set(bins)) == 64


def test_factorial_effects_recover_main_effects_and_interactions():
    rng = np.random.default_rng(0)
    rows = []
    for a in (0.0, 1.0):
        for b in (0.0, 1.0):
            for _ in range(3):
                rows.append({"factor:A": a, "factor:B": b,
                             "y": 2 * a - 1 * b + 3 * a * b + rng.normal(0, 1e-6)})
    eff = effects(pd.DataFrame(rows), "y", ["A", "B"]).set_index("term")["effect (high - low)"]
    # +/-1 coding: main effect = average change from low to high; interaction effect = 3
    assert eff["A"] == pytest.approx(2 + 3 / 2, abs=1e-4)
    assert eff["A x B"] == pytest.approx(3 / 2, abs=1e-4)


def test_src_ranks_the_dominant_factor():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"factor:A": rng.uniform(size=200), "factor:B": rng.uniform(size=200)})
    df["y"] = 5 * df["factor:A"] + 0.1 * df["factor:B"]
    tab, r2 = src(df, "y", ["A", "B"])
    assert tab.iloc[0]["factor"] == "A" and r2 > 0.99


def test_variant_is_a_sensitivity_campaign_with_its_own_release(policy):
    row = run_variant(policy, {"tor_required_decel_mps2": 2.5}, 25, 0, "retrain")
    assert row["release_id"] != Release.build(policy).release_id
    base = run_variant(policy, {}, 25, 0, "retrain")
    assert base["release_id"] == Release.build(policy).release_id


def test_authority_above_training_is_retrained_or_flagged(policy, monkeypatch):
    import avval.sensitivity as sens
    calls = []
    monkeypatch.setattr("avval.policy.train_policy",
                        lambda **kw: (calls.append(kw) or policy, {}))
    pol, note = sens._policy_for({"acc_authority_mps2": 4.5}, policy, {}, "retrain")
    assert calls == [{"accel_min": -4.5}] and "re-trained" in note
    _, note = sens._policy_for({"acc_authority_mps2": 4.5}, policy, {}, "saturate")
    assert "CONFOUNDED" in note
    _, note = sens._policy_for({"acc_authority_mps2": 3.0}, policy, {}, "retrain")
    assert note == ""  # below the training authority: pure actuator saturation
    with pytest.raises(ValueError, match="excluded"):
        sens._policy_for({"acc_authority_mps2": 4.5}, policy, {}, "exclude_above_nominal")


def test_oat_smoke_writes_a_scoped_report(policy, tmp_path, monkeypatch):
    import avval.sensitivity as sens
    proto = load_protocol()
    proto["factors"] = {k: proto["factors"][k] for k in ("tor_ttc_s", "distracted_share")}
    proto["designs"]["oat"]["points"] = 2
    monkeypatch.setattr(sens, "load_protocol", lambda: proto)
    df = run_sensitivity(policy, "oat", n=20, seed=0, workers=1)
    assert len(df) == 1 + 2 * 2 - sum(  # 2 points per factor, the nominal one skipped
        np.isclose(v, nominal_values(Release.build(policy), proto)[k])
        for k, f in proto["factors"].items() for v in np.linspace(*f["range"], 2))
    md, png = write_sensitivity(df, "oat", 20, 0)
    text = open(md, encoding="utf-8").read()
    assert "Only these factors were varied" in text and "tor_ttc_s" in text
    assert (tmp_path / "sensitivity_oat.png").stat().st_size > 10_000


# ---- frozen sensitivity protocol (item 13) -------------------------------------------------
def _small_protocol():
    proto = load_protocol()
    proto["factors"] = {k: proto["factors"][k] for k in ("monitor_detection_delay_s",
                                                         "standstill_hold_decel_mps2")}
    proto["designs"] = {"oat": {"points": 2}, "factorial2": {"factors": [
        "standstill_hold_decel_mps2"]}, "lhs": {"samples": 2, "seed": 0}}
    proto["n"] = 15
    return proto


def test_frozen_protocol_is_recorded_everywhere_and_persists_variants(store, policy,
                                                                     monkeypatch, tmp_path):
    import avval.sensitivity as sens
    proto = _small_protocol()
    monkeypatch.setattr(sens, "load_protocol", lambda: proto)
    rel = Release.build(policy)
    m = sens.freeze_protocol(rel)
    assert set(m["designs"]) == {"oat", "factorial2", "lhs"}
    df = run_sensitivity(policy, "oat", workers=1, manifest=m, store=store)
    recs = store.list_campaigns(protocol_id=m["protocol_id"])
    assert len(recs) == len(m["designs"]["oat"]) == len(df)
    assert all(r["kind"] == "sensitivity" and r["status"] == "COMPLETE" for r in recs)
    assert {r["campaign_id"]: r["data_sha256"] for r in recs} == dict(
        zip(df["campaign"], df["data_sha256"]))
    md, _ = write_sensitivity(df, "oat", 15, 0, m["protocol_id"])
    assert m["protocol_id"] in open(md, encoding="utf-8").read()
    csv = pd.read_csv(tmp_path / "sensitivity_oat.csv")
    assert (csv["protocol_id"] == m["protocol_id"]).all()


def test_a_changed_protocol_or_release_is_refused(policy, monkeypatch):
    import avval.sensitivity as sens
    proto = _small_protocol()
    monkeypatch.setattr(sens, "load_protocol", lambda: proto)
    rel = Release.build(policy)
    sens.freeze_protocol(rel)
    proto["n"] = 16
    with pytest.raises(ValueError, match="config differs"):
        sens.load_manifest(rel)
    proto["n"] = 15
    with pytest.raises(ValueError, match="release_id differs"):
        sens.load_manifest(rel.with_overrides({"sim": {"monitor": {"tor_ttc_s": 2.5}}}))


def test_delay_factors_lie_on_the_step_grid(policy):
    rel = Release.build(policy)
    for kind in ("oat", "lhs"):
        for v in design(kind, rel):
            for f in ("monitor_detection_delay_s", "actuator_delay_s"):
                if f in v:
                    assert abs(v[f] / 0.05 - round(v[f] / 0.05)) < 1e-9


# ---- v4 review, Part C: common random numbers, paired primary responses -----------------
SCENARIO_COLS = ["scenario", "ego_speed", "headway", "initial_gap_m", "lead_decel",
                 "closing_speed", "friction", "avoidable_by_reference", "handback_required"]


def test_variants_share_cases_and_seeds_and_differ_only_in_the_varied_factor(policy):
    """Common random numbers: the same run index gets the same case and simulation seed in
    every variant. A design factor changes no case at all; the exposure factor
    `distracted_share` changes only some runs' driver state, never another case parameter."""
    def cases(values):
        _, _, df = run_variant(policy, values, 300, 0, "retrain", keep_data=True)
        return df.sort_values("run_idx").reset_index(drop=True)
    nom = cases({})
    design_var = cases({"tor_ttc_s": 3.0})
    share_var = cases({"distracted_share": 0.40})
    for var in (design_var, share_var):
        assert (var["seed"] == nom["seed"]).all()
        pd.testing.assert_frame_equal(var[SCENARIO_COLS], nom[SCENARIO_COLS])
    assert (design_var["driver_state"] == nom["driver_state"]).all()
    changed = share_var["driver_state"] != nom["driver_state"]
    assert 0 < changed.sum() < len(nom)  # 0.20 -> 0.40: some attentive runs become distracted
    assert (share_var.loc[changed, "driver_state"] == "distracted").all()


def test_paired_effects_recover_known_differences_with_intervals():
    from avval.sensitivity import paired_effects
    proto = load_protocol()
    rng = np.random.default_rng(0)
    n = 2000
    ttc = rng.gamma(4.0, 0.7, n)
    nom = pd.DataFrame({"run_idx": np.arange(n), **{k: ttc for k in
                                                     ("eff_ttc_p01", "eff_ttc_p05", "eff_ttc_p50")},
                        "required_decel_exceedance": (rng.uniform(size=n) < 0.02).astype(float),
                        "near_miss_1p5s": (rng.uniform(size=n) < 0.015).astype(float)})
    same = paired_effects(nom, nom.copy(), proto)
    for name in proto["primary_responses"]:
        assert same[f"{name}_diff"] == 0.0
        assert same[f"{name}_diff_lo"] == same[f"{name}_diff_hi"] == 0.0  # paired: no noise
    var = nom.copy()
    for k in ("eff_ttc_p01", "eff_ttc_p05", "eff_ttc_p50"):
        var[k] = nom[k] - 0.25  # every run 0.25 s closer
    flip = np.flatnonzero(nom["near_miss_1p5s"] == 0)[:40]  # +2 percentage points
    var.loc[flip, "near_miss_1p5s"] = 1.0
    eff = paired_effects(nom, var, proto)
    for k in ("eff_ttc_p01", "eff_ttc_p05", "eff_ttc_p50"):
        assert eff[f"{k}_diff"] == pytest.approx(-0.25)
    assert eff["near_miss_1p5s_diff"] == pytest.approx(0.02)
    assert eff["near_miss_1p5s_diff_lo"] > 0.0  # detected
    assert eff["near_miss_1p5s_mde80"] < 0.02
    # with an infinite effective TTC on both sides the quantile difference is still defined
    inf_nom = nom.assign(eff_ttc_p50=np.inf)
    assert paired_effects(inf_nom, inf_nom.copy(), proto)["eff_ttc_p50_diff"] == 0.0
    with pytest.raises(ValueError, match="same run indices"):
        paired_effects(nom, var.iloc[::-1].reset_index(drop=True), proto)


def test_primary_responses_and_uncertainty_are_part_of_the_frozen_protocol(policy, monkeypatch):
    import avval.sensitivity as sens
    proto = _small_protocol()
    monkeypatch.setattr(sens, "load_protocol", lambda: proto)
    rel = Release.build(policy)
    m = sens.freeze_protocol(rel)
    assert m["config"]["primary_responses"] == proto["primary_responses"]
    assert m["analysis_version"] == "sensitivity-analysis/v5"
    proto["primary_responses"]["near_miss_1p5s"]["event"] = "min_ttc < 2.0"
    with pytest.raises(ValueError, match="config differs"):
        sens.load_manifest(rel)


def test_reports_label_primary_and_secondary_responses(policy, monkeypatch):
    import avval.sensitivity as sens
    proto = _small_protocol()
    proto["n"] = 30
    monkeypatch.setattr(sens, "load_protocol", lambda: proto)
    df = run_sensitivity(policy, "factorial2", n=30, seed=0, workers=1)
    assert (df.loc[0, [c for c in df if c.endswith("_diff")]] == 0).all()  # row 0 = nominal
    md, _ = write_sensitivity(df, "factorial2", 30, 0)
    text = open(md, encoding="utf-8").read()
    assert "## Primary responses (paired differences from the nominal variant)" in text
    assert "## Secondary responses" in text and "not informative on their own" in text
    assert "Factorial effects on eff_ttc_p05 (primary)" in text
