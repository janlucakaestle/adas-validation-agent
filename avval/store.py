"""DuckDB results store. Every simulated run is one row, tagged with its campaign."""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa

from . import RESULTS_DIR

DB_PATH = RESULTS_DIR / "runs.duckdb"
QUERY_TIMEOUT_S = 10.0   # per query; generous for this data size, stops runaway agent SQL
SANDBOX_MEMORY = "1GB"   # memory cap of the query sandbox
_CHUNK_ROWS = 65_536     # results are streamed in chunks, so max_rows is never pre-allocated

SCHEMA = """
CREATE TABLE IF NOT EXISTS all_runs (
    campaign VARCHAR, run_idx INTEGER, seed BIGINT,
    scenario VARCHAR, ego_speed DOUBLE,
    headway DOUBLE,        -- s; the initial gap is headway * ego_speed
    initial_gap_m DOUBLE,
    lead_decel DOUBLE,     -- m/s^2, lead_brake only (NULL for cut_in)
    closing_speed DOUBLE,  -- m/s, cut_in only (NULL for lead_brake)
    friction DOUBLE, driver_state VARCHAR,
    driver_category VARCHAR,  -- intended_use | foreseeable_misuse, from odd.yaml
    collision BOOLEAN, impact_speed DOUBLE,
    min_ttc DOUBLE,        -- before impact; NULL if the vehicles never close
    min_ttc_accel DOUBLE,  -- acceleration-aware TTC; NULL if the gap never closes
    min_thw DOUBLE,        -- after the first 2 s; NULL if no sample qualifies
    min_gap DOUBLE,        -- NULL for a collision
    max_decel DOUBLE,
    max_jerk DOUBLE,       -- from 0.5 s moving-average acceleration
    max_jerk_raw DOUBLE,   -- from raw 20 Hz differences
    tor_issued BOOLEAN, tor_time DOUBLE,
    takeover_time DOUBLE, duration DOUBLE,
    preventable BOOLEAN,      -- FALSE if the ideal reference also collides (avval/reference.py)
    ccd_preventable BOOLEAN   -- careful-competent-driver reference; NULL while disabled
);
CREATE TABLE IF NOT EXISTS campaigns (
    name VARCHAR, created TIMESTAMP, method VARCHAR, budget INTEGER, seed BIGINT,
    provenance VARCHAR  -- JSON text, see avval/provenance.py
);
"""
COLUMNS = ["campaign", "run_idx", "seed", "scenario", "ego_speed", "headway", "initial_gap_m",
           "lead_decel", "closing_speed", "friction", "driver_state", "driver_category",
           "collision", "impact_speed", "min_ttc", "min_ttc_accel", "min_thw", "min_gap",
           "max_decel", "max_jerk", "max_jerk_raw", "tor_issued", "tor_time", "takeover_time",
           "duration", "preventable", "ccd_preventable"]
_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|attach|copy|pragma|"
                        r"install|load|export|import|call|set)\b", re.I)


def _arrow_reader(result, batch_size: int):
    """Streaming Arrow reader over a DuckDB result (new API name first, then the old one)."""
    if hasattr(result, "to_arrow_reader"):
        return result.to_arrow_reader(batch_size)
    return result.fetch_record_batch(batch_size)


