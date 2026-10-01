"""An LLM validation agent that plans, runs and reports a validation campaign through tools.

The agent never touches the simulator directly: every action goes through a narrow tool
interface (spec, run, SQL, coverage, acceptance, report) that enforces the ODD, the run
budget and read-only data access. That constraint is what makes its output auditable.
"""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field

from .campaign import Campaign
from .config import load_odd
from .estimation import find_estimation
from .evaluation import TARGETS, coverage, describe_cell, failure_predicate, predicate_stats
from .report import write_search_report

DEFAULT_MODEL = os.environ.get("AVVAL_MODEL", "claude-sonnet-5")
MAX_CASES_PER_CALL = 40
# A full 40-case batch is ~4k tokens on its own; only tokens actually produced are billed.
MAX_OUTPUT_TOKENS = 16000

# USD per million tokens (input, output), September 2026 list prices - check before relying on them.
PRICES = {"claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0),
          "claude-opus-5-5": (4.0, 20.0)}
CACHE_WRITE_MULT, CACHE_READ_MULT = 1.25, 0.10  # 5-minute cache: writes 1.25x, reads 0.1x input


@dataclass
class Usage:
    """Accumulated token usage and an estimated cost for a run."""
    model: str
    input_tokens: int = 0          # uncached input
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, u) -> None:
        if u is None:
            return
        self.calls += 1
        self.input_tokens += getattr(u, "input_tokens", 0) or 0
        self.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        self.output_tokens += getattr(u, "output_tokens", 0) or 0

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
        return {"model": self.model, "api_calls": self.calls, "input_tokens_total": total_in,
                "cache_read_tokens": self.cache_read_tokens,
                "cache_write_tokens": self.cache_write_tokens,
                "cache_hit_rate": round(self.cache_read_tokens / total_in, 3) if total_in else 0.0,
                "output_tokens": self.output_tokens,
                "est_cost_usd": None if c is None else round(c, 3),
                "est_cost_without_cache_usd": None if u is None else round(u, 3)}

SYSTEM_PROMPT = """You are a validation engineer for an SAE Level 2 ADAS function: Adaptive
Cruise Control driven by a learned policy. The driver supervises at all times; when the system
cannot cope it requests the driver to intervene (a takeover request, TOR).
Your job is to FIND and EVIDENCE triggering conditions (SOTIF) within a fixed simulation
budget, not to estimate failure rates. Your runs are chosen by you, so rates computed over
them reflect your search, not real-world risk. You see only the runs you choose; failure
rates and the release verdict are computed separately, after you submit, and are not
available to you.

Work like a careful engineer:
1. Read the system spec (ODD, failure predicate, coverage definition, budget).
2. Spend part of the budget on broad coverage of the ODD so every coverage cell has data.
3. Use SQL over the `runs` table to find where failures cluster. Form explicit hypotheses
   about triggering conditions (SOTIF), then spend budget testing them: probe boundaries,
   vary one factor at a time, and repeat seeds where outcomes are stochastic (driver
   takeover time is random).
4. Before you claim a triggering condition, check it with test_predicate on your own runs:
   it reports how strongly the condition concentrates failures (inside vs outside rate,
   lift, interval). Refine the condition and test again. Keep some budget for confirming
   your conclusions, not just discovering them.
5. Submit your report. You do not choose a verdict; the release verdict is added to your
   report by code, from a separate campaign. Never quote failure rates from your own runs as
   if they were real-world rates. Every triggering condition you claim must cite a SQL query
   over your runs that shows the evidence. Distinguish clearly between what the data shows
   and what you infer.
Be concise in your reasoning between tool calls."""

