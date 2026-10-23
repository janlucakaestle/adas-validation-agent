"""The agent loop, tested offline with a scripted stand-in for the LLM API."""
import json
from types import SimpleNamespace as NS

from avval.agent import ValidationAgent
from avval.campaign import Campaign

CASE = dict(scenario="lead_brake", ego_speed=30, headway=0.8, lead_decel=8, friction=1.0,
            driver_state="attentive")


def _tool(name, args, i):
    return NS(type="tool_use", name=name, input=args, id=f"tu_{i}")


class ScriptedClient:
    """Replays assistant turns; a turn may be a callable of the replies so far, so a script
    can cite IDs returned by earlier tool calls."""

    def __init__(self, turns):
        self.turns, self.received = list(turns), []
        self.messages = self

    def create(self, **kwargs):
        self.received.append(kwargs["messages"][-1])
        turn = self.turns.pop(0)
        return NS(content=turn(self) if callable(turn) else turn, stop_reason="tool_use")

    def reply(self, i):
        return json.loads(self.received[i]["content"][0]["content"])


def test_agent_runs_tools_and_writes_an_evidence_backed_report(store, policy, tmp_path):
    pred = "scenario = 'lead_brake' AND headway < 1.0"
    sql = f"SELECT count(*) AS n FROM runs WHERE {pred} AND collision"
    turns = [
        [NS(type="text", text="Reading spec."), _tool("get_system_spec", {}, 1)],
        [_tool("run_scenarios", {"cases": [CASE] * 5 + [{**CASE, "friction": 0.1}]}, 2)],
        [_tool("query_results", {"sql": "DROP TABLE all_runs"}, 3)],
        [_tool("evaluate_acceptance", {}, 4)],
        [_tool("test_predicate", {"where": pred}, 5)],
        [_tool("query_results", {"sql": sql}, 6)],
        lambda c: [_tool("submit_report", {"summary": "Found a failure.", "triggering_conditions": [{
            "description": "Harsh braking at short headway", "predicate": pred,
            "predicate_test_id": c.reply(5)["test_id"], "evidence_sql": sql,
            "evidence_query_id": c.reply(6)["query_id"]}]}, 7)],
    ]
    client = ScriptedClient(turns)
    agent = ValidationAgent(Campaign("agent_test", store, policy, budget=20), client=client)
    result = agent.run(verbose=False)

    assert result.finished and result.turns == 7 and result.stop_reason == "submitted"
    assert store.n_runs("agent_test") == 5            # out-of-ODD case rejected, not run
    assert "outside ODD" in client.received[2]["content"][0]["content"]
    assert "error" in client.reply(3)                  # destructive SQL refused
    assert "Unknown tool" in client.received[4]["content"][0]["content"]
    text = open(result.report_path, encoding="utf-8").read()
    assert "TC-01" in text and "Evidence bundle SHA-256" in text
    assert store.get_campaign("agent_test")["status"] == "COMPLETE"
    bundle = json.loads((tmp_path / "evidence_agent_test.json").read_text())
    assert bundle["conditions"][0]["predicate"] == pred


def test_transcripts_keep_complete_outputs(store, policy):
    turns = [[_tool("run_scenarios", {"cases": [CASE] * 40}, 1)],
             [_tool("submit_report", {"summary": "s", "triggering_conditions": []}, 2)]]
    agent = ValidationAgent(Campaign("t", store, policy, 40), client=ScriptedClient(turns))
    agent.run(verbose=False)
    entry = agent.transcript[0]
    assert len(entry["output"]) > 2000                 # no arbitrary 2,000-character cut
    from avval.frozen import sha256_text
    assert entry["output_sha256"] == sha256_text(entry["output"])


def test_requests_enable_prompt_caching(store, policy):
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
    assert abs(u.cost() - 5.70) < 1e-9          # 2.00 + 2.50 + 0.20 + 1.00
    assert abs(u.cost(cached=False) - 7.00) < 1e-9


def test_system_spec_defines_driver_states_targets_and_columns(store, policy):
    agent = ValidationAgent(Campaign("spec", store, policy, 5), client=object())
    spec = json.loads(agent.call_tool("get_system_spec", {}))
    ds = spec["driver_states"]
    assert set(ds) == {"attentive", "distracted"}
    assert ds["distracted"]["category"] == "foreseeable_misuse"
    assert set(spec["discovery_targets"]) == {"collision", "near_miss"}
    assert "avoidable_by_reference" in spec["columns"]
    assert "handback_required" not in spec["columns"]


