"""Held-out evaluation: predicates are frozen before a fresh, independent campaign scores them."""
import json

import pytest

import avval.holdout as ho
from avval.agent import ValidationAgent
from avval.campaign import Campaign
from avval.config import Release
from avval.estimation import run_estimation

CUT_IN = dict(scenario="cut_in", ego_speed=30.0, closing_speed=8.0, headway=0.4, friction=1.0,
              driver_state="attentive")


def _agent_campaign(store, policy, name, pred, seed=5):
    agent = ValidationAgent(Campaign(name, store, policy, 20, seed=seed, method="agent"),
                            client=object())
    agent.call_tool("run_scenarios", {"cases": [CUT_IN] * 4 + [{**CUT_IN, "headway": 1.8}] * 2})
    sql = f"SELECT count(*) AS n FROM runs WHERE {pred}"
    t = json.loads(agent.call_tool("test_predicate", {"where": pred}))
    q = json.loads(agent.call_tool("query_results", {"sql": sql}))
    out = json.loads(agent.call_tool("submit_report", {"summary": "s", "triggering_conditions": [{
        "description": "d", "predicate": pred, "predicate_test_id": t["test_id"],
        "evidence_sql": sql, "evidence_query_id": q["query_id"]}]}))
    assert out["accepted"]


@pytest.fixture
def frozen(store, policy):
    _agent_campaign(store, policy, "agent_s0", "scenario = 'cut_in' AND headway < 0.5")
    _agent_campaign(store, policy, "agent_s1", "scenario = 'cut_in' AND headway = 0.3", seed=6)
    return ho.freeze_predicates(store, ["agent_s0", "agent_s1"], Release.build(policy))


def test_freeze_reads_verified_evidence_bundles(frozen, tmp_path):
    assert [p["predicate"] for p in frozen["predicates"]] == [
        "scenario = 'cut_in' AND headway < 0.5", "scenario = 'cut_in' AND headway = 0.3"]
    assert ho.load_frozen()["set_sha256"] == frozen["set_sha256"]
    b = json.loads((tmp_path / "evidence_agent_s0.json").read_text())
    b["conditions"][0]["predicate"] = "TRUE"
    (tmp_path / "evidence_agent_s0.json").write_text(json.dumps(b))
    with pytest.raises(ValueError, match="hash"):
        ho._bundle_predicates("agent_s0")


def test_a_frozen_set_cannot_be_edited(frozen, tmp_path):
    f = json.loads((tmp_path / "frozen_predicates.json").read_text())
    f["predicates"][0]["predicate"] = "scenario = 'cut_in' AND headway < 0.6"
    (tmp_path / "frozen_predicates.json").write_text(json.dumps(f))
    with pytest.raises(ValueError, match="edited after freezing"):
        ho.load_frozen()


def test_the_discovery_data_is_never_the_hold_out(store, policy, frozen):
    run_estimation(store, policy, 30, seed=0, name="estimate")
    proto = ho.freeze_holdout_protocol(store, frozen, Release.build(policy), 200, seed=11)
    with pytest.raises(ValueError, match="not the frozen hold-out"):
        ho.check_holdout(store, frozen, proto, "estimate")
    with pytest.raises(ValueError, match="seed"):
        ho.freeze_holdout_protocol(store, frozen, Release.build(policy), 200, seed=5,
                                   path=ho.PROTOCOL_PATH.with_name("other.json"))


def test_seed_and_size_are_frozen_before_execution(store, policy, frozen):
    rel = Release.build(policy)
    proto = ho.freeze_holdout_protocol(store, frozen, rel, 200, seed=11)
    assert (proto["seed"], proto["planned_runs"]) == (11, 200)
    assert ho.load_holdout_protocol(frozen, rel)["protocol_id"] == proto["protocol_id"]
    with pytest.raises(ValueError, match="different hold-out protocol"):
        ho.freeze_holdout_protocol(store, frozen, rel, 100_000, seed=4242)
    ho.run_holdout(store, policy, frozen, proto)
    rec = store.get_campaign("holdout")
    assert (rec["seed"], rec["planned_runs"], rec["protocol_id"]) == (11, 200, proto["protocol_id"])
    # an exploratory hold-out of another size is a different kind and is never accepted
    ho.run_exploratory_holdout(store, policy, frozen, 50, seed=12, name="explore")
    with pytest.raises(ValueError, match="not the frozen hold-out"):
        ho.check_holdout(store, frozen, proto, "explore")


def test_an_edited_hold_out_protocol_is_refused(store, policy, frozen, tmp_path):
    ho.freeze_holdout_protocol(store, frozen, Release.build(policy), 200, seed=11)
    p = json.loads(ho.PROTOCOL_PATH.read_text())
    p["planned_runs"] = 100
    ho.PROTOCOL_PATH.write_text(json.dumps(p))
    with pytest.raises(ValueError, match="does not match its protocol ID"):
        ho.load_holdout_protocol(frozen)


def test_hold_out_under_another_release_or_runtime_is_rejected(store, policy, frozen,
                                                               monkeypatch):
    rel = Release.build(policy)
    proto = ho.freeze_holdout_protocol(store, frozen, rel, 120, seed=11)
    ho.run_holdout(store, policy, frozen, proto)
    other = rel.with_overrides({"exposure": {"factors": {"driver_state": {"weights": {
        "attentive": 0.7, "distracted": 0.3}}}}})
    with pytest.raises(ValueError, match="current release differs"):
        ho.evaluate(store, frozen, proto, "holdout", other)
    monkeypatch.setattr("avval.provenance.runtime_id", lambda fp=None: "0" * 64)
    with pytest.raises(ValueError, match="runtime"):
        ho.evaluate(store, frozen, proto, "holdout", rel)


def test_hold_out_evaluation_classifies_support(store, policy, frozen, tmp_path):
    rel = Release.build(policy)
    proto = ho.freeze_holdout_protocol(store, frozen, rel, 200, seed=11)
    ho.run_holdout(store, policy, frozen, proto)
    rows = ho.evaluate(store, frozen, proto, "holdout", rel)
    by = {r["predicate"]: r for r in rows}
    point = by["scenario = 'cut_in' AND headway = 0.3"]
    assert point["support"] == "exact-point description" and point["runs_inside"] == 0
    assert by["scenario = 'cut_in' AND headway < 0.5"]["exposure_mass"] > 0
    path = ho.write_holdout(store, frozen, proto, "holdout", rel)
    text = open(path, encoding="utf-8").read()
    assert "Only `exposure-supported` conditions generalise" in text
    assert json.loads((tmp_path / "holdout_predicates.json").read_text())[
        "holdout_protocol_id"] == proto["protocol_id"]


def test_exposure_mass_is_undefined_for_outcome_predicates(policy):
    rel = Release.build(policy)
    assert ho.exposure_mass("collision AND headway < 0.5", rel) is None
    m = ho.exposure_mass("scenario = 'cut_in'", rel, n=20_000)
    assert m == pytest.approx(0.4, abs=0.02)


def test_support_classes_distinguish_zero_measure_from_a_small_hold_out():
    assert ho.support_class("headway = 0.3", 0.0, 0) == "exact-point description"
    assert ho.support_class("headway < 0.3", 0.0, 0).startswith("unsupported (zero exposure")
    assert ho.support_class("headway < 0.4", 0.002, 0).startswith("not observed")
    assert ho.support_class("collision", None, 0).startswith("unsupported (no hold-out")
    assert ho.support_class("headway < 0.4", 0.0005, 3).startswith("neighbourhood")
    assert ho.support_class("headway < 0.9", 0.05, 40) == "exposure-supported"
