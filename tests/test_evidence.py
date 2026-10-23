"""The evidence protocol is mandatory: incomplete submissions are rejected, never annotated."""
import json

import pytest

from avval.agent import ValidationAgent
from avval.campaign import Campaign

CUT_IN = dict(scenario="cut_in", ego_speed=30.0, closing_speed=8.0, headway=0.4, friction=1.0,
              driver_state="attentive")
PRED = "scenario = 'cut_in' AND headway < 0.5"
SQL = f"SELECT count(*) AS n FROM runs WHERE {PRED} AND collision"


@pytest.fixture
def agent(store, policy):
    a = ValidationAgent(Campaign("ev", store, policy, 30), client=object())
    a.call_tool("run_scenarios", {"cases": [CUT_IN] * 6 + [{**CUT_IN, "headway": 1.8}] * 4})
    return a


def _call(agent, name, args):
    return json.loads(agent.call_tool(name, args))


def _ids(agent, pred=PRED, sql=SQL):
    t = _call(agent, "test_predicate", {"where": pred})
    q = _call(agent, "query_results", {"sql": sql})
    return t["test_id"], q["query_id"]


def _submit(agent, **tc):
    return _call(agent, "submit_report", {"summary": "s", "triggering_conditions": [tc]})


def _good(agent):
    tid, qid = _ids(agent)
    return dict(description="close fast cut-ins", predicate=PRED, predicate_test_id=tid,
                evidence_sql=SQL, evidence_query_id=qid)


def test_complete_submission_is_accepted_and_bundled(agent, tmp_path):
    out = _submit(agent, **_good(agent))
    assert out == {"accepted": True, "conditions_accepted": 1}
    b = json.loads((tmp_path / "evidence_ev.json").read_text())
    c = b["conditions"][0]
    assert c["test"]["where"] == PRED and c["evidence"]["sql"] == SQL
    assert len(c["condition_sha256"]) == 64 and len(b["bundle_sha256"]) == 64


@pytest.mark.parametrize("field, value, problem", [
    ("predicate", "", "missing predicate"),
    ("predicate_test_id", "", "missing predicate_test_id"),
    ("predicate_test_id", "deadbeef0000", "does not name a successful test_predicate"),
    ("evidence_query_id", "", "missing evidence_query_id"),
    ("evidence_sql", "SELECT count(*) AS n FROM runs", "does not contain the predicate"),
    ("description", "", "missing description"),
])
def test_incomplete_submission_is_rejected(agent, field, value, problem):
    tc = _good(agent)
    tc[field] = value
    out = _submit(agent, **tc)
    assert out["accepted"] is False and any(problem in p for p in out["problems"])
    assert agent.report_path is None
    assert agent.campaign.record["status"] != "COMPLETE"


def test_untested_predicate_is_rejected(agent):
    tc = _good(agent)
    tid, _ = _ids(agent, pred="headway < 0.5")
    tc["predicate_test_id"] = tid  # a test of a different predicate
    out = _submit(agent, **tc)
    assert not out["accepted"] and any("different predicate" in p for p in out["problems"])


def test_failed_evidence_sql_is_a_failed_submission(agent):
    bad_sql = f"SELECT no_such_column FROM runs WHERE {PRED}"
    q = _call(agent, "query_results", {"sql": bad_sql})
    assert "error" in q                     # the query failed: there is no query_id to cite
    tc = _good(agent)
    tc["evidence_sql"] = bad_sql
    out = _submit(agent, **tc)
    assert not out["accepted"] and any("ran different SQL" in p for p in out["problems"])


def test_evidence_with_no_rows_is_rejected(agent):
    sql = f"SELECT run_idx FROM runs WHERE {PRED} AND false"
    tid, qid = _ids(agent, sql=sql)
    out = _submit(agent, description="d", predicate=PRED, predicate_test_id=tid,
                  evidence_sql=sql, evidence_query_id=qid)
    assert not out["accepted"] and any("no rows" in p for p in out["problems"])


def test_stale_evidence_after_more_runs_is_rejected(agent):
    tc = _good(agent)
    agent.call_tool("run_scenarios", {"cases": [CUT_IN]})
    out = _submit(agent, **tc)
    assert not out["accepted"]
    assert any("re-run test_predicate" in p for p in out["problems"])
    assert any("re-run it on the final data" in p for p in out["problems"])
    assert _submit(agent, **_good(agent))["accepted"]  # fixed: accepted


def test_one_bad_condition_rejects_the_whole_report(agent):
    good = _good(agent)
    out = _call(agent, "submit_report", {"summary": "s", "triggering_conditions": [
        good, {**good, "predicate": ""}]})
    assert not out["accepted"] and all(p.startswith("condition 2") for p in out["problems"])


def test_incompatible_evidence_artifact_is_rejected(agent):
    """A query id from a different ledger (another campaign) is not evidence here."""
    from avval.evidence import Ledger
    other = Ledger("other")
    qid = other.record_query(SQL, [{"n": 3}], False, agent.campaign.used)
    tc = _good(agent)
    tc["evidence_query_id"] = qid
    out = _submit(agent, **tc)
    assert not out["accepted"]


def test_no_tools_after_submission(agent):
    _submit(agent, **_good(agent))
    assert "already submitted" in agent.call_tool("run_scenarios", {"cases": [CUT_IN]})
