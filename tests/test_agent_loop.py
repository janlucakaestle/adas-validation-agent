"""The agent loop, tested offline with a scripted stand-in for the LLM API."""
import json
from types import SimpleNamespace as NS

from avval.agent import ValidationAgent
from avval.campaign import Campaign
import avval.report as report_mod


def _tool(name, args, i):
    return NS(type="tool_use", name=name, input=args, id=f"tu_{i}")


class ScriptedClient:
    """Replays a fixed sequence of assistant turns, recording what the agent sends back."""

    def __init__(self, turns):
        self.turns, self.received = list(turns), []
        self.messages = self

    def create(self, **kwargs):
        self.received.append(kwargs["messages"][-1])
        return NS(content=self.turns.pop(0), stop_reason="tool_use")


def test_agent_runs_tools_and_writes_report(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)
    case = dict(scenario="lead_brake", ego_speed=30, headway=0.8, lead_decel=8, friction=1.0,
                driver_state="attentive")
    turns = [
        [NS(type="text", text="Reading spec."), _tool("get_system_spec", {}, 1)],
        [_tool("run_scenarios", {"cases": [case] * 5 + [{**case, "friction": 0.1}]}, 2)],
        [_tool("query_results", {"sql": "SELECT avg(CAST(collision AS INT)) p FROM runs"}, 3)],
        [_tool("query_results", {"sql": "DROP TABLE all_runs"}, 4)],
        [_tool("evaluate_acceptance", {}, 5)],
        [_tool("submit_report", {"summary": "Found a failure.",
                                 "triggering_conditions": [{
                                     "description": "Harsh braking at short gap",
                                     "evidence_sql": "SELECT count(*) n FROM runs WHERE collision"}]},
               6)],
    ]
    client = ScriptedClient(turns)
    agent = ValidationAgent(Campaign("agent_test", store, policy, budget=20), client=client)
    result = agent.run(verbose=False)

    assert result.finished and result.turns == 6
    assert store.n_runs("agent_test") == 5            # out-of-ODD case rejected, not run
    run_reply = client.received[2]["content"][0]["content"]
    assert "outside ODD" in run_reply                  # agent is told why
    drop_reply = client.received[4]["content"][0]["content"]
    assert "error" in drop_reply                       # destructive SQL refused
    acc_reply = client.received[5]["content"][0]["content"]
    assert "Unknown tool" in acc_reply                 # the acceptance tool is gone
    text = open(result.report_path, encoding="utf-8").read()
    assert "No estimation campaign matches" in text and "TC-01" in text


def test_requests_enable_prompt_caching(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)  # keep test reports out of results/
    turns = [[_tool("get_system_spec", {}, 1)],
             [_tool("submit_report", {"summary": "s", "triggering_conditions": []}, 2)]]

    class Recording(ScriptedClient):
        def create(self, **kwargs):
            self.kwargs = kwargs
            resp = super().create(**kwargs)
            resp.usage = NS(input_tokens=100, cache_creation_input_tokens=2000,
                            cache_read_input_tokens=8000, output_tokens=500)
            return resp

    client = Recording(turns)
    agent = ValidationAgent(Campaign("cache_test", store, policy, 5), client=client,
                            model="claude-sonnet-5")
    result = agent.run(verbose=False)
    assert client.kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert client.kwargs["extra_body"] == {"cache_control": {"type": "ephemeral"}}
    u = result.usage
    assert u["api_calls"] == 2 and u["cache_read_tokens"] == 16_000
    assert u["est_cost_usd"] < u["est_cost_without_cache_usd"]

    off = ValidationAgent(Campaign("nocache", store, policy, 5), client=Recording(
        [[_tool("submit_report", {"summary": "s", "triggering_conditions": []}, 1)]]),
        cache=False)
    off.run(verbose=False)
    assert "extra_body" not in off.client.kwargs and isinstance(off.client.kwargs["system"], str)


def test_usage_cost_arithmetic():
    from avval.agent import Usage
    u = Usage("claude-sonnet-5", input_tokens=1_000_000, cache_write_tokens=1_000_000,
              cache_read_tokens=1_000_000, output_tokens=100_000)
    # 2.00 + 2.50 + 0.20 + 1.00
    assert abs(u.cost() - 5.70) < 1e-9
    assert abs(u.cost(cached=False) - 7.00) < 1e-9


def test_system_spec_defines_driver_states(store, policy):
    agent = ValidationAgent(Campaign("spec", store, policy, 5), client=object())
    import json
    spec = json.loads(agent.call_tool("get_system_spec", {}))
    ds = spec["driver_states"]
    assert set(ds) == {"attentive", "distracted"}
    assert ds["distracted"]["category"] == "foreseeable_misuse"
    assert ds["attentive"]["category"] == "intended_use"
    assert all(v["definition"] for v in ds.values())


# ---- What the agent knows ---------------------------------------------------------------
BANNED = ["training", "trained", "fault", "ground truth", "weak", "behaviour-cloned",
          "behavior-cloned", "intelligent driver model", "idm", "out-of-distribution",
          "estimation", "evaluate_acceptance", "threshold", "takeover_mean", "floor_s",
          "min_n"]
# Column meanings for the agent's own runs are allowed (e.g. `preventable` in query_results);
# the preventability reference config itself is not in the spec (checked by the key-set test).