class Store:
    def __init__(self, path: Path | str = DB_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self._snapshots: dict = {}
        self.con.execute(SCHEMA)
        self._check_schema(path)

    def _check_schema(self, path) -> None:
        """Refuse a database written by an older version instead of migrating it: the ODD,
        driver model and metrics have changed, so old rows would be silently misleading."""
        cols = [r[0] for r in self.con.execute("DESCRIBE all_runs").fetchall()]
        if set(cols) != set(COLUMNS):
            missing = sorted(set(COLUMNS) - set(cols))
            extra = sorted(set(cols) - set(COLUMNS))
            self.con.close()
            raise RuntimeError(
                f"{path} was written by an older version of avval (missing columns: {missing}; "
                f"obsolete columns: {extra}). Move or delete it and re-run the campaigns.")

    def reset_campaign(self, campaign: str) -> None:
        self.con.execute("DELETE FROM all_runs WHERE campaign = ?", [campaign])
        self._snapshots.pop(campaign, None)
        self.con.execute("DELETE FROM campaigns WHERE name = ?", [campaign])

    def register_campaign(self, name: str, method: str, budget: int, seed: int,
                          provenance: dict) -> None:
        self.con.execute("INSERT INTO campaigns VALUES (?, ?, ?, ?, ?, ?)",
                         [name, datetime.now(), method, budget, seed,
                          json.dumps(provenance, sort_keys=True)])

    def campaign_info(self, name: str) -> list[dict]:
        """Every registration of a campaign, oldest first (more than one if it was reopened)."""
        df = self.con.execute("SELECT * FROM campaigns WHERE name = ? ORDER BY created",
                              [name]).df()
        return [{**rec, "provenance": json.loads(rec["provenance"])}
                for rec in df.to_dict("records")]

    def insert(self, rows: list[dict]) -> None:
        if not rows:
            return
        df = pd.DataFrame(rows).reindex(columns=COLUMNS)  # noqa: F841 - referenced by DuckDB below
        self.con.execute("INSERT INTO all_runs BY NAME SELECT * FROM df")
        for campaign in {r["campaign"] for r in rows}:
            self._snapshots.pop(campaign, None)

    def n_runs(self, campaign: str) -> int:
        return self.con.execute("SELECT count(*) FROM all_runs WHERE campaign = ?",
                                [campaign]).fetchone()[0]

    def campaign_df(self, campaign: str) -> pd.DataFrame:
        return self.con.execute("SELECT * FROM all_runs WHERE campaign = ? ORDER BY run_idx",
                                [campaign]).df()

    def _snapshot(self, campaign: str):
        """The campaign's rows as an immutable Arrow table, cached until the campaign changes."""
        snap = self._snapshots.get(campaign)
        if snap is None:
            res = self.con.execute("SELECT * FROM all_runs WHERE campaign = ? ORDER BY run_idx",
                                   [campaign])
            snap = (res.to_arrow_table() if hasattr(res, "to_arrow_table")
                    else res.fetch_arrow_table())
            # DuckDB's Arrow export keeps about 8 MB of buffer per column alive (about 180 MB
            # per cached 300-run campaign, outside DuckDB's own memory accounting), so a
            # 200-campaign benchmark ran out of memory. Copying keeps only the data.
            snap = pa.concat_tables([snap, snap.slice(0, 0)]).combine_chunks()
            self._snapshots[campaign] = snap
        return snap

    def query(self, sql: str, campaign: str, max_rows: int = 50,
              timeout_s: float = QUERY_TIMEOUT_S) -> pd.DataFrame:
        """Read-only SQL over one campaign, exposed as the table `runs`.

        Used for the agent's queries, the agent's evidence SQL in reports, and the criteria.
        Two layers, because the first is pattern matching and not a security boundary:
        1. A filter that accepts a single SELECT/WITH statement without write keywords.
        2. The statement runs in a fresh in-memory DuckDB connection whose only table is a
           read-only view (`runs`) over a snapshot of this campaign's rows. It has no handle
           on the results database, external access (ATTACH, COPY, file reads) is disabled
           and the configuration is locked, so even a statement that got past the filter can
           neither read other campaigns nor change stored runs. A timer cancels queries
           that run longer than `timeout_s`, memory is capped, and at most `max_rows` rows
           are returned.
        """
        stmt = sql.strip().rstrip(";")
        if ";" in stmt or not re.match(r"^\s*(select|with)\b", stmt, re.I) or _FORBIDDEN.search(stmt):
            raise ValueError("Only a single read-only SELECT/WITH statement is allowed.")
        return self._run_sandboxed(stmt, campaign, max_rows, timeout_s)

    def _run_sandboxed(self, stmt: str, campaign: str, max_rows: int,
                       timeout_s: float) -> pd.DataFrame:
        box = duckdb.connect(":memory:")
        try:
            box.register("runs", self._snapshot(campaign))
            box.execute(f"SET memory_limit = '{SANDBOX_MEMORY}'")
            box.execute("SET enable_external_access = false")
            box.execute("SET lock_configuration = true")
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
        finally:
            box.close()
