"""Multi-seed comparison of search strategies."""
import pytest

from avval.baselines import random_search
from avval.benchmark import (REGIONS, at_least, campaign_stats, matched_per_seed,
                             seed_campaigns, strategy_summary, summary_table, write_benchmark)
from avval.campaign import Campaign
from avval.config import driver_attributes


def _row(campaign, i, **kw):
    base = dict(campaign=campaign, run_idx=i, seed=i, scenario="cut_in", ego_speed=30.0,
                headway=1.0, closing_speed=3.0, friction=1.0, driver_state="distracted",
                collision=False, preventable=True, tor_issued=False, min_ttc=5.0,
                min_ttc_accel=5.0, max_jerk=1.0)
    base.update(kw)
    return {**base, **driver_attributes(base["driver_state"])}


def test_seed_campaigns_are_grouped_and_ordered_numerically(store, policy):
    for k in (0, 2, 10):
        store.insert([_row(f"random_s{k}", 0)])
    store.insert([_row("random_other", 0), _row("grid", 0)])
    assert seed_campaigns(store, "random") == ["random_s0", "random_s2", "random_s10"]
    assert seed_campaigns(store, "grid") == ["grid"]  # single campaign without seeds
    assert seed_campaigns(store, "agent") == []


def test_detection_probability_counts_seeds_that_hit_a_region(store):
    hit = dict(driver_state="attentive", collision=True, preventable=True)
    store.insert([_row("x_s0", 0), _row("x_s0", 1, **hit)])     # finds it at run 2
    store.insert([_row("x_s1", 0), _row("x_s1", 1)])            # never
    store.insert([_row("x_s2", 0, **hit), _row("x_s2", 1)])     # finds it at run 1
    store.insert([_row("x_s3", 0, driver_state="attentive", collision=True,
                       preventable=False), _row("x_s3", 1)])    # unpreventable: not counted
    s = strategy_summary(store, "x")
    assert s["seeds"] == 4
    assert s["P(attentive_preventable_collision)"] == pytest.approx(0.5)
    assert s["seeds_with_failure"] == 3 and s["first_failure_mean"] == pytest.approx(4 / 3)
    stats = campaign_stats(store, "x_s1")
    assert stats["first_failure"] != stats["first_failure"]  # NaN: no failure found


def test_every_region_is_valid_sql(store, policy):
    camp = Campaign("r", store, policy, 20, method="random")
    random_search(camp)
    stats = campaign_stats(store, "r")
    assert set(REGIONS) <= set(stats)


def test_benchmark_writes_table_and_figure(store, policy, tmp_path):
    for k in range(3):
        random_search(Campaign(f"random_s{k}", store, policy, 25, seed=k, method="random"))
    path, summaries = write_benchmark(store, ["random", "grid"])
    assert [s["strategy"] for s in summaries] == ["random"]
    text = open(path, encoding="utf-8").read()
    assert "P(detect attentive_preventable_collision)" in text and "± " in text
    assert (tmp_path / "discovery_curves.png").stat().st_size > 10_000
    table = summary_table(summaries)
    assert table.loc[0, "seeds"] == 3


def test_matched_budget_per_seed(store, policy, tmp_path):
    """Each agent seed is compared with the baselines cut to that seed's own run count."""
    import avval.benchmark as bm
    for k in range(3):
        random_search(Campaign(f"random_s{k}", store, policy, 25, seed=k, method="random"))
    random_search(Campaign("agent_s0", store, policy, 9, seed=5, method="agent"))
    random_search(Campaign("agent_s1", store, policy, 14, seed=6, method="agent"))
    m = matched_per_seed(store, "agent", ["random"], region="comfort_exceedance")
    df = m["per_seed"]
    assert list(df["runs"]) == [9, 14] and m["seeds"] == 2
    for r in df.to_dict("records"):           # the baseline share is recomputed at each budget
        cut = [campaign_stats(store, f"random_s{k}", r["runs"])["comfort_exceedance"]
               for k in range(3)]
        assert r["random_p"] == sum(cut) / 3
        lo, hi = r["random_ci"]
        assert lo <= r["random_p"] <= hi
    b = m["baselines"]["random"]
    assert b["expected"] == df["random_p"].sum()
    assert b["p_at_least"] == at_least(df["random_p"].tolist(), m["detected"])
    path, _ = write_benchmark(store, ["random", "agent"])
    text = open(path, encoding="utf-8").read()
    assert "## Matched budget, per seed" in text and "agent_s1" in text


def test_at_least_matches_exact_cases():
    assert at_least([0.5, 0.5], 2) == 0.25
    assert at_least([0.5, 0.5], 1) == 0.75
    assert at_least([0.3, 0.6, 0.9], 0) == 1.0
    assert abs(at_least([0.3, 0.6, 0.9], 3) - 0.3 * 0.6 * 0.9) < 1e-12
