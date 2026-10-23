"""Benchmark: frozen protocol bound to release/runtime, completeness, probability model."""
import json

import numpy as np
import pytest
from scipy import stats

import avval.baselines as bl
import avval.benchmark as bm
import avval.config as cfg
from avval.baselines import ADAPTIVE, STRATEGIES, robustness, run_strategy
from avval.benchmark import (at_least, campaign_name, freeze_protocol, kaplan_meier,
                             load_manifest, posterior_predictive_at_least, rmst,
                             validate_protocol, write_benchmark)
from avval.campaign import Campaign
from avval.config import Release
from avval.frozen import freeze, thaw
from avval.search import SearchInterface


def test_at_least_matches_exact_cases():
    assert at_least([0.5, 0.5], 2) == 0.25
    assert at_least([0.5, 0.5], 1) == 0.75
    assert at_least([0.3, 0.6, 0.9], 0) == 1.0
    assert abs(at_least([0.3, 0.6, 0.9], 3) - 0.3 * 0.6 * 0.9) < 1e-12


@pytest.mark.parametrize("m, k", [(12, 0), (12, 5), (100, 37), (5, 5)])
def test_single_budget_marginal_is_the_jeffreys_posterior(m, k):
    """With weights Dirichlet(1, ..., 1, 1/2, 1/2) on m campaigns plus an always- and a
    never-hit pseudo-trajectory, p = (sum of hitting weights) + w_always is
    Beta(k + 1/2, m - k + 1/2): the Jeffreys posterior for k hits in m campaigns."""
    rng = np.random.default_rng(0)
    w = rng.dirichlet(np.r_[np.ones(m), 0.5, 0.5], size=40_000)
    p = w[:, :k].sum(1) + w[:, m]
    jeff = stats.beta(k + 0.5, m - k + 0.5)
    assert stats.kstest(p, jeff.cdf).pvalue > 0.01
    # and the implementation draws exactly this: one seed, at_least(p, 1) = p
    detect = np.zeros((m, 1), bool)
    detect[:k, 0] = True
    pp = posterior_predictive_at_least(detect, 1, draws=40_000, seed=3)
    assert pp["posterior_predictive"] == pytest.approx(jeff.mean(), abs=4e-3)
    assert pp["upper95"] == pytest.approx(jeff.ppf(0.95), abs=6e-3)


@pytest.mark.parametrize("prior", [0.5, 1.0])
def test_every_single_budget_marginal_is_beta_k_plus_prior(prior):
    """With several (nested) budgets at once, the implementation's posterior draw of the
    detection probability at EVERY budget j is Beta(k_j + prior, m - k_j + prior): Jeffreys
    for the primary prior 1/2, uniform for the sensitivity prior 1. The draws share one
    weight vector, so the budgets are dependent (nested) but each marginal is exact."""
    from avval.benchmark import posterior_detection_probs
    rng = np.random.default_rng(5)
    m = 40
    first = rng.geometric(1 / 120, size=m)
    budgets = np.array([20, 60, 120, 200, 300, 2000])
    detect = first[:, None] < budgets[None, :]
    p = posterior_detection_probs(detect, draws=40_000, seed=2, prior=prior)
    ks = detect.sum(0)
    assert ks[0] < ks[-2] and ks[-1] == m  # spans few-hit to all-hit budgets
    for j, k in enumerate(ks):
        ref = stats.beta(k + prior, m - k + prior)
        assert stats.kstest(p[:, j], ref.cdf).pvalue > 0.001, (j, k)
        assert p[:, j].mean() == pytest.approx(ref.mean(), abs=3e-3)
    assert (np.diff(p, axis=1) >= -1e-12).all()  # nested within every draw


