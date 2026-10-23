"""The search interface shared by every discovery strategy: the LLM agent and all baselines.

Every strategy obtains its information through this class: the public system spec (ODD,
driver-state definitions, coverage definition, discovery objectives, column meanings), the
per-run columns in `AGENT_COLUMNS` for the runs it chose, coverage of its own campaign,
predicate statistics on its own runs, and its budget. Nothing else: no acceptance criteria,
verdicts, reference or driver-model parameters, design values or other campaigns.

What differs between strategies is the FORM, not the content: the LLM reads `spec()` as JSON
with natural-language descriptions; numerical baselines read `domain()`, the same content in
programmatic form (values, ranges, bins), and optimise a scalar robustness score of three
visible columns. The LLM can therefore reason semantically about visible derived labels such
as `avoidable_by_reference`, which is also part of the primary benchmark region; the
baselines do not use that label. A benchmark therefore compares complete search strategies,
including semantic reasoning, not optimisation efficiency on one identical objective.
"""
from __future__ import annotations

from .config import load_discovery
from .evaluation import coverage, describe_cell, predicate_stats, target_predicate
from .frozen import thaw
from .protected import AGENT_COLUMNS, COLUMN_DESCRIPTIONS

# Fields returned per run by run_scenarios (a subset of AGENT_COLUMNS).
RUN_FIELDS = ("run_idx", "scenario", "ego_speed", "headway", "lead_decel", "closing_speed",
              "friction", "driver_state", "collision", "end_state", "min_ttc", "tor_issued",
              "takeover_time")
INTERFACE_VERSION = "search-interface/v3"


class SearchInterface:
    def __init__(self, campaign):
        self.campaign = campaign

    # what may be known
    def spec(self) -> dict:
        odd = thaw(self.campaign.release.odd)
        states = odd["parameters"]["driver_state"].pop("states")
        disc = load_discovery()
        return {"odd": odd, "driver_states": states,
                "discovery_targets": {k: {"predicate": v["predicate"],
                                          "description": v["description"]}
                                      for k, v in disc["targets"].items()},
                "default_target": disc["default_target"],
                "columns": {c: COLUMN_DESCRIPTIONS[c] for c in AGENT_COLUMNS},
                "note": "takeover_time is measured from the takeover request to the driver's "
                        "first input.",
                "budget_total": self.campaign.budget,
                "budget_remaining": self.campaign.remaining}

    def domain(self) -> dict:
        """The public search domain in programmatic form, derived ONLY from `spec()`, i.e.
        exactly the information the agent receives (minus its natural-language text):
        categorical values, per-scenario parameter ranges, coverage bins, visible columns,
        discovery targets and budget. Numerical baselines use nothing else."""
        spec = self.spec()
        params = spec["odd"]["parameters"]
        scenarios = list(params["scenario"]["values"])
        own = {params[k]["scenario"]: k for k in params if "scenario" in params[k]
               and k != "scenario"}
        ranges = {}
        for scen in scenarios:
            keys = ["ego_speed", "headway", own[scen], "friction"]
            ranges[scen] = {k: list(params[k]["ranges"][scen] if "ranges" in params[k]
                                    else params[k]["range"]) for k in keys}
        return {"scenarios": scenarios, "driver_states": list(params["driver_state"]["values"]),
                "ranges": ranges, "odd": spec["odd"], "columns": list(spec["columns"]),
                "targets": spec["discovery_targets"], "budget": spec["budget_total"]}

    # what may be done
    def run(self, cases: list[dict]) -> list[dict]:
        """Run cases; returns only the visible fields of each stored run."""
        rows = self.campaign.run(cases)
        return [{k: r[k] for k in AGENT_COLUMNS} for r in rows]

    def query(self, sql: str, max_rows: int):
        return self.campaign.store.query(sql, self.campaign.name, max_rows=max_rows,
                                         columns=AGENT_COLUMNS)

    def coverage(self) -> dict:
        cov = coverage(self.campaign.store, self.campaign.name, self.campaign.release.odd)
        return {"cells_total": cov["cells_total"], "cells_covered": cov["cells_covered"],
                "dimensions": cov["dimensions"],
                "uncovered_examples": [describe_cell(c, self.campaign.release.odd)
                                       for c in cov["uncovered"][:20]]}

    def test_predicate(self, where: str, target: str | None = None) -> dict:
        return predicate_stats(self.campaign.store, self.campaign.name, where, target,
                               columns=AGENT_COLUMNS)

    def target_counts(self, first_idx: int) -> dict:
        """Discovery-target hits among runs with run_idx >= first_idx (the latest batch)."""
        targets = load_discovery()["targets"]
        sel = ", ".join(f"count(*) FILTER (WHERE {target_predicate(t)}) AS \"{t}\""
                        for t in targets)
        row = self.query(f"SELECT {sel} FROM runs WHERE run_idx >= {int(first_idx)}", 1)
        return {t: int(row.iloc[0][t]) for t in targets}

    @property
    def budget(self) -> int:
        return self.campaign.budget

    @property
    def remaining(self) -> int:
        return self.campaign.remaining