TOOLS = [
    {"name": "get_system_spec",
     "description": "Returns the ODD parameters (meaning and range), driver-state "
                    "definitions, the failure predicate, the coverage definition and the "
                    "remaining simulation budget.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_scenarios",
     "description": f"Simulate up to {MAX_CASES_PER_CALL} scenario cases. Each case needs scenario, "
                    "ego_speed, gap, friction, driver_state, plus exactly one scenario-specific "
                    "parameter: lead_decel (m/s^2) for lead_brake, or closing_speed (m/s) for "
                    "cut_in. Giving the other scenario's parameter is an error. All values must be "
                    "inside the ODD. Each case costs one run of budget; repeat a case to sample "
                    "another random driver takeover time. Returns per-case key metrics and a "
                    "batch summary.",
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
     "description": "Run one read-only DuckDB SQL SELECT over table `runs` (this campaign only). "
                    "Columns: run_idx, scenario, ego_speed, headway (s), initial_gap_m "
                    "(headway * ego_speed), lead_decel (NULL for cut_in), "
                    "closing_speed (NULL for lead_brake), friction, driver_state (attentive | "
                    "distracted), driver_category (intended_use | foreseeable_misuse), "
                    "collision, impact_speed, min_ttc (s, before impact; NULL = never closing), "
                    "min_ttc_accel (s, TTC with current accelerations; NULL = never closing), "
                    "min_thw (s, after the first 2 s), min_gap (m; NULL = collision), max_decel, max_jerk (m/s^3, "
                    "0.5 s moving-average acceleration), max_jerk_raw (20 Hz differences), "
                    "tor_issued, tor_time, takeover_time, duration, preventable (FALSE if an "
                    "ideal system braking at 0.9*mu*g from hazard onset also collides, i.e. the "
                    "collision is physics, not the function), ccd_preventable (NULL unless "
                    "enabled). Returns at most 50 rows.",
     "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}},
                      "required": ["sql"]}},
    {"name": "check_coverage",
     "description": "Returns how many coverage cells have enough runs, and up to 20 uncovered cells "
                    "with their parameter ranges.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "test_predicate",
     "description": "Check a candidate triggering condition against YOUR runs only. `where` is a "
                    "SQL WHERE clause over table `runs` (no WHERE keyword), in the form "
                    "\"<column> <op> <value> AND ...\". Returns runs inside and outside the "
                    "condition, the target rate inside and outside, the lift (inside rate / outside rate) and a "
                    "95% interval on the inside rate. Costs no simulation budget.",
     "input_schema": {
         "type": "object",
         "properties": {"where": {"type": "string"},
                        "target": {"type": "string", "enum": list(TARGETS),
                                   "description": "What to count: 'failure' is the failure "
                                                  "predicate from the system spec."}},
         "required": ["where"]}},
    {"name": "submit_report",
     "description": "Finish the campaign and write the report of your findings. Call exactly "
                    "once, at the end.",
     "input_schema": {
         "type": "object",
         "properties": {
             "summary": {"type": "string",
                         "description": "Markdown: key findings, limitations, recommended "
                                        "next tests."},
             "triggering_conditions": {"type": "array", "items": {
                 "type": "object",
                 "properties": {"description": {"type": "string"},
                                "evidence_sql": {"type": "string"},
                                "predicate": {"type": "string",
                                              "description": "The condition as a SQL WHERE "
                                                             "clause, as passed to "
                                                             "test_predicate."}},
                 "required": ["description", "evidence_sql"]}}},
         "required": ["summary", "triggering_conditions"]}},
]


@dataclass
class AgentResult:
    finished: bool
    turns: int
    report_path: str | None
    transcript: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    stop_reason: str = ""          # "submitted", "max_turns", "no_tool_calls" or "cost_cap"


