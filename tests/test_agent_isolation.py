"""Secret boundary: nothing protected reaches the agent, directly or through generated text.

The protected set is derived from the release configuration itself
(avval/protected.py::protected_items), so a new threshold, reference parameter or driver
number added to a config file is covered without editing this test. The payload is every
string the agent can receive: system prompt, tool schemas, the first user message, the
system spec, and the keys and messages of every tool result, including validation errors,
SQL errors and submission rejections.
"""
import json
import re

import pytest

import avval.agent as agent_mod
from avval.agent import ValidationAgent
from avval.campaign import Campaign
from avval.config import Release, load_discovery
from avval.protected import AGENT_COLUMNS, PROTECTED_TERMS, protected_items, public_numbers

CASE = dict(scenario="cut_in", ego_speed=30.0, closing_speed=8.0, headway=0.4, friction=1.0,
            driver_state="attentive")
_NUM = re.compile(r"(?<![\w.^])-?\d+(?:\.\d+)?(?:[eE]-?\d+)?(?![\w])")
_ENUM = re.compile(r"(?m)^\s*\d+\.\s")  # "5. Submit ..." list markers are not values


def _keys_and_messages(obj, out):
    """Keys and message strings of a tool result (data values are not 'text' the system
    authored, so they are excluded)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            if k in ("error", "note", "problems") or k.endswith("error"):
                out.append(json.dumps(v))
            _keys_and_messages(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _keys_and_messages(v, out)
    return out


def payload(store, policy, budget=30) -> str:
    """Probes use neutral inputs: the agent's own text echoed back in an error message is
    not a leak (hidden columns and unknown tools are tested separately)."""
    agent = ValidationAgent(Campaign("iso", store, policy, budget), client=object())
    parts = [agent_mod.SYSTEM_PROMPT, json.dumps(agent_mod.TOOLS),
             f"Validate the function. Campaign 'iso', simulation budget {budget} runs. "
             "Start by reading the system spec."]
    calls = [("get_system_spec", {}),
             ("run_scenarios", {"cases": [CASE, {**CASE, "friction": 0.45},
                                          {**CASE, "lead_decel": 3.0}, {"scenario": "x"},
                                          {**CASE, "headway": float("nan")}]}),
             ("query_results", {"sql": "SELECT * FROM runs"}),
             ("query_results", {"sql": "SELECT nonexistent_col FROM runs"}),
             ("query_results", {"sql": "DELETE FROM runs"}),
             ("check_coverage", {}),
             ("test_predicate", {"where": "headway < 0.5"}),
             ("test_predicate", {"where": "headway < 0.5", "target": "near_miss"}),
             ("test_predicate", {"where": "no_such_col > 1"}),
             ("test_predicate", {"where": "x", "target": "secret_target"}),
             ("submit_report", {"summary": "s", "triggering_conditions": [
                 {"description": "", "predicate": "", "evidence_sql": "SELECT 1"}]}),
             ("some_other_tool", {})]
    for name, args in calls:
        out = json.loads(agent.call_tool(name, args))
        parts.append(json.dumps(out) if name == "get_system_spec" else
                     " ".join(_keys_and_messages(out, [])))
    return "\n".join(parts)


@pytest.fixture
def text(store, policy):
    return payload(store, policy)


def _term_hits(text):
    return [t for t in PROTECTED_TERMS
            if re.search(rf"(?<![A-Za-z]){re.escape(t)}", text,
                         0 if t in ("IDM", "MLP", "AC-0", "Green") else re.I)]


def _string_hits(text, release):
    visible = set(AGENT_COLUMNS)
    public_preds = {t["predicate"] for t in load_discovery()["targets"].values()}
    norm = " ".join(text.split()).lower()
    hits = []
    for item in protected_items(release):
        if not isinstance(item.value, str):
            continue
        v = " ".join(item.value.split()).lower()
        if v in visible or v in public_preds or v.replace("not ", "") in visible:
            continue
        if v in norm:
            hits.append(item.label)
    return hits


def _number_hits(text, release, budget=30):
    public = public_numbers(release, budget)
    secret = {item.value: item.label for item in protected_items(release)
              if isinstance(item.value, float) and item.value not in public}
    found = {float(x) for x in _NUM.findall(_ENUM.sub(" ", text))}
    return {secret[v]: v for v in found if v in secret}


def test_no_protected_term_reaches_the_agent(text):
    assert not _term_hits(text)


def test_no_protected_formula_or_identifier_reaches_the_agent(text, policy):
    assert not _string_hits(text, Release.build(policy))


def test_no_protected_number_reaches_the_agent(text, policy):
    """Every protected number that is not also a legitimately public number (ODD ranges,
    coverage bins, discovery objectives, tool limits, budget) is absent. Protected values
    equal to public ones cannot be hidden; the term check above ensures they are never
    labelled as the protected quantity."""
    assert not _number_hits(text, Release.build(policy))


def test_known_leaks_are_closed(text):
    assert "1.5" not in _NUM.findall(text)          # the AC-02 boundary in the old predicate
    assert not re.search(r"0\.9\s*\*?\s*(mu|μ)", text)  # the reference level in the SQL help
    assert "min_ttc_below" not in text


def test_discovery_objectives_do_not_encode_acceptance_values(policy):
    release = Release.build(policy)
    secret = {item.value for item in protected_items(release)
              if item.category == "acceptance" and isinstance(item.value, float)}
    for t in load_discovery()["targets"].values():
        assert not {float(x) for x in _NUM.findall(t["predicate"])} & secret


def test_hidden_columns_are_not_queryable(store, policy):
    agent = ValidationAgent(Campaign("cols", store, policy, 5), client=object())
    for col in ("handback_required", "max_required_decel", "tor_reason", "seed",
                "max_jerk_automated", "ccd_avoidable_by_reference", "hazard_onset_s"):
        out = json.loads(agent.call_tool("query_results", {"sql": f"SELECT {col} FROM runs"}))
        assert "error" in out, col


# ---- the checker itself catches leaks ------------------------------------------------------
@pytest.mark.parametrize("leak", [
    " Failures are runs with min_ttc < 1.5.",                 # AC-02 threshold
    " The reference brakes at 0.9*mu*g.",                     # reference parameter
    " Attentive drivers react in 1.3 s on average.",          # driver-model number
    " The monitor hands back above 3.0 m/s^2 required deceleration.",
    " Release passes if AC-01 holds.",
    " The policy was behaviour-cloned from IDM.",
])
def test_checker_detects_injected_leaks(store, policy, monkeypatch, leak):
    monkeypatch.setattr(agent_mod, "SYSTEM_PROMPT", agent_mod.SYSTEM_PROMPT + leak)
    t = payload(store, policy)
    rel = Release.build(policy)
    assert _term_hits(t) or _string_hits(t, rel) or _number_hits(t, rel)


def test_checker_detects_a_leak_through_a_generated_tool_description(store, policy, monkeypatch):
    rel = Release.build(policy)
    thr = next(c["threshold"] for c in rel.acceptance["criteria"] if c["id"] == "AC-04")
    tools = json.loads(json.dumps(agent_mod.TOOLS))
    tools[1]["description"] += f" Jerk above {thr} m/s^3 counts."
    monkeypatch.setattr(agent_mod, "TOOLS", tools)
    assert _number_hits(payload(store, policy), rel)
