"""The read-only SQL guard, and the sandbox behind it that holds even if the guard is bypassed."""
import time

import duckdb
import pytest

import avval.store as store_mod
from avval.campaign import Campaign, random_case

WRITE_ATTEMPTS = [
    # Direct writes to the real tables: before the sandbox (guard bypassed) the first of these deleted
    # every stored run, since queries ran on the results database connection itself.
    "DELETE FROM all_runs",
    "UPDATE all_runs SET collision = true",
    "INSERT INTO all_runs SELECT * FROM all_runs",
    "DROP TABLE all_runs",
    "DELETE FROM campaigns",
    # Writes to the campaign view and escapes from the sandbox.
    "DELETE FROM runs",
    "UPDATE runs SET collision = true",
    "INSERT INTO runs SELECT * FROM runs",
    "DROP VIEW runs",
    "CREATE TABLE all_runs AS SELECT * FROM runs",
    "ALTER VIEW runs RENAME TO x",
    "SELECT * FROM all_runs",                                  # other campaigns: not visible
    "SELECT * FROM campaigns",
    "SET enable_external_access = true",                       # config is locked
    "SET lock_configuration = false",
    "COPY runs TO '{tmp}/leak.csv'",                            # no file access
    "ATTACH '{db}' AS real",                                    # no handle on the results DB
    "ATTACH '{db}' AS real; DELETE FROM real.all_runs",
    "SELECT * FROM read_csv_auto('{db}')",
    "INSTALL httpfs",
]
# Reads outside the campaign snapshot: files, globbing, network, extensions, settings. With
# the keyword guard bypassed, the sandbox itself must refuse each one.
READ_ESCAPES = [
    "SELECT * FROM read_text('{db}')",
    "SELECT * FROM read_blob('{db}')",
    "SELECT * FROM glob('*')",
    "SELECT * FROM '{db}'",
    "SELECT * FROM read_parquet('https://example.com/x.parquet')",
    "LOAD httpfs",
    "SELECT * FROM duckdb_settings() WHERE name = 'x'; SET enable_external_access = true",
    "SELECT * FROM read_csv_auto('{db}')",
    "COPY runs TO '{tmp}/leak.csv'",
]


@pytest.fixture
def populated(store, policy):
    for name in ("a", "b"):
        camp = Campaign(name, store, policy, 15, seed=1)
        camp.run([random_case(camp.case_rng(i)) for i in range(15)])
    return store


def _fingerprint(store):
    return store.con.execute("SELECT campaign, count(*), sum(hash(COLUMNS(*))) FROM all_runs "
                             "GROUP BY campaign ORDER BY campaign").fetchall()


def test_guard_rejects_writes_and_multiple_statements(populated):
    for bad in ("DROP TABLE all_runs", "SELECT 1; DELETE FROM all_runs",
                "WITH x AS (SELECT 1) INSERT INTO all_runs SELECT * FROM all_runs",
                "ATTACH 'x.duckdb' AS y", "SET threads = 1"):
        with pytest.raises(ValueError, match="read-only"):
            populated.query(bad, "a")


def test_no_path_modifies_stored_runs_even_with_the_guard_bypassed(populated, tmp_path,
                                                                   monkeypatch):
    before = _fingerprint(populated)
    db = populated.con.execute("SELECT path FROM duckdb_databases() WHERE NOT internal "
                               "AND path IS NOT NULL").fetchone()[0]
    # Layer 1 disabled: the write-keyword filter matches nothing...
    monkeypatch.setattr(store_mod, "_FORBIDDEN", __import__("re").compile(r"(?!)"))
    for attempt in WRITE_ATTEMPTS:
        sql = attempt.format(db=db.replace("\\", "/"), tmp=str(tmp_path).replace("\\", "/"))
        try:  # ...and the single-statement / SELECT-only checks are skipped too
            populated._run_sandboxed(sql, "a", max_rows=50, timeout_s=5)
        except Exception:
            pass  # refused inside the sandbox; either way, check the store below
        assert _fingerprint(populated) == before, attempt
    assert not (tmp_path / "leak.csv").exists()
    # The sandbox is rebuilt per query: in-sandbox changes never leak into the next query.
    assert populated.query("SELECT count(*) AS n FROM runs", "a").n[0] == 15