class ValidationAgent:
    def __init__(self, campaign: Campaign, client=None, model: str = DEFAULT_MODEL,
                 max_turns: int = 40, cache: bool = True, max_cost_usd: float | None = None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.campaign, self.client, self.model, self.max_turns = campaign, client, model, max_turns
        self.report_path: str | None = None
        self.predicate_tests: list[dict] = []  # every test_predicate call, in order
        self.cache = cache
        self.usage = Usage(model)
        self.max_cost_usd = max_cost_usd  # hard stop inside the loop, checked after each call
        self.transcript: list = []        # kept on the agent so a crashed run can still be saved

    def _request_kwargs(self, messages: list) -> dict:
        """Build the API request. With caching on:
        - an explicit breakpoint on the system prompt caches tools + system (they precede it),
        - top-level automatic caching moves a second breakpoint to the end of the growing
          conversation, so each turn re-reads the previous turns from cache.
        Everything before the breakpoint must be byte-identical between calls, which is why
        tool outputs are serialised deterministically and nothing time-varying is in the prompt.
        """
        kwargs = {"model": self.model, "max_tokens": MAX_OUTPUT_TOKENS, "tools": TOOLS, "messages": messages}
        if self.cache:
            kwargs["system"] = [{"type": "text", "text": SYSTEM_PROMPT,
                                 "cache_control": {"type": "ephemeral"}}]
            # extra_body works across SDK versions, including ones without a typed parameter
            kwargs["extra_body"] = {"cache_control": {"type": "ephemeral"}}
        else:
            kwargs["system"] = SYSTEM_PROMPT
        return kwargs

    # ---------------- tools ----------------
    def _spec(self, _):
        """What the agent may know (README "What the agent knows", decision C13): what each
        parameter means and its range, the failure predicate it searches for, the coverage
        definition and its budget. No acceptance thresholds, driver-model numbers,
        preventability reference, training details or results from other campaigns."""
        odd = copy.deepcopy(load_odd())
        states = odd["parameters"]["driver_state"].pop("states")  # returned once, below
        return {"odd": odd, "driver_states": states, "failure_predicate": failure_predicate(),
                "note": "takeover_time is measured from the takeover request to the driver's "
                        "first input.",
                "budget_total": self.campaign.budget, "budget_remaining": self.campaign.remaining}

    def _run(self, args):
        cases = args.get("cases", [])[:MAX_CASES_PER_CALL]
        errors, valid = [], []
        for i, c in enumerate(cases):
            try:
                from .config import validate_case
                valid.append(validate_case(c))
            except ValueError as e:
                errors.append({"case": i, "error": str(e)})
        rows = self.campaign.run(valid)
        keys = ("run_idx", "scenario", "ego_speed", "headway", "lead_decel", "closing_speed",
                "friction", "driver_state", "collision", "min_ttc", "tor_issued", "takeover_time")
        return {"runs": [{k: (round(r[k], 2) if isinstance(r[k], float) else r[k]) for k in keys}
                         for r in rows],
                "batch": {"executed": len(rows), "collisions": sum(r["collision"] for r in rows),
                          "min_ttc_below_1.5": sum(r["min_ttc"] is not None and r["min_ttc"] < 1.5
                                                for r in rows)},
                "rejected": errors, "skipped_for_budget": len(valid) - len(rows),
                "budget_remaining": self.campaign.remaining}

    def _query(self, args):
        df = self.campaign.store.query(args["sql"], self.campaign.name)
        return {"rows": json.loads(df.to_json(orient="records")), "n_rows": len(df)}

    def _coverage(self, _):
        cov = coverage(self.campaign.store, self.campaign.name)
        return {"cells_total": cov["cells_total"], "cells_covered": cov["cells_covered"],
                "uncovered_examples": [describe_cell(c) for c in cov["uncovered"][:20]]}

    def _test_predicate(self, args):
        result = predicate_stats(self.campaign.store, self.campaign.name, args["where"],
                                 args.get("target", "failure"))
        self.predicate_tests.append(result)
        return result

    def _submit(self, args):
        # The release verdict is attached here, in code, after the agent has finished: the
        # agent never sees the estimation campaign (TASKS4:T37).
        self.report_path = str(write_search_report(
            self.campaign.store, self.campaign.name, summary=args["summary"],
            triggering_conditions=args["triggering_conditions"],
            author=f"agent ({self.model})",
            estimation=find_estimation(self.campaign.store, self.campaign.policy),
            include_verdict=True, predicate_tests=self.predicate_tests))
        return {"report_path": self.report_path}

    def call_tool(self, name: str, args: dict) -> str:
        # sort_keys keeps serialisation byte-stable, which prompt caching depends on
        handlers = {"get_system_spec": self._spec, "run_scenarios": self._run,
                    "query_results": self._query, "check_coverage": self._coverage,
                    "test_predicate": self._test_predicate, "submit_report": self._submit}
        if name not in handlers:
            return json.dumps({"error": f"Unknown tool {name!r}. Available: {sorted(handlers)}"})
        try:
            return json.dumps(handlers[name](args), default=str, sort_keys=True)
        except Exception as e:  # errors go back to the agent so it can correct itself
            return json.dumps({"error": f"{type(e).__name__}: {e}"})

    # ---------------- loop ----------------
    def run(self, verbose: bool = True) -> AgentResult:
        messages = [{"role": "user", "content":
                     f"Validate the function. Campaign '{self.campaign.name}', simulation budget "
                     f"{self.campaign.budget} runs. Start by reading the system spec."}]
        transcript, nudged = self.transcript, False
        stop = "max_turns"
        for turn in range(1, self.max_turns + 1):
            resp = self.client.messages.create(**self._request_kwargs(messages))
            self.usage.add(getattr(resp, "usage", None))
            if getattr(resp, "stop_reason", None) == "max_tokens":
                # A cut-off tool call may carry partial input (e.g. half a batch), so it is not
                # executed; the agent is told why and asked to send smaller calls.
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
                    transcript.append({"turn": turn, "tool": block.name, "input": block.input,
                                       "output": out[:2000]})
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
        return AgentResult(False, turn, self.report_path, transcript, self.usage.summary(), stop)