def test_shared_weights_preserve_nesting_across_budgets():
    rng = np.random.default_rng(1)
    first = rng.geometric(1 / 150, size=20)
    detect = first[:, None] < np.array([100, 150, 200])[None, :]
    aug = np.vstack([detect.astype(float), np.ones(3), np.zeros(3)])
    p = rng.dirichlet(np.r_[np.ones(20), 0.5, 0.5], size=2000) @ aug
    assert (np.diff(p, axis=1) >= -1e-12).all()  # non-decreasing in the budget


def test_uncertain_baseline_probabilities_widen_the_tail_probability():
    rng = np.random.default_rng(0)
    budgets = rng.integers(150, 220, size=10)
    detect = rng.geometric(1 / 150, size=12)[:, None] < budgets[None, :]
    pp = posterior_predictive_at_least(detect, 10, draws=4000, seed=1)
    assert pp["upper95"] > 3 * pp["plug_in"]
    assert pp["posterior_predictive"] >= pp["plug_in"]
    many = rng.geometric(1 / 150, size=3000)[:, None] < budgets[None, :]
    pm = posterior_predictive_at_least(many, 10, draws=1000, seed=1)
    assert pm["posterior_predictive"] == pytest.approx(pm["plug_in"], rel=0.25)
    assert pm["upper95"] - pm["plug_in"] < pp["upper95"] - pp["plug_in"]  # narrower


def test_few_campaigns_that_all_missed_do_not_give_a_zero_bound():
    detect = np.zeros((2, 3), bool)
    assert posterior_predictive_at_least(detect, 2)["upper95"] > 0.05
    assert posterior_predictive_at_least(detect, 2, prior=0.0)["upper95"] == 0.0  # why it matters


def test_kaplan_meier_keeps_censored_campaigns():
    times = np.array([10.0, 20.0, 300.0, 300.0])
    events = np.array([True, True, False, False])
    assert list(kaplan_meier(times, events)["survival"]) == pytest.approx([0.75, 0.5])
    assert rmst(times, events, 300.0) == pytest.approx(10 + 0.75 * 10 + 0.5 * 280)


def test_baselines_use_only_the_public_domain_and_visible_outputs(store, policy):
    import inspect
    src = inspect.getsource(bl)
    assert "release.odd" not in src and "load_odd" not in src
    assert "avoidable_by_reference" not in inspect.getsource(robustness)
    for name in ADAPTIVE:
        c = Campaign(f"{name}_t", store, policy, 45, seed=3, method=name)
        run_strategy(name, c)
        assert store.n_runs(c.name) == 45 and store.get_campaign(c.name)["status"] == "COMPLETE"


def test_baselines_are_reproducible(store, policy):
    for name in ("random", "cem"):
        for k in (0, 1):
            run_strategy(name, Campaign(f"{name}_r{k}", store, policy, 45, seed=7, method=name))
        a = store.campaign_df(f"{name}_r0").drop(columns="campaign")
        b = store.campaign_df(f"{name}_r1").drop(columns="campaign")
        assert a.equals(b)


def test_baseline_hyperparameters_are_part_of_the_protocol_id(policy, monkeypatch, tmp_path):
    rel = Release.build(policy)
    a = freeze_protocol(rel, path=tmp_path / "a.json")
    spec = thaw(bl.BASELINE_SPEC)
    spec["cem"]["elite_fraction"] = 0.25
    monkeypatch.setattr(bl, "BASELINE_SPEC", spec)
    b = freeze_protocol(rel, path=tmp_path / "b.json")
    assert a["protocol_id"] != b["protocol_id"]
    with pytest.raises(ValueError, match="baseline specification changed"):
        load_manifest(path=tmp_path / "a.json")


def test_protocol_edits_after_freezing_are_refused(policy, monkeypatch):
    freeze_protocol(Release.build(policy))
    proto = thaw(bm.load_protocol())
    proto["budget"] = 301
    orig = cfg.load_file
    monkeypatch.setattr(cfg, "load_file",
                        lambda name: freeze(proto) if name == "benchmark" else orig(name))
    with pytest.raises(ValueError, match="changed after the protocol was frozen"):
        load_manifest()