def test_cost_cap_stops_the_loop(store, policy):
    class Costly(ScriptedClient):
        def create(self, **kwargs):
            resp = super().create(**kwargs)
            resp.usage = NS(input_tokens=1_000_000, cache_creation_input_tokens=0,
                            cache_read_input_tokens=0, output_tokens=0)  # $2 per call
            return resp

    turns = [[_tool("get_system_spec", {}, i)] for i in range(5)]
    agent = ValidationAgent(Campaign("cap", store, policy, 5), client=Costly(turns),
                            model="claude-sonnet-5", max_cost_usd=3.0)
    result = agent.run(verbose=False)
    assert not result.finished and result.stop_reason == "cost_cap"
    assert result.usage["api_calls"] == 2 and agent.transcript[-1]["note"].startswith("stopped")
    rec = store.get_campaign("cap")
    assert rec["status"] == "COMPLETE" and rec["stop_reason"] == "cost_cap"


def test_truncated_reply_is_not_executed(store, policy):
    class Truncating(ScriptedClient):
        def create(self, **kwargs):
            resp = super().create(**kwargs)
            if len(self.received) == 1:
                resp.stop_reason = "max_tokens"
            return resp

    turns = [[_tool("run_scenarios", {"cases": [CASE] * 3}, 1)],
             [_tool("submit_report", {"summary": "s", "triggering_conditions": []}, 2)]]
    client = Truncating(turns)
    agent = ValidationAgent(Campaign("trunc_test", store, policy, 10), client=client)
    result = agent.run(verbose=False)
    assert result.finished and result.turns == 2
    assert store.n_runs("trunc_test") == 0
    assert "cut off" in client.received[1]["content"]


def test_cli_agent_runs_the_chosen_seed_and_saves_usage(store, policy, tmp_path, monkeypatch):
    """`agent --no-protocol --first-seed 2` runs campaign <name>_s2 and saves usage/transcript."""
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
            self.camp.finish("max_turns")
            return agent_mod.AgentResult(False, 1, None, self.transcript,
                                         self.usage.summary(), "max_turns")

    monkeypatch.setattr(agent_mod, "ValidationAgent", FakeAgent)
    real = store_mod.Store
    monkeypatch.setattr(store_mod, "Store", lambda *a, **k: real(*a, **k) if a or k else store)
    monkeypatch.setattr("avval.policy.LearnedACC.load", classmethod(lambda cls: policy))
    cli.main(["agent", "--no-protocol", "--name", "clitest", "--first-seed", "2",
              "--max-cost-usd", "4", "--model", "claude-haiku-4-5"])
    assert runs == [("clitest_s2", 4.0)]
    assert store.get_campaign("clitest_s2")["seed"] == 2
    assert json.loads((tmp_path / "usage_clitest_s2.json").read_text())["model"] == "claude-haiku-4-5"
    assert (tmp_path / "transcript_clitest_s2.json").exists()


def test_cli_agent_refuses_without_a_frozen_protocol(store, policy, monkeypatch):
    import pytest

    import avval.cli as cli
    import avval.store as store_mod
    real = store_mod.Store
    monkeypatch.setattr(store_mod, "Store", lambda *a, **k: real(*a, **k) if a or k else store)
    monkeypatch.setattr("avval.policy.LearnedACC.load", classmethod(lambda cls: policy))
    with pytest.raises(FileNotFoundError):
        cli.main(["agent", "--first-seed", "0"])


def test_usage_records_the_model_id_returned_by_the_api(store, policy):
    class Returning(ScriptedClient):
        def create(self, **kwargs):
            resp = super().create(**kwargs)
            resp.model = "claude-sonnet-5-20260901"
            return resp

    agent = ValidationAgent(Campaign("ret", store, policy, 5), client=Returning(
        [[_tool("submit_report", {"summary": "s", "triggering_conditions": []}, 1)]]),
        model="claude-sonnet-5")
    result = agent.run(verbose=False)
    assert result.usage["model"] == "claude-sonnet-5"
    assert result.usage["models_returned"] == ["claude-sonnet-5-20260901"]
    # ... and the campaign's own provenance carries it, with the client version
    from importlib import metadata
    client = store.get_campaign("ret")["provenance"]["agent_client"]
    assert client["model_requested"] == "claude-sonnet-5"
    assert client["models_returned"] == ["claude-sonnet-5-20260901"]
    assert client["anthropic_version"] == metadata.version("anthropic")
    assert result.usage["anthropic_version"] == metadata.version("anthropic")
    # every API call is time-stamped and its tokens logged
    assert result.usage["first_call_utc"] and result.usage["last_call_utc"]
    assert len(result.usage["calls"]) == 1  # one API response (the scripted one has no usage)
    assert client["first_call_utc"] == result.usage["first_call_utc"]
    rt = store.get_campaign("ret")["provenance"]["runtime"]["packages"]
    assert rt["anthropic"] == metadata.version("anthropic")
