"""Store schema versioning, coverage (including driver state) and campaign-scoped SQL."""
import duckdb
import numpy as np
import pytest

from avval.campaign import Campaign, random_case
from avval.evaluation import all_cells, coverage, evaluate_acceptance, failure_curve
from avval.store import SCHEMA_VERSION, LegacyDatabaseError, Store


def test_query_is_read_only_and_scoped(store, policy):
    Campaign("a", store, policy, 5).run([random_case(np.random.default_rng(0))])
    Campaign("other", store, policy, 5)
    assert store.query("SELECT count(*) AS n FROM runs", "a").n[0] == 1
    assert store.query("SELECT count(*) AS n FROM runs", "other").n[0] == 0
    for bad in ("DROP TABLE all_runs", "SELECT 1; DELETE FROM all_runs",
                "WITH x AS (SELECT 1) INSERT INTO all_runs SELECT * FROM all_runs"):
        with pytest.raises(ValueError):
            store.query(bad, "a")
    assert len(store.query("WITH c AS (SELECT * FROM runs) SELECT * FROM c", "a")) == 1


def test_coverage_includes_driver_state(store, policy):
    camp = Campaign("c", store, policy, 60)
    camp.run([random_case(camp.case_rng(i)) for i in range(60)])
    cov = coverage(store, "c")
    assert cov["cells_total"] == len(all_cells()) == 216  # 2 scenarios x 2 driver states x 54
    assert "driver_state" in cov["dimensions"] and cov["complete_odd"]
    assert 0 < cov["cells_covered"] <= 60
    curve = failure_curve(store, "c")
    assert len(curve) == 60 and curve["distinct_failing_cells"].is_monotonic_increasing


def test_a_cell_needs_each_driver_state(store, policy):
    case = dict(scenario="cut_in", ego_speed=30.0, closing_speed=3.0, headway=1.5,
                friction=1.0, driver_state="attentive")
    camp = Campaign("d", store, policy, 4)
    camp.run([case, case])
    assert coverage(store, "d")["cells_covered"] == 1
    camp.run([{**case, "driver_state": "distracted"}])
    assert coverage(store, "d")["cells_covered"] == 2


def test_unused_scenario_parameter_is_null(store, policy):
    camp = Campaign("n", store, policy, 40)
    camp.run([random_case(camp.case_rng(i)) for i in range(40)])
    bad = store.query("SELECT count(*) AS n FROM runs WHERE (scenario = 'lead_brake') "
                      "= (lead_decel IS NULL OR closing_speed IS NOT NULL)", "n").n[0]
    assert bad == 0


def test_legacy_database_is_refused(tmp_path):
    path = tmp_path / "old.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE all_runs (campaign VARCHAR, run_idx INTEGER, scenario VARCHAR, "
                "preventable BOOLEAN, driver_state VARCHAR)")
    con.execute("CREATE TABLE campaigns (name VARCHAR, provenance VARCHAR)")
    con.close()
    with pytest.raises(LegacyDatabaseError, match="legacy schema"):
        Store(path)


def test_same_names_with_other_types_or_versions_are_refused(tmp_path):
    path = tmp_path / "x.duckdb"
    Store(path).con.close()
    con = duckdb.connect(str(path))
    con.execute("ALTER TABLE all_runs ALTER COLUMN min_ttc TYPE VARCHAR")
    con.close()
    with pytest.raises(LegacyDatabaseError, match="columns"):
        Store(path)
    path2 = tmp_path / "y.duckdb"
    Store(path2).con.close()
    con = duckdb.connect(str(path2))
    con.execute("UPDATE schema_meta SET value = '2' WHERE key = 'schema_version'")
    con.close()
    with pytest.raises(LegacyDatabaseError, match="schema version"):
        Store(path2)
    path3 = tmp_path / "z.duckdb"
    Store(path3).con.close()
    con = duckdb.connect(str(path3))
    con.execute("UPDATE schema_meta SET value = '2' WHERE key = 'metric_semantics_version'")
    con.close()
    with pytest.raises(LegacyDatabaseError, match="metric semantics"):
        Store(path3)


def test_new_store_records_versions(store):
    meta = dict(store.con.execute("SELECT key, value FROM schema_meta").fetchall())
    assert meta["schema_version"] == SCHEMA_VERSION


def test_runs_need_a_registered_campaign(store):
    from tests.helpers import row
    with pytest.raises(duckdb.ConstraintException):
        store.insert([row("ghost", 0)])


def test_driver_category_is_queryable(store, policy):
    camp = Campaign("dc", store, policy, 60)
    camp.run([random_case(camp.case_rng(i)) for i in range(60)])
    df = store.query("SELECT DISTINCT driver_state, driver_category FROM runs", "dc")
    assert dict(zip(df.driver_state, df.driver_category)) == {
        "attentive": "intended_use", "distracted": "foreseeable_misuse"}


def test_acceptance_on_a_simulated_campaign_has_every_criterion(store, policy):
    camp = Campaign("acc", store, policy, 60)
    camp.run([random_case(camp.case_rng(i)) for i in range(60)])
    acc = {a["id"]: a for a in evaluate_acceptance(store, "acc")}
    assert set(acc) == {"AC-01", "AC-02", "AC-03", "AC-04", "AC-07", "AC-08", "AC-09",
                        "AC-10", "AC-06", "AC-02-S", "AC-03-C"}
    assert all(acc[i]["status"] == "INFO" for i in ("AC-06", "AC-02-S", "AC-03-C"))
    assert acc["AC-02"]["n"] == acc["AC-04"]["n"] == 60  # all runs, no outcome conditioning