def test_benchmark_is_bound_to_the_frozen_release_and_runtime(policy, monkeypatch):
    rel = Release.build(policy)
    freeze_protocol(rel)
    assert load_manifest(rel)
    with pytest.raises(ValueError, match="current release differs"):
        load_manifest(rel.with_overrides({"sim": {"monitor": {"tor_ttc_s": 2.5}}}))
    monkeypatch.setattr("avval.provenance.runtime_id", lambda fp=None: "0" * 64)
    with pytest.raises(ValueError, match="current runtime differs"):
        load_manifest(rel)


# ---- completeness -------------------------------------------------------------------------
def _tiny():
    p = thaw(bm.load_protocol())
    p.update(budget=30, strategies=["agent", "random", "boundary"])
    p["seeds"] = {"agent": [0, 1], "baselines": {"first": 0, "count": 2}}
    p["primary"]["bootstrap_draws"] = 300
    return p


def _agent_campaign(store, policy, name, seed, pid, tmp_path, model="claude-x-1"):
    """A stand-in agent campaign (no API): 20 uniform runs, then submitted."""
    c = Campaign(name, store, policy, 30, seed=seed, method="agent", protocol_id=pid)
    dom = SearchInterface(c).domain()
    c.run([bl.random_case(c.case_rng(i), dom) for i in range(20)])
    c.finish("submitted")
    (tmp_path / f"usage_{name}.json").write_text(json.dumps({"models_returned": [model],
                                                             "est_cost_usd": 0.1}))
    return c


@pytest.fixture
def protocol(store, policy, monkeypatch, tmp_path):
    proto = _tiny()
    monkeypatch.setattr(bm, "load_protocol", lambda: proto)
    m = freeze_protocol(Release.build(policy))
    pid = m["protocol_id"]
    for s in range(2):
        for strat in ("random", "boundary"):
            run_strategy(strat, Campaign(campaign_name(strat, s), store, policy, 30, seed=s,
                                         method=strat, protocol_id=pid))
    _agent_campaign(store, policy, "agent_s0", 0, pid, tmp_path)
    return m


def test_incomplete_protocol_cannot_produce_a_confirmatory_report(store, protocol):
    _, problems = validate_protocol(store, protocol)
    assert any("agent seed 1" in p and "missing" in p for p in problems)
    with pytest.raises(ValueError, match="incomplete"):
        write_benchmark(store, protocol)
    path, res = write_benchmark(store, protocol, partial=True)
    text = open(path, encoding="utf-8").read()
    assert "PARTIAL, EXPLORATORY" in text and "Under this simulator" not in text
    assert res["mode"] == "partial (exploratory)"


def test_complete_protocol_reports_scoped_results(store, policy, protocol, tmp_path):
    _agent_campaign(store, policy, "agent_s1", 1, protocol["protocol_id"], tmp_path)
    chosen, problems = validate_protocol(store, protocol)
    assert problems == [] and chosen["agent"] == ["agent_s0", "agent_s1"]
    path, res = write_benchmark(store, protocol)
    text = open(path, encoding="utf-8").read()
    assert "Under this simulator, information interface" in text
    assert "derived labels" in text and "not frequentist p-values" in text
    assert res["mode"].startswith("complete (development")  # not final evidence
    a = json.loads((tmp_path / "benchmark_analysis.json").read_text())
    assert a["protocol_id"] == protocol["protocol_id"]
    assert set(a["matched"]["baselines"]["random"]["prior_sensitivity"]) == set(bm.PRIORS)


def test_mixed_runtime_campaigns_are_rejected(store, policy, protocol, tmp_path):
    _agent_campaign(store, policy, "agent_s1", 1, protocol["protocol_id"], tmp_path)
    store.update_campaign("random_s1", runtime_id="0" * 64)
    _, problems = validate_protocol(store, protocol)
    assert any("random seed 1" in p and "runtime_id" in p for p in problems)


