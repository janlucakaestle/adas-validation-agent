"""The read-only SQL guard, and the sandbox behind it that holds even if the guard is bypassed."""
import time

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


@pytest.fixture
def populated(store, policy):
    for name in ("a", "b"):
        camp = Campaign(name, store, policy, 15, seed=1)
        camp.run([random_case(camp.rng) for _ in range(15)])
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
    camp = Campaign("a", populated, policy, 20, seed=2, fresh=False)
    assert populated.query("SELECT count(*) AS n FROM runs", "a").n[0] == 15
    camp.run([random_case(camp.rng) for _ in range(5)])
    assert populated.query("SELECT count(*) AS n FROM runs", "a").n[0] == 20
