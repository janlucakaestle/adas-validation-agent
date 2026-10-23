"""DuckDB results store (schema v3). Every simulated run is one row, tagged with its campaign.

Schema versioning: a `schema_meta` table records the schema version and the metric-semantics
version. Opening a database checks the versions, every column name and type, and the key
constraints; a database written by an older version (including one with identically named
but semantically different columns) is refused, never migrated silently. Old databases are
kept as they are and read-only; their results are superseded and must be re-run (see
REMEDIATION_SUMMARY.md, "Breaking changes and migrations").

Campaign lifecycle: every campaign has exactly one row in `campaigns` (primary key), with
its planned and completed run counts and a status (CREATED, RUNNING, COMPLETE, FAILED),
its release, runtime and exposure-model identities and, once complete, a hash of its data.
`(campaign, run_idx)` is the primary key of `all_runs`, so a run can never be stored twice.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import threading
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa

from . import RESULTS_DIR

SCHEMA_VERSION = "4"            # v4: evidence_mode, holdout_exploratory kind
METRIC_SEMANTICS_VERSION = "4"  # v4: fixed hand-back oracle capability
DB_PATH = RESULTS_DIR / "runs_v4.duckdb"
QUERY_TIMEOUT_S = 10.0   # per query; generous for this data size, stops runaway agent SQL
SANDBOX_MEMORY = "1GB"   # memory cap of the query sandbox
_CHUNK_ROWS = 65_536     # results are streamed in chunks, so max_rows is never pre-allocated

STATUSES = ("CREATED", "RUNNING", "COMPLETE", "FAILED")
KINDS = ("search", "nominal_estimation", "holdout_evaluation", "holdout_exploratory",
         "sensitivity", "compatibility_replay")
# final: created with `--final` from a clean, committed, lock-matching tree; the only mode
# whose campaigns can be release or confirmatory evidence. development: everything else.
EVIDENCE_MODES = ("final", "development")
END_STATES = ("collision", "both_stopped", "horizon_safe", "horizon_unresolved")

# (name, type, nullable). Order matters: it is the stored column order.
RUN_COLUMNS = [
    ("campaign", "VARCHAR", False), ("run_idx", "INTEGER", False), ("seed", "BIGINT", False),
    ("scenario", "VARCHAR", False), ("ego_speed", "DOUBLE", False),
    ("headway", "DOUBLE", False),          # s; the initial gap is headway * ego_speed
    ("initial_gap_m", "DOUBLE", False),
    ("lead_decel", "DOUBLE", True),        # m/s^2, lead_brake only (NULL for cut_in)
    ("closing_speed", "DOUBLE", True),     # m/s, cut_in only (NULL for lead_brake)
    ("friction", "DOUBLE", False), ("driver_state", "VARCHAR", False),
    ("driver_category", "VARCHAR", False),  # intended_use | foreseeable_misuse
    ("hazard_onset_s", "DOUBLE", False),
    # scenario properties from the references (independent of the system's actions)
    ("avoidable_by_reference", "BOOLEAN", False),
    ("handback_required", "BOOLEAN", False),
    ("ccd_avoidable_by_reference", "BOOLEAN", True),
    # outcomes
    ("collision", "BOOLEAN", False), ("impact_speed", "DOUBLE", False),
    ("collision_time", "DOUBLE", True), ("end_state", "VARCHAR", False),
    ("min_ttc", "DOUBLE", True), ("min_ttc_accel", "DOUBLE", True),
    ("min_thw", "DOUBLE", True), ("min_gap", "DOUBLE", True),
    ("max_decel", "DOUBLE", False), ("max_jerk", "DOUBLE", True),
    ("max_jerk_automated", "DOUBLE", True), ("max_jerk_raw", "DOUBLE", False),
    ("max_required_decel", "DOUBLE", True),
    ("tor_issued", "BOOLEAN", False), ("tor_time", "DOUBLE", True),
    ("tor_reason", "VARCHAR", True), ("takeover_time", "DOUBLE", True),
    ("duration", "DOUBLE", False),
]
COLUMNS = [c for c, _, _ in RUN_COLUMNS]
CAMPAIGN_COLUMNS = [
    ("campaign_id", "VARCHAR", False), ("kind", "VARCHAR", False), ("method", "VARCHAR", False),
    ("created", "TIMESTAMP", False), ("updated", "TIMESTAMP", False),
    ("seed", "BIGINT", False), ("planned_runs", "INTEGER", False),
    ("completed_runs", "INTEGER", False), ("status", "VARCHAR", False),
    ("stop_reason", "VARCHAR", True), ("release_id", "VARCHAR", False),
    ("runtime_id", "VARCHAR", False), ("exposure_model_id", "VARCHAR", False),
    ("protocol_id", "VARCHAR", True), ("case_source", "VARCHAR", False),
    ("overrides", "VARCHAR", False), ("provenance", "VARCHAR", False),
    ("data_sha256", "VARCHAR", True), ("resumed", "INTEGER", False),
    ("evidence_mode", "VARCHAR", False),
]


def _ddl(cols) -> str:
    return ",\n    ".join(f"{n} {t}{'' if null else ' NOT NULL'}" for n, t, null in cols)


SCHEMA = f"""
CREATE TABLE schema_meta (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL);
CREATE TABLE campaigns (
    {_ddl(CAMPAIGN_COLUMNS)},
    PRIMARY KEY (campaign_id),
    CHECK (status IN ({", ".join(repr(s) for s in STATUSES)})),
    CHECK (kind IN ({", ".join(repr(k) for k in KINDS)})),
    CHECK (evidence_mode IN ({", ".join(repr(m) for m in EVIDENCE_MODES)})),
    CHECK (completed_runs >= 0 AND completed_runs <= planned_runs)
);
CREATE TABLE all_runs (
    {_ddl(RUN_COLUMNS)},
    PRIMARY KEY (campaign, run_idx),
    FOREIGN KEY (campaign) REFERENCES campaigns (campaign_id),
    CHECK (end_state IN ({", ".join(repr(s) for s in END_STATES)})),
    CHECK (run_idx >= 0)
);
"""

_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|"
                        r"pragma|install|load|export|import|call|set|reset|checkpoint|"
                        r"vacuum|use)\b", re.I)
# String literals, quoted identifiers and comments are removed before the keyword scan, so
# a word like 'set' inside a string or a column alias "load" is not a false positive.
_STRIP = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/", re.S)


class LegacyDatabaseError(RuntimeError):
    """The database was written by an incompatible (older or newer) schema."""


class CampaignExistsError(ValueError):
    pass


def _arrow_reader(result, batch_size: int):
    """Streaming Arrow reader over a DuckDB result (new API name first, then the old one)."""
    if hasattr(result, "to_arrow_reader"):
        return result.to_arrow_reader(batch_size)
    return result.fetch_record_batch(batch_size)


def check_read_only_sql(sql: str) -> str:
    """Layer 1 of the SQL guard: a single SELECT/WITH statement without write keywords
    (outside string literals, quoted identifiers and comments). Returns the statement."""
    stmt = sql.strip().rstrip(";").strip()
    bare = _STRIP.sub(" ", stmt)
    if (";" in bare or not re.match(r"^\s*(select|with)\b", bare, re.I)
            or _FORBIDDEN.search(bare)):
        raise ValueError("Only a single read-only SELECT/WITH statement is allowed.")
    return stmt


class Store:
    def __init__(self, path: Path | str | None = None, read_only: bool = False):
        path = DB_PATH if path is None else path
        self.path = str(path)
        if self.path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.path, read_only=read_only)
        self._snapshots: dict = {}
        tables = {r[0] for r in self.con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()}
        if not tables and not read_only:
            self.con.execute(SCHEMA)
            self.con.execute("INSERT INTO schema_meta VALUES (?, ?), (?, ?), (?, ?)",
                             ["schema_version", SCHEMA_VERSION,
                              "metric_semantics_version", METRIC_SEMANTICS_VERSION,
                              "created", datetime.now().isoformat(timespec="seconds")])
        self._check_schema(tables or {"schema_meta", "campaigns", "all_runs"})

    # ------------------------------------------------------------ schema
    def _refuse(self, why: str) -> None:
        self.con.close()
        raise LegacyDatabaseError(
            f"{self.path}: {why}. This database was written by an incompatible version of "
            f"avval (expected schema {SCHEMA_VERSION}, metric semantics "
            f"{METRIC_SEMANTICS_VERSION}). Its results are not migrated, because the meaning "
            "of stored metrics changed; keep it as a read-only legacy artifact and re-run "
            "the campaigns into a new database (see REMEDIATION_SUMMARY.md).")

    def _check_schema(self, tables: set) -> None:
        if "schema_meta" not in tables:
            self._refuse("no schema_meta table (legacy schema, pre-v3)")
        meta = dict(self.con.execute("SELECT key, value FROM schema_meta").fetchall())
        if meta.get("schema_version") != SCHEMA_VERSION:
            self._refuse(f"schema version {meta.get('schema_version')!r}")
        if meta.get("metric_semantics_version") != METRIC_SEMANTICS_VERSION:
            self._refuse(f"metric semantics version {meta.get('metric_semantics_version')!r}")
        for table, cols in (("all_runs", RUN_COLUMNS), ("campaigns", CAMPAIGN_COLUMNS)):
            got = [(r[0], r[1], r[2] == "YES") for r in
                   self.con.execute(f"DESCRIBE {table}").fetchall()]
            if got != list(cols):
                self._refuse(f"table {table} has columns {got}, expected {list(cols)}")
        cons = {(r[0], r[1], tuple(r[2])) for r in self.con.execute(
            "SELECT table_name, constraint_type, constraint_column_names "
            "FROM duckdb_constraints() WHERE constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')"
        ).fetchall()}
        need = {("all_runs", "PRIMARY KEY", ("campaign", "run_idx")),
                ("campaigns", "PRIMARY KEY", ("campaign_id",)),
                ("all_runs", "FOREIGN KEY", ("campaign",))}
        if not need <= cons:
            self._refuse(f"missing key constraints {sorted(need - cons)}")

    # ------------------------------------------------------------ campaigns
    def create_campaign(self, rec: dict) -> None:
        now = datetime.now()
        row = {"created": now, "updated": now, "completed_runs": 0, "status": "CREATED",
               "stop_reason": None, "data_sha256": None, "resumed": 0, "protocol_id": None,
               "evidence_mode": "development", **rec}
        row["overrides"] = json.dumps(row["overrides"], sort_keys=True)
        row["provenance"] = json.dumps(row["provenance"], sort_keys=True, default=str)
        names = [c for c, _, _ in CAMPAIGN_COLUMNS]
        try:
            self.con.execute(f"INSERT INTO campaigns ({', '.join(names)}) VALUES "
                             f"({', '.join('?' * len(names))})", [row[n] for n in names])
        except duckdb.ConstraintException:
            raise CampaignExistsError(
                f"campaign {rec['campaign_id']!r} already exists. Campaign identities are "
                "immutable: choose a new name, resume it explicitly (Campaign.resume), or "
                "delete it explicitly (Store.delete_campaign).") from None

    def import_campaign(self, rec: dict, df: pd.DataFrame) -> None:
        """Copy a COMPLETE campaign (record and rows) from another store, verifying that the
        copied rows reproduce the recorded data hash (used to persist sensitivity variants
        that ran in worker processes)."""
        keep = {k: rec[k] for k in ("campaign_id", "kind", "method", "seed", "planned_runs",
                                    "release_id", "runtime_id", "exposure_model_id",
                                    "protocol_id", "case_source", "overrides", "provenance",
                                    "evidence_mode")}
        self.create_campaign(keep)
        self.insert(df.astype(object).where(df.notna(), None).to_dict("records"))
        if self.data_hash(rec["campaign_id"]) != rec["data_sha256"]:
            self.delete_campaign(rec["campaign_id"])
            raise ValueError(f"{rec['campaign_id']}: imported rows do not match the data hash")
        self.update_campaign(rec["campaign_id"], status=rec["status"],
                             completed_runs=rec["completed_runs"],
                             stop_reason=rec["stop_reason"], data_sha256=rec["data_sha256"])

    def get_campaign(self, campaign_id: str) -> dict | None:
        df = self.con.execute("SELECT * FROM campaigns WHERE campaign_id = ?",
                              [campaign_id]).df()
        if df.empty:
            return None
        rec = df.iloc[0].to_dict()
        rec["overrides"] = json.loads(rec["overrides"])
        rec["provenance"] = json.loads(rec["provenance"])
        for k in ("seed", "planned_runs", "completed_runs", "resumed"):
            rec[k] = int(rec[k])
        for k in ("stop_reason", "protocol_id", "data_sha256"):
            if pd.isna(rec[k]):
                rec[k] = None
        return rec

    def list_campaigns(self, **where) -> list[dict]:
        clause = " AND ".join(f"{k} = ?" for k in where) or "TRUE"
        ids = [r[0] for r in self.con.execute(
            f"SELECT campaign_id FROM campaigns WHERE {clause} ORDER BY created DESC, "
            "campaign_id", list(where.values())).fetchall()]
        return [self.get_campaign(i) for i in ids]

    def update_campaign(self, campaign_id: str, **fields) -> None:
        fields["updated"] = datetime.now()
        sets = ", ".join(f"{k} = ?" for k in fields)
        self.con.execute(f"UPDATE campaigns SET {sets} WHERE campaign_id = ?",
                         [*fields.values(), campaign_id])

    def delete_campaign(self, campaign_id: str) -> None:
        """Explicitly remove a campaign and its runs (never done implicitly)."""
        self.con.execute("DELETE FROM all_runs WHERE campaign = ?", [campaign_id])
        self.con.execute("DELETE FROM campaigns WHERE campaign_id = ?", [campaign_id])
        self._drop_snapshots(campaign_id)

    # ------------------------------------------------------------ runs
    def insert(self, rows: list[dict]) -> None:
        if not rows:
            return
        df = pd.DataFrame(rows).reindex(columns=COLUMNS)  # noqa: F841 - used by DuckDB below
        self.con.execute("INSERT INTO all_runs BY NAME SELECT * FROM df")
        for campaign in {r["campaign"] for r in rows}:
            self._drop_snapshots(campaign)

    def _drop_snapshots(self, campaign: str) -> None:
        for key in [k for k in self._snapshots if k[0] == campaign]:
            del self._snapshots[key]

    def n_runs(self, campaign: str) -> int:
        return self.con.execute("SELECT count(*) FROM all_runs WHERE campaign = ?",
                                [campaign]).fetchone()[0]

    def max_run_idx(self, campaign: str) -> int:
        r = self.con.execute("SELECT max(run_idx) FROM all_runs WHERE campaign = ?",
                             [campaign]).fetchone()[0]
        return -1 if r is None else int(r)

    def campaign_df(self, campaign: str) -> pd.DataFrame:
        return self.con.execute("SELECT * FROM all_runs WHERE campaign = ? ORDER BY run_idx",
                                [campaign]).df()

    def data_hash(self, campaign: str) -> str:
        """SHA-256 of the campaign's rows (all columns, ordered by run_idx), serialised as
        CSV with round-trip float formatting. Recomputed when evidence is used."""
        df = self.campaign_df(campaign)
        buf = io.StringIO()
        df.to_csv(buf, index=False, float_format="%.17g", lineterminator="\n")
        return hashlib.sha256(buf.getvalue().encode()).hexdigest()

    def _snapshot(self, campaign: str, columns: tuple | None):
        """The campaign's rows as an immutable Arrow table, cached until the campaign changes."""
        key = (campaign, columns)
        snap = self._snapshots.get(key)
        if snap is None:
            cols = ", ".join(columns) if columns else "*"
            res = self.con.execute(f"SELECT {cols} FROM all_runs WHERE campaign = ? "
                                   "ORDER BY run_idx", [campaign])
            snap = (res.to_arrow_table() if hasattr(res, "to_arrow_table")
                    else res.fetch_arrow_table())
            # DuckDB's Arrow export keeps large buffers alive; copying keeps only the data.
            snap = pa.concat_tables([snap, snap.slice(0, 0)]).combine_chunks()
            self._snapshots[key] = snap
        return snap

    # ------------------------------------------------------------ sandboxed SQL
    def query(self, sql: str, campaign: str, max_rows: int = 50,
              timeout_s: float = QUERY_TIMEOUT_S, columns: tuple | None = None
              ) -> pd.DataFrame:
        """Read-only SQL over one campaign, exposed as the table `runs`.

        Used for the agent's queries and evidence SQL, and for every criterion. Layers:
        1. A filter that accepts a single SELECT/WITH statement without write keywords
           (pattern matching, not a security boundary).
        2. The statement runs in a fresh in-memory DuckDB connection whose only table is a
           view (`runs`) over a snapshot of this campaign's rows, optionally restricted to
           `columns` (the agent sees only its allowlist). It has no handle on the results
           database; external access (files, network, ATTACH, COPY) and extension loading
           are disabled and the configuration is locked. A timer cancels queries that run
           longer than `timeout_s`, memory is capped, and at most `max_rows` rows return.
        """
        stmt = check_read_only_sql(sql)
        return self._run_sandboxed(stmt, campaign, max_rows, timeout_s, columns)

    def _open_box(self, campaign: str, columns: tuple | None):
        box = duckdb.connect(":memory:")
        try:
            box.register("runs", self._snapshot(campaign, columns))
            for setting in (f"SET memory_limit = '{SANDBOX_MEMORY}'",
                            "SET autoinstall_known_extensions = false",
                            "SET autoload_known_extensions = false",
                            "SET temp_directory = ''",
                            "SET enable_external_access = false",
                            "SET lock_configuration = true"):
                try:
                    box.execute(setting)
                except duckdb.Error:
                    if "external_access" in setting or "lock_configuration" in setting:
                        raise  # the essential isolation settings must apply
        except BaseException:
            box.close()
            raise
        return box

    @staticmethod
    def _exec(box, stmt: str, max_rows: int, timeout_s: float) -> pd.DataFrame:
        timer = threading.Timer(timeout_s, box.interrupt)
        timer.start()
        try:
            reader = _arrow_reader(box.execute(stmt), min(max_rows, _CHUNK_ROWS))
            batches, n = [], 0
            while n < max_rows:
                try:
                    batch = reader.read_next_batch()
                except StopIteration:
                    break
                batches.append(batch)
                n += batch.num_rows
            table = pa.Table.from_batches(batches, schema=reader.schema)
            return table.slice(0, max_rows).to_pandas()
        except duckdb.InterruptException:
            raise ValueError(f"Query cancelled: it exceeded the {timeout_s:g} s time limit. "
                             "Simplify it or aggregate earlier.") from None
        finally:
            timer.cancel()

    def _run_sandboxed(self, stmt: str, campaign: str, max_rows: int, timeout_s: float,
                       columns: tuple | None = None) -> pd.DataFrame:
        box = self._open_box(campaign, columns)
        try:
            return self._exec(box, stmt, max_rows, timeout_s)
        finally:
            box.close()

    @contextlib.contextmanager
    def session(self, campaign: str, columns: tuple | None = None):
        """One sandbox reused for several guarded read-only queries over a campaign (same
        isolation as `query`, without rebuilding the sandbox per query). Yields a function
        query(sql, max_rows=50, timeout_s=QUERY_TIMEOUT_S)."""
        box = self._open_box(campaign, columns)

        def q(sql: str, max_rows: int = 50, timeout_s: float = QUERY_TIMEOUT_S):
            return self._exec(box, check_read_only_sql(sql), max_rows, timeout_s)
        try:
            yield q
        finally:
            box.close()
