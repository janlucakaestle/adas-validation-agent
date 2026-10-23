"""The agent's test_predicate tool: check a candidate condition on its own runs."""
import json

import pytest

from avval.agent import TOOLS, ValidationAgent
from avval.campaign import Campaign
from avval.evaluation import predicate_stats
from tests.helpers import register, row


@pytest.fixture
def synthetic(store):
    # 10 runs at headways 0.3, 0.4, ..., 1.2: the four below 0.65 s collide, the rest are fine.
    register(store, "mine", planned=10)
    store.insert([row("mine", i, collision=i < 4, headway=0.3 + 0.1 * i,
                      min_ttc=None if i < 4 else 5.0) for i in range(10)])
    register(store, "other")  # another campaign where everything fails: invisible to "mine"
    store.insert([row("other", i, collision=True, headway=1.9) for i in range(20)])
    return store


def test_exact_predicate_has_inside_rate_one(synthetic):
    r = predicate_stats(synthetic, "mine", "headway < 0.65", "collision")
    assert (r["runs_inside"], r["runs_outside"]) == (4, 6)
    assert r["target_rate_inside"] == 1.0 and r["target_rate_outside"] == 0.0
    assert r["lift"] is None  # undefined when nothing fails outside
    assert r["inside_rate_ci95"][1] == 1.0


def test_lift_and_interval_for_a_partial_condition(synthetic):
    r = predicate_stats(synthetic, "mine", "headway < 0.85", "collision")
    assert r["target_rate_inside"] == pytest.approx(4 / 6)
    lo, hi = r["inside_rate_ci95"]
    assert lo < 4 / 6 < hi


def test_other_campaigns_are_invisible(synthetic):
    r = predicate_stats(synthetic, "mine", "headway >= 1.5")
    assert r["runs_inside"] == 0 and r["runs_outside"] == 10


def test_empty_predicate_is_rejected(synthetic):
    with pytest.raises(ValueError, match="empty"):
        predicate_stats(synthetic, "mine", "  ")


def _agent(store, policy):
    return ValidationAgent(Campaign("a", store, policy, 10), client=object())


@pytest.mark.parametrize("bad", ["true; DELETE FROM runs", "headway < 1) OR (DROP TABLE runs",
                                 "no_such_column > 1", "handback_required"])
def test_invalid_writing_or_hidden_predicates_are_rejected(store, policy, bad):
    agent = _agent(store, policy)
    out = json.loads(agent.call_tool("test_predicate", {"where": bad}))
    assert "error" in out


def test_calls_return_a_citable_test_id(store, policy):
    assert "test_predicate" in {t["name"] for t in TOOLS}
    agent = _agent(store, policy)
    a = json.loads(agent.call_tool("test_predicate", {"where": "headway < 0.85"}))
    b = json.loads(agent.call_tool("test_predicate", {"where": "headway < 0.85",
                                                      "target": "near_miss"}))
    assert a["test_id"] != b["test_id"] and a["test_id"] in agent.ledger.tests
