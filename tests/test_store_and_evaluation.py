import pytest

from avval.campaign import Campaign, random_case
from avval.evaluation import all_cells, coverage, evaluate_acceptance, failure_curve


def test_campaign_respects_budget(store, policy):
    camp = Campaign("t", store, policy, budget=10)
    camp.run([random_case(camp.rng) for _ in range(25)])
    assert store.n_runs("t") == 10 and camp.remaining == 0


def test_query_is_read_only_and_scoped(store, policy):
    Campaign("a", store, policy, 5).run([random_case(__import__("numpy").random.default_rng(0))])
    assert store.query("SELECT count(*) AS n FROM runs", "a").n[0] == 1
    assert store.query("SELECT count(*) AS n FROM runs", "other").n[0] == 0
    for bad in ("DROP TABLE all_runs", "SELECT 1; DELETE FROM all_runs",
                "WITH x AS (SELECT 1) INSERT INTO all_runs SELECT * FROM all_runs"):
        with pytest.raises(ValueError):
            store.query(bad, "a")
    # CTE-style queries from the agent are supported
    assert len(store.query("WITH c AS (SELECT * FROM runs) SELECT * FROM c", "a")) == 1


def test_acceptance_and_coverage(store, policy):
    camp = Campaign("c", store, policy, 60)
    camp.run([random_case(camp.rng) for _ in range(60)])
    acc = {a["id"]: a for a in evaluate_acceptance(store, "c")}
    assert set(acc) == {"AC-01", "AC-02", "AC-03", "AC-04", "AC-06"}  # AC-05 retired
    assert all(a["status"] in {"PASS", "FAIL", "INSUFFICIENT EVIDENCE", "NO FAILURES OBSERVED"}
               for k, a in acc.items() if k != "AC-06")
    assert acc["AC-06"]["status"] == "INFO"
    cov = coverage(store, "c")
    assert cov["cells_total"] == len(all_cells()) == 108
    assert 0 < cov["cells_covered"] <= 60
    curve = failure_curve(store, "c")
    assert len(curve) == 60 and curve["distinct_failing_cells"].is_monotonic_increasing


def test_unused_scenario_parameter_is_null(store, policy):
    camp = Campaign("n", store, policy, 40)
    camp.run([random_case(camp.rng) for _ in range(40)])
    bad = store.query("SELECT count(*) AS n FROM runs WHERE (scenario = 'lead_brake') "
                      "= (lead_decel IS NULL OR closing_speed IS NOT NULL)", "n").n[0]
    assert bad == 0


def test_old_database_is_refused_with_a_clear_message(tmp_path):
    import duckdb
    from avval.store import Store
    path = tmp_path / "old.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE all_runs (campaign VARCHAR, run_idx INTEGER, scenario VARCHAR, "
                "severity DOUBLE, driver_state VARCHAR)")
    con.close()
    with pytest.raises(RuntimeError, match="older version.*re-run the campaigns"):
        Store(path)


def test_driver_category_is_queryable(store, policy):
    camp = Campaign("d", store, policy, 60)
    camp.run([random_case(camp.rng) for _ in range(60)])
    df = store.query("SELECT DISTINCT driver_state, driver_category FROM runs", "d")
    assert dict(zip(df.driver_state, df.driver_category)) == {
        "attentive": "intended_use", "distracted": "foreseeable_misuse"}


def test_ac03_covers_only_the_distracted_driver(store, policy):
    from avval.config import load_acceptance
    ac03 = next(c for c in load_acceptance()["criteria"] if c["id"] == "AC-03")
    camp = Campaign("m", store, policy, 40)
    case = dict(scenario="lead_brake", ego_speed=30, headway=0.8, lead_decel=8, friction=1.0)
    camp.run([{**case, "driver_state": s} for s in ("attentive", "distracted")] * 20)
    states = set(store.query(f"SELECT DISTINCT driver_state FROM runs WHERE {ac03['where']}",
                             "m").driver_state)
    assert states == {"distracted"}
    assert "AC-05" in {c["id"] for c in load_acceptance()["retired_criteria"]}


def test_ac02_excludes_collisions(store, policy):
    camp = Campaign("ac2", store, policy, 80)
    camp.run([random_case(camp.rng) for _ in range(80)])
    acc = {a["id"]: a for a in evaluate_acceptance(store, "ac2")}
    n_ok = store.query("SELECT count(*) AS n FROM runs WHERE NOT collision", "ac2").n[0]
    assert 0 < n_ok < 80 and acc["AC-02"]["n"] == n_ok


def test_never_closing_runs_count_as_safe(store):
    from avval.config import load_acceptance
    ac2 = next(c for c in load_acceptance()["criteria"] if c["id"] == "AC-02")
    ttcs = [None] * 18 + [0.5, 3.0]  # 18 never closing, one unsafe, one safe
    rows = [{"campaign": "nc", "run_idx": i, "scenario": "cut_in", "driver_state": "attentive",
             "collision": False, "min_ttc": t} for i, t in enumerate(ttcs)]
    store.insert(rows)
    from avval.evaluation import value_sql
    value = store.query(f"SELECT {value_sql(ac2)} AS v FROM runs WHERE {ac2['where']}", "nc").v[0]
    assert value > 1.5  # 5th percentile of {0.5, 3.0, inf x 18}, not of {0.5, 3.0}
    failed = store.query("SELECT count(*) FILTER (WHERE "
                         f"{load_acceptance()['failure_predicate']}) AS n FROM runs", "nc").n[0]
    assert failed == 1