def _agent_text(store, policy):
    from avval.agent import SYSTEM_PROMPT, TOOLS
    agent = ValidationAgent(Campaign("know", store, policy, 5), client=object())
    spec = agent.call_tool("get_system_spec", {})
    tools = json.dumps(TOOLS)
    return SYSTEM_PROMPT, tools, spec


def test_acceptance_tool_is_gone(store, policy):
    from avval.agent import TOOLS
    assert "evaluate_acceptance" not in {t["name"] for t in TOOLS}
    agent = ValidationAgent(Campaign("gone", store, policy, 5), client=object())
    assert "Unknown tool" in agent.call_tool("evaluate_acceptance", {})


def test_prompt_tools_and_spec_contain_no_hints(store, policy):
    import re
    for name, text in zip(("prompt", "tools", "spec"), _agent_text(store, policy)):
        hits = [w for w in BANNED if re.search(rf"\b{re.escape(w)}", text, re.I)]
        assert not hits, f"{name} mentions {hits}"


def test_spec_holds_meanings_ranges_target_and_budget_only(store, policy):
    spec = json.loads(_agent_text(store, policy)[2])
    assert set(spec) == {"odd", "driver_states", "failure_predicate", "note", "budget_total",
                         "budget_remaining"}


def test_agent_sql_sees_only_its_own_runs(store, policy):
    other = Campaign("other", store, policy, 10)
    other.run([dict(scenario="cut_in", ego_speed=30.0, closing_speed=5.0, headway=20.0 / 30.0,
                    friction=1.0, driver_state="attentive")] * 10)
    agent = ValidationAgent(Campaign("mine", store, policy, 5), client=object())
    assert json.loads(agent.call_tool("query_results", {"sql": "SELECT count(*) AS n FROM runs"})
                      )["rows"] == [{"n": 0}]
    for sql in ("SELECT * FROM all_runs", "SELECT * FROM campaigns"):
        assert "error" in json.loads(agent.call_tool("query_results", {"sql": sql}))


def test_cost_cap_stops_the_loop(store, policy):
    """--max-cost-usd: the loop stops after the call that reaches the cap."""
    class Costly(ScriptedClient):
        def create(self, **kwargs):
            resp = super().create(**kwargs)
            resp.usage = NS(input_tokens=1_000_000, cache_creation_input_tokens=0,
                            cache_read_input_tokens=0, output_tokens=0)  # $2 per call on Sonnet 5
            return resp

    turns = [[_tool("get_system_spec", {}, i)] for i in range(5)]
    agent = ValidationAgent(Campaign("cap", store, policy, 5), client=Costly(turns),
                            model="claude-sonnet-5", max_cost_usd=3.0)
    result = agent.run(verbose=False)
    assert not result.finished and result.stop_reason == "cost_cap"
    assert result.usage["api_calls"] == 2 and agent.transcript[-1]["note"].startswith("stopped")


def test_cli_agent_runs_the_chosen_seed_and_saves_usage(store, policy, tmp_path, monkeypatch):
    """`agent --first-seed 2` runs campaign <name>_s2 and writes its usage and transcript."""
    import avval.agent as agent_mod
    import avval.cli as cli
    import avval.store as store_mod
    runs = []

    class FakeAgent:
        def __init__(self, camp, **kw):
            self.camp, self.kw, self.transcript = camp, kw, [{"turn": 1, "text": "hi"}]
            self.usage = agent_mod.Usage(kw["model"])

        def run(self):
            runs.append((self.camp.name, self.kw["max_cost_usd"]))
            return agent_mod.AgentResult(False, 1, None, self.transcript,
                                         self.usage.summary(), "max_turns")

    monkeypatch.setattr(agent_mod, "ValidationAgent", FakeAgent)
    monkeypatch.setattr(store_mod, "Store", lambda: store)
    monkeypatch.setattr(cli, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(cli, "_print_benchmark", lambda *a: None)
    cli.main(["agent", "--name", "clitest", "--first-seed", "2", "--max-cost-usd", "4",
              "--model", "claude-haiku-4-5"])
    assert runs == [("clitest_s2", 4.0)]
    assert store.con.execute("SELECT seed FROM campaigns WHERE name = 'clitest_s2'").fetchone()[0] == 2
    assert json.loads((tmp_path / "usage_clitest_s2.json").read_text())["model"] == "claude-haiku-4-5"
    assert (tmp_path / "transcript_clitest_s2.json").exists()


def test_truncated_reply_is_not_executed(store, policy):
    """A reply cut off at max_tokens may hold a partial tool call: skip it, tell the agent."""
    case = dict(scenario="lead_brake", ego_speed=30, headway=0.8, lead_decel=8, friction=1.0,
                driver_state="attentive")

    class Truncating(ScriptedClient):
        def create(self, **kwargs):
            resp = super().create(**kwargs)
            if len(self.received) == 1:
                resp.stop_reason = "max_tokens"
            return resp

    turns = [[_tool("run_scenarios", {"cases": [case] * 3}, 1)],
             [_tool("submit_report", {"summary": "s", "triggering_conditions": []}, 2)]]
    client = Truncating(turns)
    agent = ValidationAgent(Campaign("trunc_test", store, policy, 10), client=client)
    result = agent.run(verbose=False)
    assert result.finished and result.turns == 2
    assert store.n_runs("trunc_test") == 0             # the cut-off batch never ran
    assert "cut off" in client.received[1]["content"]