def test_extra_tampered_or_mixed_model_campaigns_are_rejected(store, policy, protocol, tmp_path):
    pid = protocol["protocol_id"]
    _agent_campaign(store, policy, "agent_s1", 1, pid, tmp_path, model="claude-y-2")
    run_strategy("random", Campaign("random_s7", store, policy, 30, seed=7, method="random",
                                    protocol_id=pid))
    store.con.execute("UPDATE all_runs SET collision = NOT collision "
                      "WHERE campaign = 'boundary_s0' AND run_idx = 1")
    _, problems = validate_protocol(store, protocol)
    assert any("unexpected campaign" in p and "random_s7" in p for p in problems)
    assert any("boundary seed 0" in p and "data hash" in p for p in problems)
    assert any("different returned models" in p for p in problems)


def test_an_infrastructure_retry_is_accepted_once_and_only_as_such(store, policy, protocol,
                                                                   tmp_path):
    pid = protocol["protocol_id"]
    failed = Campaign("agent_s1", store, policy, 30, seed=1, method="agent", protocol_id=pid)
    failed.fail("infrastructure: APIConnectionError")
    _agent_campaign(store, policy, "agent_s1_retry1", 1, pid, tmp_path)
    chosen, problems = validate_protocol(store, protocol)
    assert problems == [] and "agent_s1_retry1" in chosen["agent"]
    store.update_campaign("agent_s1", stop_reason="error: ValueError")  # not infrastructure
    _, problems = validate_protocol(store, protocol)
    assert any("agent seed 1" in p for p in problems)


def test_strategy_list_covers_adaptive_baselines():
    assert {"cem", "evolutionary", "boundary", "bayesopt"} <= set(STRATEGIES)
    assert set(bm.load_protocol()["strategies"]) - {"agent"} <= set(STRATEGIES)


def test_agent_model_identity_reports_alias_limitation_and_time_span(tmp_path):
    from avval.benchmark import agent_model_identity, model_identity_lines
    for name, f, la in (("agent_s0", "2026-10-22T09:00:00+00:00", "2026-10-22T09:20:00+00:00"),
                        ("agent_s1", "2026-10-22T09:25:00+00:00", "2026-10-22T09:50:00+00:00")):
        (tmp_path / f"usage_{name}.json").write_text(json.dumps(
            {"models_returned": ["claude-sonnet-5"], "first_call_utc": f, "last_call_utc": la}))
    ident = agent_model_identity(["agent_s0", "agent_s1"], usage_dir=tmp_path)
    assert not ident["dated_snapshot"]
    assert ident["first_call_utc"].startswith("2026-10-22T09:00")
    assert ident["last_call_utc"].startswith("2026-10-22T09:50")
    text = "\n".join(model_identity_lines(ident))
    assert "Limitation" in text and "cannot detect a model update" in text
    (tmp_path / "usage_agent_s0.json").write_text(json.dumps(
        {"models_returned": ["claude-sonnet-4-5-20250929"]}))
    (tmp_path / "usage_agent_s1.json").write_text(json.dumps(
        {"models_returned": ["claude-sonnet-4-5-20250929"]}))
    dated = agent_model_identity(["agent_s0", "agent_s1"], usage_dir=tmp_path)
    assert dated["dated_snapshot"] and "Limitation" not in "\n".join(model_identity_lines(dated))


def test_cost_caps_do_not_bind_before_the_turn_limit():
    """The frozen caps must leave max_turns as the binding stop: per-seed cap at least twice
    the worst projected 40-turn cost ($2.37), and the total cap at least seeds x per-seed."""
    proto = bm.load_protocol()
    a = proto["agent"]
    assert a["cost_cap_usd_per_seed"] >= 2 * 2.37
    assert a["total_cost_cap_usd"] >= len(proto["seeds"]["agent"]) * a["cost_cap_usd_per_seed"]
