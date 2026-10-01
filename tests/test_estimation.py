"""Finding failures (search campaigns) is separate from measuring failure rates (estimation)."""
import json
import re
from collections import Counter

import numpy as np
import pytest

import avval.report as report_mod
from avval.agent import ValidationAgent
from avval.baselines import auto_report, coverage_grid, random_search
from avval.campaign import Campaign
from avval.config import load_exposure, load_odd, validate_case
from avval.estimation import (check_exposure, find_estimation, release_verdict, run_estimation,
                              sample_case)
from avval.policy import train_policy


def test_exposure_config_is_valid_and_sampled_as_specified():
    check_exposure(load_exposure(), load_odd())
    rng = np.random.default_rng(0)
    cases = [sample_case(rng) for _ in range(4000)]
    for c in cases:
        validate_case(c)  # every sample lies inside the ODD
    drivers = Counter(c["driver_state"] for c in cases)
    assert drivers["attentive"] / len(cases) == pytest.approx(
        load_exposure()["driver_state"]["attentive"], abs=0.02)


def test_invalid_exposure_is_rejected():
    bad = {**load_exposure(), "friction": {"bins": [0.2, 0.7, 1.0], "weights": [0.5, 0.5]}}
    with pytest.raises(ValueError, match="friction"):
        check_exposure(bad, load_odd())


@pytest.fixture
def estimated(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)
    run_estimation(store, policy, n=150, seed=0)
    return store


def _verdict_section(store, policy, name):
    """The release-verdict section of an agent report written for search campaign `name`."""
    agent = ValidationAgent(Campaign(name, store, policy, 1, fresh=False), client=object())
    agent.call_tool("submit_report", {"summary": "s", "triggering_conditions": []})
    text = open(agent.report_path, encoding="utf-8").read()
    return text[text.index("## Release verdict"):text.index("## Discovery")]


def test_verdict_is_identical_whichever_search_campaign_ran(estimated, policy):
    store = estimated
    random_search(Campaign("random", store, policy, 60, seed=1, method="random"))
    coverage_grid(Campaign("grid", store, policy, 120, seed=2, method="grid"))
    agent = Campaign("agent", store, policy, 30, seed=3, method="agent")
    agent.run([dict(scenario="cut_in", ego_speed=36.0, closing_speed=9.0, headway=0.3,
                    friction=0.5, driver_state="attentive")] * 30)  # a very different sample
    sections = [_verdict_section(store, policy, n) for n in ("random", "grid", "agent")]
    assert "estimation campaign `estimate`" in sections[0]
    assert sections[0] == sections[1] == sections[2]
    assert release_verdict(store, policy)["estimation_campaign"] == "estimate"


def test_search_reports_contain_no_verdict(estimated, policy):
    camp = Campaign("random", estimated, policy, 40, method="random")
    random_search(camp)
    text = open(auto_report(camp, "random"), encoding="utf-8").read()
    assert not re.search(r"^#+ .*verdict", text, re.I | re.M)  # no verdict section
    assert not re.search(r"\b(NO-GO|GO|INSUFFICIENT EVIDENCE)\b", text)
    assert "## Acceptance criteria" not in text
    assert "## Discovery" in text and "### Failing coverage cells" in text


def test_agent_report_shows_the_estimation_verdict(estimated, policy):
    camp = Campaign("agent", estimated, policy, 5, method="agent")
    agent = ValidationAgent(camp, client=object())
    acc = release_verdict(estimated, policy)
    agent.call_tool("submit_report", {"summary": "s", "triggering_conditions": []})
    text = open(agent.report_path, encoding="utf-8").read()
    assert (f"## Release verdict (from estimation campaign `estimate`): {acc['verdict']}"
            in text)


def test_estimation_must_match_current_provenance(estimated, policy):
    assert find_estimation(estimated, policy) == "estimate"
    retrained, _ = train_policy(n_samples=2_000, seed=1)
    assert find_estimation(estimated, retrained) is None  # new release: must re-estimate
    with pytest.raises(LookupError, match="estimate --n 2000"):
        release_verdict(estimated, retrained)