def test_other_campaigns_are_not_readable(populated):
    with pytest.raises(Exception, match="all_runs"):
        populated._run_sandboxed("SELECT count(*) FROM all_runs", "a", 50, 5)
    assert populated.query("SELECT count(DISTINCT campaign) AS c FROM runs", "a").c[0] == 1


def test_slow_query_is_cancelled_gracefully(populated):
    t0 = time.time()
    with pytest.raises(ValueError, match="time limit"):
        populated.query("SELECT count(*) FROM range(100000) a, range(100000) b", "a",
                        timeout_s=0.5)
    assert time.time() - t0 < 5
    assert populated.query("SELECT count(*) AS n FROM runs", "a").n[0] == 15  # still usable


def test_row_limit(populated):
    assert len(populated.query("SELECT * FROM range(1000)", "a", max_rows=7)) == 7
    assert len(populated.query("SELECT * FROM range(200000)", "a", max_rows=10**9)) == 200000
    assert len(populated.query("SELECT * FROM runs WHERE false", "a")) == 0


def test_snapshot_follows_new_runs(populated, policy):
    camp = Campaign("c", populated, policy, 20, seed=2)
    camp.run([random_case(camp.case_rng(i)) for i in range(15)])
    assert populated.query("SELECT count(*) AS n FROM runs", "c").n[0] == 15
    camp.run([random_case(camp.case_rng(i)) for i in range(15, 20)])
    assert populated.query("SELECT count(*) AS n FROM runs", "c").n[0] == 20


def test_keyword_filter_has_no_false_positives_on_strings_and_identifiers(populated):
    """Words like 'set', 'load', 'update' inside string literals, quoted identifiers or
    comments are not statements; the filter must not reject them."""
    for sql in ("SELECT 'set' AS x FROM runs LIMIT 1",
                'SELECT count(*) AS "load" FROM runs',
                "SELECT 1 AS n -- update later\n",
                "SELECT scenario FROM runs WHERE scenario <> 'drop table'",
                "SELECT 1 /* delete; */ AS n"):
        populated.query(sql, "a")


def test_column_allowlist_restricts_the_view(populated):
    df = populated.query("SELECT * FROM runs", "a", columns=("run_idx", "collision"))
    assert list(df.columns) == ["run_idx", "collision"]
    with pytest.raises(Exception, match="seed"):
        populated.query("SELECT seed FROM runs", "a", columns=("run_idx", "collision"))


@pytest.mark.parametrize("attempt", READ_ESCAPES)
def test_sandbox_refuses_reads_outside_the_snapshot(populated, tmp_path, attempt):
    db = populated.con.execute("SELECT path FROM duckdb_databases() WHERE NOT internal "
                               "AND path IS NOT NULL").fetchone()[0]
    sql = attempt.format(db=db.replace("\\", "/"), tmp=str(tmp_path).replace("\\", "/"))
    with pytest.raises(duckdb.Error):  # the sandbox refuses it even with the guard bypassed
        populated._run_sandboxed(sql, "a", max_rows=50, timeout_s=5)
    with pytest.raises((duckdb.Error, ValueError)):  # and so does the full query path
        populated.query(sql, "a")


def test_guard_rejects_non_select_statements_that_the_sandbox_would_tolerate(populated):
    for sql in ("PRAGMA database_list", "CHECKPOINT", "DETACH memory", "LOAD httpfs",
                "USE memory", "RESET memory_limit", "VACUUM"):
        with pytest.raises(ValueError, match="read-only"):
            populated.query(sql, "a")
    dbs = populated._run_sandboxed("SELECT database_name FROM duckdb_databases() "
                                   "WHERE NOT internal", "a", 50, 5)
    assert list(dbs.database_name) == ["memory"]  # nothing but the in-memory sandbox
