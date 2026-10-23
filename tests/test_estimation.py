"""Search campaigns find failures; only an eligible nominal estimation measures rates."""
import re

import pytest

from avval.agent import ValidationAgent
from avval.baselines import auto_report, coverage_grid, random_search
from avval.campaign import Campaign
from avval.config import Release
from avval.estimation import find_estimation, release_verdict, run_estimation
from avval.policy import train_policy


@pytest.fixture
def estimated(store, policy):
    run_estimation(store, policy, n=150, seed=0)
    return store


def test_only_an_eligible_nominal_estimation_is_found(estimated, policy):
    store = estimated
    assert find_estimation(store, policy) == "estimate"
    # a sensitivity variant (overrides) and a plain search campaign are never evidence
    run_estimation(store, policy, 20, seed=1, name="variant", kind="sensitivity",
                   overrides={"sim": {"monitor": {"tor_ttc_s": 2.5}}})
    random_search(Campaign("random", store, policy, 20, method="random"))
    assert find_estimation(store, policy) == "estimate"


def test_tampered_estimation_data_is_not_evidence(estimated, policy):
    estimated.con.execute("UPDATE all_runs SET collision = NOT collision "
                          "WHERE campaign = 'estimate' AND run_idx = 3")
    assert find_estimation(estimated, policy) is None


def test_estimation_of_another_release_or_runtime_is_not_evidence(estimated, policy):
    retrained, _ = train_policy(n_samples=2_000, seed=1)
    assert find_estimation(estimated, retrained) is None
    with pytest.raises(LookupError, match="COMPLETE nominal estimation"):
        release_verdict(estimated, retrained)
    estimated.update_campaign("estimate", runtime_id="0" * 64)
    assert find_estimation(estimated, policy) is None


def test_verdict_is_identical_whichever_search_campaign_ran(estimated, policy):
    store = estimated
    random_search(Campaign("random", store, policy, 60, seed=1, method="random"))
    coverage_grid(Campaign("grid", store, policy, 230, seed=2, method="grid"))
    rel = Release.build(policy)
    a = release_verdict(store, release=rel)
    b = release_verdict(store, release=rel)
    assert a["verdict"] == b["verdict"] and a["estimation_campaign"] == "estimate"


def test_search_reports_contain_no_verdict(estimated, policy):
    camp = Campaign("random", estimated, policy, 40, method="random")
    random_search(camp)
    text = open(auto_report(camp, "random"), encoding="utf-8").read()
    assert not re.search(r"^#+ .*verdict", text, re.I | re.M)
    assert not re.search(r"\b(NO-GO|GO|INSUFFICIENT EVIDENCE)\b", text)
    assert "## Acceptance criteria" not in text and "## Discovery" in text


def test_agent_report_shows_the_verdict_of_the_same_release(estimated, policy):
    camp = Campaign("agent", estimated, policy, 5, method="agent")
    agent = ValidationAgent(camp, client=object())
    out = agent.call_tool("submit_report", {"summary": "s", "triggering_conditions": []})
    assert '"accepted": true' in out
    acc = release_verdict(estimated, policy)
    text = open(agent.report_path, encoding="utf-8").read()
    assert f"## Release verdict (from estimation campaign `estimate`): {acc['verdict']}" in text
