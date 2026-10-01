"""The agent's test_predicate tool: check a candidate condition on its own runs."""
import json

import pytest

from avval.agent import TOOLS, ValidationAgent
from avval.campaign import Campaign
from avval.config import driver_attributes
from avval.evaluation import predicate_stats


def _row(campaign, i, failed, headway):
    r = dict(campaign=campaign, run_idx=i, seed=i, scenario="cut_in", ego_speed=30.0,
             headway=headway, initial_gap_m=headway * 30.0,
             closing_speed=5.0, friction=1.0, driver_state="attentive", collision=failed,
             preventable=True, tor_issued=False, min_ttc=None if failed else 5.0)
    return {**r, **driver_attributes("attentive")}


@pytest.fixture
def synthetic(store):
    # 10 runs at headways 0.3, 0.4, ..., 1.2: the four below 0.65 s collide, the rest are fine.
    store.insert([_row("mine", i, failed=i < 4, headway=0.3 + 0.1 * i) for i in range(10)])
    # another campaign where everything fails: must be invisible to "mine"
    store.insert([_row("other", i, failed=True, headway=1.9) for i in range(20)])
    return store


def test_exact_failure_predicate_has_inside_rate_one(synthetic):
    r = predicate_stats(synthetic, "mine", "headway < 0.65")
    assert (r["runs_inside"], r["runs_outside"]) == (4, 6)
    assert r["target_rate_inside"] == 1.0 and r["target_rate_outside"] == 0.0
    assert r["lift"] is None  # undefined when nothing fails outside
    assert r["inside_rate_ci95"][1] == 1.0


def test_lift_and_interval_for_a_partial_condition(synthetic):
    r = predicate_stats(synthetic, "mine", "headway < 0.85")  # 6 inside, 4 of them failing
    assert r["target_rate_inside"] == pytest.approx(4 / 6)
    assert r["target_rate_outside"] == 0.0
    lo, hi = r["inside_rate_ci95"]
    assert lo < 4 / 6 < hi


def test_other_campaigns_are_invisible(synthetic):
    r = predicate_stats(synthetic, "mine", "headway >= 1.5")
    assert r["runs_inside"] == 0 and r["runs_outside"] == 10


@pytest.mark.parametrize("bad", ["true; DELETE FROM runs", "headway < 1) OR (DROP TABLE runs",
                                 "no_such_column > 1"])
def test_invalid_or_writing_predicates_are_rejected_with_a_reason(synthetic, policy, bad):
    agent = ValidationAgent(Campaign("mine", synthetic, policy, 10, fresh=False), client=object())
    out = json.loads(agent.call_tool("test_predicate", {"where": bad}))
    assert "error" in out
    assert synthetic.n_runs("mine") == 10 and synthetic.n_runs("other") == 20


def test_calls_are_logged_and_linked_to_submitted_conditions(synthetic, policy):
    assert "test_predicate" in {t["name"] for t in TOOLS}
    agent = ValidationAgent(Campaign("mine", synthetic, policy, 10, fresh=False), client=object())
    agent.call_tool("test_predicate", {"where": "headway < 0.85"})
    agent.call_tool("test_predicate", {"where": "headway  <  0.65"})
    agent.call_tool("submit_report", {"summary": "s", "triggering_conditions": [{
        "description": "Close cut-ins", "predicate": "headway < 0.65",
        "evidence_sql": "SELECT count(*) AS n FROM runs WHERE headway < 0.65 AND collision"}]})
    text = open(agent.report_path, encoding="utf-8").read()
    assert "## Hypothesis tests" in text and "`headway < 0.85`" in text
    assert "TC-01: submitted predicate tested 1 time(s) (tests 2)." in text
    assert "Predicate: `headway < 0.65`" in text
