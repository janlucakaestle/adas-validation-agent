"""An LLM search agent that plans and runs a discovery campaign through tools.

The agent never touches the simulator or database directly: every action goes through the
search interface shared with all baselines (avval/search.py), which enforces the ODD, the
run budget, read-only access to an allowlist of its own campaign's columns, and the secret
boundary (avval/protected.py). Every claim it submits must pass the evidence protocol
(avval/evidence.py); an incomplete submission is rejected and the agent is told why.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import RESULTS_DIR
from .evidence import Ledger, bundle, run_evidence_query, validate_submission
from .frozen import canonical_json, sha256_text
from .search import RUN_FIELDS, SearchInterface

DEFAULT_MODEL = os.environ.get("AVVAL_MODEL", "claude-sonnet-5")
MAX_CASES_PER_CALL = 40
QUERY_ROWS = 50  # rows returned to the agent per query (the ledger keeps more)
# A full 40-case batch is ~4k tokens on its own; only tokens actually produced are billed.
MAX_OUTPUT_TOKENS = 16000
PROMPT_VERSION = "agent-prompt/v3"

# USD per million tokens (input, output), September 2026 list prices - check before relying on them.
PRICES = {"claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0),
          "claude-opus-5-5": (4.0, 20.0)}
CACHE_WRITE_MULT, CACHE_READ_MULT = 1.25, 0.10  # 5-minute cache: writes 1.25x, reads 0.1x input


def anthropic_version() -> str | None:
    """Installed version of the Anthropic client (also part of the runtime fingerprint)."""
    from importlib import metadata
    try:
        return metadata.version("anthropic")
    except metadata.PackageNotFoundError:
        return None


@dataclass
class Usage:
    """Accumulated token usage and an estimated cost for a run."""
    model: str
    input_tokens: int = 0          # uncached input
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    models_returned: set = field(default_factory=set)  # model IDs the API reported
    # One entry per API response: UTC time, returned model and its token counts. The time
    # span documents WHEN the seed ran (the alias `claude-sonnet-5` has no dated snapshot ID,
    # so time is the only handle on which model version served it); the per-call tokens let
    # cost be projected per turn.
    call_log: list = field(default_factory=list)

    def add(self, u, model: str | None = None) -> None:
        from datetime import datetime, timezone
        if model:
            self.models_returned.add(str(model))
        stamp = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "model": None if model is None else str(model)}
        if u is None:  # still time-stamped: the call happened
            self.call_log.append(stamp)
            return
        self.calls += 1
        tok = {"input": getattr(u, "input_tokens", 0) or 0,
               "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
               "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
               "output": getattr(u, "output_tokens", 0) or 0}
        self.input_tokens += tok["input"]
        self.cache_write_tokens += tok["cache_write"]
        self.cache_read_tokens += tok["cache_read"]
        self.output_tokens += tok["output"]
        self.call_log.append({**stamp, **tok})

    def cost(self, cached: bool = True) -> float | None:
        base = next((p for m, p in PRICES.items() if self.model.startswith(m)), None)
        if base is None:
            return None
        inp, out = base[0] / 1e6, base[1] / 1e6
        if not cached:  # what the same tokens would cost with caching off
            total_in = self.input_tokens + self.cache_write_tokens + self.cache_read_tokens
            return total_in * inp + self.output_tokens * out
        return (self.input_tokens * inp + self.cache_write_tokens * inp * CACHE_WRITE_MULT
                + self.cache_read_tokens * inp * CACHE_READ_MULT + self.output_tokens * out)

    def summary(self) -> dict:
        total_in = self.input_tokens + self.cache_write_tokens + self.cache_read_tokens
        c, u = self.cost(True), self.cost(False)
        return {"model": self.model, "models_returned": sorted(self.models_returned),
                "anthropic_version": anthropic_version(),
                "api_calls": self.calls, "input_tokens_total": total_in,
                "cache_read_tokens": self.cache_read_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "cache_hit_rate": round(self.cache_read_tokens / total_in, 3) if total_in else 0.0,
                "output_tokens": self.output_tokens,
                "est_cost_usd": None if c is None else round(c, 3),
                "est_cost_without_cache_usd": None if u is None else round(u, 3),
                "first_call_utc": self.call_log[0]["utc"] if self.call_log else None,
                "last_call_utc": self.call_log[-1]["utc"] if self.call_log else None,
                "calls": list(self.call_log)}


SYSTEM_PROMPT = """You are a validation engineer for an SAE Level 2 ADAS function: Adaptive
Cruise Control. The driver supervises at all times; when the system cannot cope it requests
the driver to intervene (a takeover request, TOR).
Your job is to FIND and EVIDENCE triggering conditions (SOTIF) within a fixed simulation
budget, not to measure how often the function fails in real traffic. Your runs are chosen by
you, so rates computed over them reflect your search, not real-world risk. You see only the
runs you choose.

