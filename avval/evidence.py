"""Evidence protocol for submitted triggering conditions (mandatory, content-addressed).

Every `test_predicate` and `query_results` call is recorded in a ledger with its complete
input and machine-readable result and a SHA-256 over both; the agent receives a short ID for
each. A submitted triggering condition is accepted only if ALL of the following hold:

1. it has a description and a non-empty, machine-evaluable predicate;
2. `predicate_test_id` names a successful `test_predicate` call whose predicate is the
   submitted one (whitespace/case-normalised) and which ran on the campaign's final data;
3. `evidence_query_id` names a successful `query_results` call whose SQL is the submitted
   `evidence_sql`, which returned at least one row, ran on the final data, and contains the
   predicate (so the evidence is about the condition);
4. re-executing the predicate test and the evidence query at submission reproduces the
   logged results exactly (same hashes).

If any condition fails any requirement, the whole submission is rejected and the agent is
told what is missing; no report is written. A failed evidence query is a failed submission,
never a warning in a finished report. Accepted conditions are written to an evidence bundle
(`results/evidence_<campaign>.json`) with every hash, the full results and the full ledger,
and the Markdown report is rendered from that bundle.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .frozen import canonical_json, content_hash, sha256_text

EVIDENCE_MAX_ROWS = 1000  # rows kept per evidence query (the agent sees fewer)
ID_LEN = 12


def norm_sql(sql: str) -> str:
    """Whitespace- and case-normalised SQL (string literals keep their case)."""
    parts = re.split(r"('(?:[^']|'')*')", sql.strip().rstrip(";"))
    return "".join(p if p.startswith("'") else " ".join(p.split()).lower()
                   for p in parts).strip()


def _rows(df) -> list[dict]:
    return json.loads(df.to_json(orient="records", double_precision=15))


@dataclass
class Ledger:
    campaign: str
    entries: list = field(default_factory=list)  # every recorded call, in order
    tests: dict = field(default_factory=dict)    # id -> test record
    queries: dict = field(default_factory=dict)  # id -> query record

    def _add(self, kind: str, rec: dict) -> str:
        rec = {"seq": len(self.entries), "kind": kind, **rec}
        full = content_hash(rec)
        rec["sha256"] = full
        self.entries.append(rec)
        return full

    def record_test(self, where: str, target: str, result: dict, n_runs: int) -> str:
        full = self._add("test_predicate", {"where": where, "target": target,
                                            "result": result, "n_runs": n_runs})
        short = full[:ID_LEN]
        self.tests[short] = {"id": short, "sha256": full, "where": where, "target": target,
                             "result": result, "n_runs": n_runs,
                             "result_sha256": content_hash(result)}
        return short

    def record_query(self, sql: str, rows: list[dict], truncated: bool, n_runs: int) -> str:
        full = self._add("query_results", {"sql": sql, "rows": rows, "truncated": truncated,
                                           "n_runs": n_runs})
        short = full[:ID_LEN]
        self.queries[short] = {"id": short, "sha256": full, "sql": sql, "rows": rows,
                               "truncated": truncated, "n_runs": n_runs,
                               "rows_sha256": content_hash(rows)}
        return short

    def record_failure(self, tool: str, args: dict, error: str) -> None:
        self._add(f"{tool}:error", {"input": args, "error": error})

    def to_json(self) -> dict:
        return {"campaign": self.campaign, "entries": self.entries,
                "ledger_sha256": content_hash(self.entries)}


def run_evidence_query(iface, sql: str) -> tuple[list[dict], bool]:
    df = iface.query(sql, EVIDENCE_MAX_ROWS + 1)
    truncated = len(df) > EVIDENCE_MAX_ROWS
    return _rows(df.head(EVIDENCE_MAX_ROWS)), truncated


def validate_submission(ledger: Ledger, iface, conditions: list) -> tuple[list[dict], list[str]]:
    """(accepted conditions with evidence, problems). Accepted only if `problems` is empty."""
    problems: list[str] = []
    accepted: list[dict] = []
    n_now = iface.campaign.used
    if not isinstance(conditions, list):
        return [], ["triggering_conditions must be a list"]
    for i, tc in enumerate(conditions, 1):
        label = f"condition {i}"
        own: list[str] = []
        if not isinstance(tc, dict):
            problems.append(f"{label}: must be an object")
            continue
        desc = str(tc.get("description") or "").strip()
        pred = str(tc.get("predicate") or "").strip()
        sql = str(tc.get("evidence_sql") or "").strip()
        tid = str(tc.get("predicate_test_id") or "").strip()
        qid = str(tc.get("evidence_query_id") or "").strip()
        if not desc:
            own.append("missing description")
        if not pred:
            own.append("missing predicate (a SQL WHERE clause over runs)")
        test = ledger.tests.get(tid)
        if not tid:
            own.append("missing predicate_test_id (call test_predicate on the predicate and "
                       "cite the test_id it returns)")
        elif test is None:
            own.append(f"predicate_test_id {tid!r} does not name a successful test_predicate call")
        elif pred and norm_sql(test["where"]) != norm_sql(pred):
            own.append(f"predicate_test_id {tid!r} tested a different predicate "
                       f"({test['where']!r})")
        elif test["n_runs"] != n_now:
            own.append(f"predicate_test_id {tid!r} ran on {test['n_runs']} runs, the campaign "
                       f"now has {n_now}: re-run test_predicate on the final data")
        query = ledger.queries.get(qid)
        if not sql:
            own.append("missing evidence_sql")
        if not qid:
            own.append("missing evidence_query_id (run the evidence SQL with query_results "
                       "and cite the query_id it returns)")
        elif query is None:
            own.append(f"evidence_query_id {qid!r} does not name a successful query_results call")
        else:
            if sql and norm_sql(query["sql"]) != norm_sql(sql):
                own.append(f"evidence_query_id {qid!r} ran different SQL than evidence_sql")
            if not query["rows"]:
                own.append(f"evidence_query_id {qid!r} returned no rows")
            if query["n_runs"] != n_now:
                own.append(f"evidence_query_id {qid!r} ran on {query['n_runs']} runs, the "
                           f"campaign now has {n_now}: re-run it on the final data")
        if pred and sql and norm_sql(pred) not in norm_sql(sql):
            own.append("evidence_sql does not contain the predicate; the evidence must "
                       "select or filter by the condition it supports")
        if not own:  # re-execute: the logged results must reproduce exactly
            try:
                again = iface.test_predicate(test["where"], test["target"])
                if content_hash(again) != test["result_sha256"]:
                    own.append("re-running the predicate test gave a different result")
                rows, truncated = run_evidence_query(iface, query["sql"])
                if content_hash(rows) != query["rows_sha256"]:
                    own.append("re-running the evidence query gave a different result")
            except Exception as e:  # noqa: BLE001 - reported to the agent, never swallowed
                own.append(f"re-execution failed: {type(e).__name__}: {e}")
        if own:
            problems += [f"{label}: {p}" for p in own]
            continue
        record = {"description": desc, "predicate": pred,
                  "predicate_sha256": sha256_text(norm_sql(pred)),
                  "test": {k: test[k] for k in ("id", "sha256", "where", "target", "result",
                                                "result_sha256", "n_runs")},
                  "evidence": {k: query[k] for k in ("id", "sha256", "sql", "rows",
                                                     "truncated", "rows_sha256", "n_runs")}}
        record["condition_sha256"] = content_hash(record)
        accepted.append(record)
    return accepted, problems


def bundle(ledger: Ledger, campaign_record: dict, summary: str, accepted: list[dict],
           author: str) -> dict:
    """The machine-readable evidence bundle written with an accepted report."""
    body = {"schema": "evidence/v3", "campaign": campaign_record["campaign_id"],
            "release_id": campaign_record["release_id"],
            "runtime_id": campaign_record["runtime_id"],
            "protocol_id": campaign_record.get("protocol_id"),
            "data_sha256": campaign_record.get("data_sha256"), "author": author,
            "summary": summary, "conditions": accepted, "ledger": ledger.to_json()}
    body["bundle_sha256"] = sha256_text(canonical_json(body))
    return body


def verify_bundle(b: dict, rec: dict | None, store=None) -> list[str]:
    """Problems with an evidence bundle (empty = verified): its own hash; that it names the
    given campaign record's campaign, release, runtime, protocol and data hash; the ledger
    hash and every entry hash; every condition hash; that each condition's test and query
    are ledger entries with matching content and result hashes; and, with `store` holding
    the campaign's rows, that re-running every test and evidence query on those exact rows
    reproduces the recorded results. A bundle edited after writing fails even if it is
    re-hashed into a package manifest."""
    from .evaluation import predicate_stats
    from .protected import AGENT_COLUMNS
    problems: list[str] = []
    body = {k: v for k, v in b.items() if k != "bundle_sha256"}
    if sha256_text(canonical_json(body)) != b.get("bundle_sha256"):
        problems.append("bundle_sha256 does not match the bundle content")
    if rec is None:
        return problems + ["no campaign record for the bundle"]
    for key, rkey in (("campaign", "campaign_id"), ("release_id", "release_id"),
                      ("runtime_id", "runtime_id"), ("protocol_id", "protocol_id"),
                      ("data_sha256", "data_sha256")):
        if b.get(key) != rec.get(rkey):
            problems.append(f"bundle {key} {b.get(key)!r} != campaign {rec.get(rkey)!r}")
    entries = b["ledger"]["entries"]
    if content_hash(entries) != b["ledger"].get("ledger_sha256"):
        problems.append("ledger_sha256 does not match the ledger entries")
    by_sha = {}
    for e in entries:
        if content_hash({k: v for k, v in e.items() if k != "sha256"}) != e.get("sha256"):
            problems.append(f"ledger entry {e.get('seq')} hash mismatch")
        by_sha[e.get("sha256")] = e
    for i, c in enumerate(b["conditions"], 1):
        if content_hash({k: v for k, v in c.items() if k != "condition_sha256"}) \
                != c.get("condition_sha256"):
            problems.append(f"condition {i}: condition_sha256 mismatch")
        t, q = c["test"], c["evidence"]
        te, qe = by_sha.get(t["sha256"]), by_sha.get(q["sha256"])
        if te is None or te["kind"] != "test_predicate" or any(
                te.get(k) != t[k] for k in ("where", "target", "result", "n_runs")):
            problems.append(f"condition {i}: predicate test is not the ledger entry it cites")
        if content_hash(t["result"]) != t["result_sha256"]:
            problems.append(f"condition {i}: test result hash mismatch")
        if qe is None or qe["kind"] != "query_results" or any(
                qe.get(k) != q[k] for k in ("sql", "rows", "truncated", "n_runs")):
            problems.append(f"condition {i}: evidence query is not the ledger entry it cites")
        if content_hash(q["rows"]) != q["rows_sha256"]:
            problems.append(f"condition {i}: evidence rows hash mismatch")
        if norm_sql(t["where"]) != norm_sql(c["predicate"]):
            problems.append(f"condition {i}: test predicate differs from the condition")
        if store is not None:
            name = rec["campaign_id"]
            if t["n_runs"] != store.n_runs(name) or q["n_runs"] != store.n_runs(name):
                problems.append(f"condition {i}: evidence was not produced on the stored data")
                continue
            again = predicate_stats(store, name, t["where"], t["target"], columns=AGENT_COLUMNS)
            if content_hash(again) != t["result_sha256"]:
                problems.append(f"condition {i}: predicate test does not reproduce on the data")
            df = store.query(q["sql"], name, max_rows=EVIDENCE_MAX_ROWS + 1, columns=AGENT_COLUMNS)
            if content_hash(_rows(df.head(EVIDENCE_MAX_ROWS))) != q["rows_sha256"]:
                problems.append(f"condition {i}: evidence query does not reproduce on the data")
    return problems