Work like a careful engineer:
1. Read the system spec (ODD, discovery targets, column meanings, coverage, budget).
2. Spend part of the budget on broad coverage of the ODD.
3. Use SQL over the `runs` table to find where target runs cluster. Form explicit
   hypotheses, then spend budget testing them: probe boundaries, vary one factor at a time,
   and repeat cases where outcomes are stochastic (driver takeover time is random).
4. Check every candidate condition with test_predicate on your own runs, refine it and test
   again. Keep some budget for confirming conclusions, not just discovering them.
5. Submit your report. Each triggering condition must carry: a description; the predicate
   (a SQL WHERE clause over runs); the test_id of a test_predicate call on exactly that
   predicate; an evidence_sql that contains the predicate; and the query_id of a
   query_results call that ran exactly that evidence_sql and returned rows. Tests and
   queries must be run after your last simulation. Incomplete submissions are rejected with
   the list of what is missing; fix them and submit again. Never quote rates from your own
   runs as real-world rates. Distinguish what the data shows from what you infer.
Be concise in your reasoning between tool calls."""

TOOLS = [
    {"name": "get_system_spec",
     "description": "Returns the ODD parameters (meaning and range), driver-state definitions, "
                    "the discovery targets, the meaning of every column of `runs`, the "
                    "coverage definition and the remaining simulation budget.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_scenarios",
     "description": f"Simulate up to {MAX_CASES_PER_CALL} scenario cases. Each case needs "
                    "scenario, ego_speed, headway, friction, driver_state, plus exactly one "
                    "scenario-specific parameter: lead_decel (m/s^2) for lead_brake, or "
                    "closing_speed (m/s) for cut_in. Giving the other scenario's parameter is "
                    "an error. All values must be inside the ODD. Each case costs one run of "
                    "budget; repeat a case to sample another random driver takeover time. "
                    "Returns per-case key outcomes and the number of target runs per "
                    "discovery target in the batch.",
     "input_schema": {
         "type": "object",
         "properties": {"cases": {"type": "array", "maxItems": MAX_CASES_PER_CALL, "items": {
             "type": "object",
             "properties": {
                 "scenario": {"type": "string", "enum": ["lead_brake", "cut_in"]},
                 "ego_speed": {"type": "number"},
                 "headway": {"type": "number",
                             "description": "Initial time headway in s; range per scenario."},
                 "lead_decel": {"type": "number",
                                "description": "Lead deceleration, m/s^2. lead_brake only."},
                 "closing_speed": {"type": "number",
                                   "description": "Closing speed at cut-in, m/s. cut_in only."},
                 "friction": {"type": "number"}, "driver_state": {"type": "string"}},
             "required": ["scenario", "ego_speed", "headway", "friction", "driver_state"]}}},
         "required": ["cases"]}},
    {"name": "query_results",
     "description": f"Run one read-only DuckDB SQL SELECT over table `runs` (your campaign "
                    f"only; columns and meanings are in the system spec). Returns at most "
                    f"{QUERY_ROWS} rows plus a query_id; cite the query_id as evidence.",
     "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}},
                      "required": ["sql"]}},
    {"name": "check_coverage",
     "description": "Returns how many coverage cells have enough runs, the coverage "
                    "dimensions, and up to 20 uncovered cells with their parameter ranges.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "test_predicate",
     "description": "Check a candidate triggering condition against YOUR runs only. `where` is a "
                    "SQL WHERE clause over table `runs` (no WHERE keyword), in the form "
                    "\"<column> <op> <value> AND ...\". Returns runs inside and outside the "
                    "condition, the target rate inside and outside, the lift (inside rate / "
                    "outside rate), a 95% interval on the inside rate, and a test_id to cite. "
                    "Costs no simulation budget.",
     "input_schema": {
         "type": "object",
         "properties": {"where": {"type": "string"},
                        "target": {"type": "string",
                                   "description": "A discovery target from the system spec "
                                                  "(default: the spec's default_target)."}},
         "required": ["where"]}},
    {"name": "submit_report",
     "description": "Finish the campaign and submit your findings. Every triggering condition "
                    "must cite its predicate test and its evidence query; an incomplete "
                    "submission is rejected with the list of what is missing.",
     "input_schema": {
         "type": "object",
         "properties": {
             "summary": {"type": "string",
                         "description": "Markdown: key findings, limitations, recommended "
                                        "next tests."},
             "triggering_conditions": {"type": "array", "items": {
                 "type": "object",
                 "properties": {
                     "description": {"type": "string"},
                     "predicate": {"type": "string",
                                   "description": "The condition as a SQL WHERE clause, "
                                                  "exactly as passed to test_predicate."},
                     "predicate_test_id": {"type": "string",
                                           "description": "test_id returned by test_predicate "
                                                          "for this predicate."},
                     "evidence_sql": {"type": "string",
                                      "description": "SQL containing the predicate, exactly "
                                                     "as run with query_results."},
                     "evidence_query_id": {"type": "string",
                                           "description": "query_id returned by query_results "
                                                          "for evidence_sql."}},
                 "required": ["description", "predicate", "predicate_test_id",
                              "evidence_sql", "evidence_query_id"]}}},
         "required": ["summary", "triggering_conditions"]}},
]


def interface_id() -> str:
    """Content hash of everything that defines the agent's interface (for the benchmark
    manifest): prompt, tools, search-interface version and discovery objectives."""
    from .config import protocol_id
    from .search import INTERFACE_VERSION
    return sha256_text(canonical_json({"prompt": SYSTEM_PROMPT, "tools": TOOLS,
                                       "prompt_version": PROMPT_VERSION,
                                       "interface": INTERFACE_VERSION,
                                       "discovery": protocol_id("discovery")}))


@dataclass
class AgentResult:
    finished: bool
    turns: int
    report_path: str | None
    transcript: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    stop_reason: str = ""  # "submitted", "max_turns", "no_tool_calls" or "cost_cap"


class ValidationAgent:
    def __init__(self, campaign, client=None, model: str = DEFAULT_MODEL,
                 max_turns: int = 40, cache: bool = True, max_cost_usd: float | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.campaign, self.client, self.model, self.max_turns = campaign, client, model, max_turns
        self.iface = SearchInterface(campaign)
        self.ledger = Ledger(campaign.name)
        self.report_path: str | None = None
        self.bundle: dict | None = None
        self.rejections = 0
        self.cache = cache
        self.usage = Usage(model)
        self.max_cost_usd = max_cost_usd  # hard stop inside the loop, checked after each call
        self.transcript: list = []        # kept on the agent so a crashed run can still be saved

    def _request_kwargs(self, messages: list) -> dict:
        """Build the API request. With caching on, an explicit breakpoint on the system prompt
        caches tools + system, and top-level automatic caching moves a second breakpoint to
        the end of the growing conversation. Tool outputs are serialised deterministically."""
        kwargs = {"model": self.model, "max_tokens": MAX_OUTPUT_TOKENS, "tools": TOOLS,
                  "messages": messages}
        if self.cache:
            kwargs["system"] = [{"type": "text", "text": SYSTEM_PROMPT,
                                 "cache_control": {"type": "ephemeral"}}]
            kwargs["extra_body"] = {"cache_control": {"type": "ephemeral"}}
        else:
            kwargs["system"] = SYSTEM_PROMPT
        return kwargs

    def record_client_provenance(self) -> None:
        """Add the requested model, the model IDs the API actually returned and the client
        version to the campaign's provenance record (called before the campaign ends, so the
        record and any evidence bundle built from it carry them)."""
        store, name = self.campaign.store, self.campaign.name
        prov = dict(store.get_campaign(name)["provenance"])
        prov["agent_client"] = {"model_requested": self.model,
                                "models_returned": sorted(self.usage.models_returned),
                                "anthropic_version": anthropic_version(),
                                "api_calls": self.usage.calls,
                                "first_call_utc": (self.usage.call_log[0]["utc"]
                                                   if self.usage.call_log else None),
                                "last_call_utc": (self.usage.call_log[-1]["utc"]
                                                  if self.usage.call_log else None)}
        store.update_campaign(name, provenance=json.dumps(prov, sort_keys=True, default=str))

    # ---------------- tools ----------------
    def _spec(self, _):
        return self.iface.spec()

    def _run(self, args):
        from .config import validate_case
        cases = args.get("cases", [])[:MAX_CASES_PER_CALL]
        errors, valid = [], []
        for i, c in enumerate(cases):
            try:
                valid.append(validate_case(c, self.campaign.release.odd))
            except (ValueError, TypeError, AttributeError) as e:
                errors.append({"case": i, "error": str(e)})
        first = self.campaign.used
        rows = self.iface.run(valid)
        return {"runs": [{k: (round(r[k], 2) if isinstance(r[k], float) else r[k])
                          for k in RUN_FIELDS} for r in rows],
                "batch": {"executed": len(rows),
                          "target_runs": self.iface.target_counts(first) if rows else {}},
                "rejected": errors, "skipped_for_budget": len(valid) - len(rows),
                "budget_remaining": self.campaign.remaining}

    def _query(self, args):
        sql = args["sql"]
        rows, truncated = run_evidence_query(self.iface, sql)
        qid = self.ledger.record_query(sql, rows, truncated, self.campaign.used)
        return {"rows": rows[:QUERY_ROWS], "n_rows": len(rows),
                "rows_shown": min(len(rows), QUERY_ROWS), "query_id": qid}

    def _coverage(self, _):
        return self.iface.coverage()

    def _test_predicate(self, args):
        from .evaluation import default_target
        target = args.get("target") or default_target()
        result = self.iface.test_predicate(args["where"], target)
        tid = self.ledger.record_test(args["where"], target, result, self.campaign.used)
        return {**result, "test_id": tid, "runs_at_test": self.campaign.used}

    def _submit(self, args):
        accepted, problems = validate_submission(self.ledger, self.iface,
                                                 args.get("triggering_conditions", []))
        if problems:
            self.rejections += 1
            return {"accepted": False, "problems": problems,
                    "note": "Nothing was submitted. Fix every problem and call submit_report "
                            "again."}
        from .estimation import release_verdict
        from .report import write_search_report
        self.record_client_provenance()
        rec = self.campaign.finish(stop_reason="submitted")
        author = f"agent ({self.model})"
        self.bundle = bundle(self.ledger, rec, args["summary"], accepted, author)
        (RESULTS_DIR / f"evidence_{self.campaign.name}.json").write_text(
            json.dumps(self.bundle, indent=1, default=str), encoding="utf-8")
        # The release verdict is attached here, in code, after the agent has finished, and
        # only from an estimation of the same release and runtime.
        try:
            verdict = release_verdict(self.campaign.store, release=self.campaign.release)
        except (LookupError, ValueError):
            verdict = None
        self.report_path = str(write_search_report(
            self.campaign.store, self.campaign.name, summary=args["summary"], author=author,
            bundle=self.bundle, verdict=verdict, include_verdict=True))
        return {"accepted": True, "conditions_accepted": len(accepted)}

    def call_tool(self, name: str, args: dict) -> str:
        # sort_keys keeps serialisation byte-stable, which prompt caching depends on
        handlers = {"get_system_spec": self._spec, "run_scenarios": self._run,
                    "query_results": self._query, "check_coverage": self._coverage,
                    "test_predicate": self._test_predicate, "submit_report": self._submit}
        if name not in handlers:
            return json.dumps({"error": f"Unknown tool {name!r}. Available: {sorted(handlers)}"})
        if self.report_path and name != "get_system_spec":
            return json.dumps({"error": "The report was already submitted."})
        try:
            return json.dumps(handlers[name](args), default=str, sort_keys=True)
        except Exception as e:  # errors go back to the agent so it can correct itself
            msg = f"{type(e).__name__}: {e}"
            self.ledger.record_failure(name, args, msg)
            return json.dumps({"error": msg})

    # ---------------- loop ----------------
    def run(self, verbose: bool = True) -> AgentResult:
        messages = [{"role": "user", "content":
                     f"Validate the function. Campaign '{self.campaign.name}', simulation budget "
                     f"{self.campaign.budget} runs. Start by reading the system spec."}]
        transcript, nudged = self.transcript, False
        stop = "max_turns"
        for turn in range(1, self.max_turns + 1):
            resp = self.client.messages.create(**self._request_kwargs(messages))
            self.usage.add(getattr(resp, "usage", None), getattr(resp, "model", None))
            if getattr(resp, "stop_reason", None) == "max_tokens":
                # A cut-off tool call may carry partial input, so it is not executed.
                transcript.append({"turn": turn, "note": "response hit max_tokens; discarded"})
                kept = [b for b in resp.content if b.type == "text" and b.text.strip()]
                messages.append({"role": "assistant",
                                 "content": kept or [{"type": "text", "text": "(cut off)"}]})
                messages.append({"role": "user", "content":
                                 "Your last reply hit the output limit and was cut off, so no "
                                 "tool call from it was executed. Send shorter replies and "
                                 "smaller tool calls."})
                continue
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "text" and block.text.strip():
                    transcript.append({"turn": turn, "text": block.text})
                    if verbose:
                        print(f"\n[agent] {block.text.strip()}")
                elif block.type == "tool_use":
                    out = self.call_tool(block.name, block.input)
                    # The complete output is kept (no truncation); display is shortened only.
                    transcript.append({"turn": turn, "tool": block.name, "input": block.input,
                                       "output": out, "output_sha256": sha256_text(out)})
                    if verbose:
                        print(f"[tool] {block.name}({json.dumps(block.input)[:160]}) "
                              f"-> {out[:160]}")
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            if self.report_path:
                return AgentResult(True, turn, self.report_path, transcript, self.usage.summary(),
                                   "submitted")
            cost = self.usage.cost()
            if self.max_cost_usd is not None and cost is not None and cost >= self.max_cost_usd:
                stop = "cost_cap"
                transcript.append({"turn": turn, "note": f"stopped: cost ${cost:.2f} reached "
                                                         f"the cap ${self.max_cost_usd:.2f}"})
                break
            if results:
                messages.append({"role": "user", "content": results})
            elif not nudged:
                nudged = True
                messages.append({"role": "user", "content":
                                 "Continue the campaign, or call submit_report if you are done."})
            else:
                stop = "no_tool_calls"
                break
        self.record_client_provenance()
        self.campaign.finish(stop_reason=stop)  # no report: the search ended without one
        return AgentResult(False, turn, self.report_path, transcript, self.usage.summary(), stop)

