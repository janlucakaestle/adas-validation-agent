"""Post-hoc check of the agent's submitted triggering conditions on held-out data.

The agent tests its predicates only on its own few hundred runs. Here every predicate it
submitted (read from `results/report_<campaign>.md`) is re-evaluated on the exposure-weighted
estimation campaign, which the agent never saw, and compared with a reference condition: the
box around the AC-01 collisions found in the 100k-run estimation (see `docs/progress.md`).
"""
from __future__ import annotations

import json
import re

from . import RESULTS_DIR
from .benchmark import REGIONS
from .evaluation import failure_predicate, predicate_stats

REFERENCE = "scenario = 'cut_in' AND headway <= 0.73 AND closing_speed >= 6.1"
AC01_EVENT = REGIONS["attentive_preventable_collision"]
_TC = re.compile(r"^### (TC-\d+).*?^Predicate: `([^`]+)`", re.M | re.S)


def submitted_predicates(campaign: str) -> list[tuple[str, str]]:
    """(condition id, predicate) pairs from a search report, in report order."""
    text = (RESULTS_DIR / f"report_{campaign}.md").read_text(encoding="utf-8")
    return [(tc, pred.strip()) for tc, pred in _TC.findall(text)]


def _counts(store, campaign: str, where: str) -> dict:
    p, r = f"coalesce(({where}), false)", f"coalesce(({REFERENCE}), false)"
    fail, ev = failure_predicate(), AC01_EVENT
    row = store.query(
        f"SELECT count(*) FILTER (WHERE {p} AND {r}) AS both_runs, "
        f"count(*) FILTER (WHERE {p} AND NOT {r}) AS only_pred, "
        f"count(*) FILTER (WHERE {r} AND NOT {p}) AS only_ref, "
        f"count(*) FILTER (WHERE {r} AND ({fail})) AS ref_failures, "
        f"count(*) FILTER (WHERE {p} AND {r} AND ({fail})) AS both_failures, "
        f"count(*) FILTER (WHERE ({fail})) AS all_failures, "
        f"count(*) FILTER (WHERE {p} AND ({fail})) AS pred_failures, "
        f"count(*) FILTER (WHERE ({ev})) AS all_ac01, "
        f"count(*) FILTER (WHERE {p} AND ({ev})) AS pred_ac01 FROM runs", campaign).iloc[0]
    return {k: int(v) for k, v in row.items()}


def _relation(c: dict) -> str:
    if c["both_runs"] == 0:
        return "disjoint (a different failure mode)"
    if c["only_pred"] == 0 and c["only_ref"] == 0:
        return "same runs"
    if c["only_pred"] == 0:
        return "tighter (inside the reference)"
    if c["only_ref"] == 0:
        return "looser (contains the reference)"
    return "overlapping (neither contains the other)"


def evaluate(store, campaigns: list[str], holdout: str = "estimate") -> list[dict]:
    items = [("reference", "-", REFERENCE)]
    items += [(c, tc, pred) for c in campaigns for tc, pred in submitted_predicates(c)]
    rows = []
    for source, tc, pred in items:
        s = predicate_stats(store, holdout, pred)
        c = _counts(store, holdout, pred)
        n_pred = c["both_runs"] + c["only_pred"]
        n_ref = c["both_runs"] + c["only_ref"]
        rows.append({
            "source": source, "condition": tc, "predicate": pred, **s,
            "share_of_failures_inside": c["pred_failures"] / c["all_failures"]
            if c["all_failures"] else None,
            "ac01_events_inside": c["pred_ac01"], "ac01_events_total": c["all_ac01"],
            "overlap_runs": c["both_runs"],
            "share_inside_reference": c["both_runs"] / n_pred if n_pred else None,
            "share_of_reference_covered": c["both_runs"] / n_ref if n_ref else None,
            "share_of_reference_failures_covered":
                c["both_failures"] / c["ref_failures"] if c["ref_failures"] else None,
            "relation_to_reference": "-" if source == "reference" else _relation(c)})
    return rows


def _pct(x, digits=1) -> str:
    return "-" if x is None else f"{100 * x:.{digits}f}%"


def write_posthoc(store, campaigns: list[str], holdout: str = "estimate") -> str:
    rows = evaluate(store, campaigns, holdout)
    n = store.n_runs(holdout)
    lines = [
        "# Post-hoc check of the agent's triggering conditions", "",
        f"Every predicate the agent submitted, re-evaluated on the held-out estimation campaign "
        f"`{holdout}` ({n:,} exposure-weighted runs the agent never saw). Target: the failure "
        f"predicate `{failure_predicate()}`. The interval is a 95% Clopper-Pearson interval on "
        f"the failure rate inside the predicate. The reference is the box around the AC-01 "
        f"collisions of the estimation: `{REFERENCE}`. AC-01 events: `{AC01_EVENT}`.", "",
        "| source | TC | predicate | runs inside | failure rate inside [95% CI] "
        "| failure rate outside | lift | share of all failures inside "
        "| AC-01 events inside |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lo, hi = r["inside_rate_ci95"]
        ci = "-" if lo is None else f"{_pct(r['target_rate_inside'])} [{_pct(lo)}, {_pct(hi)}]"
        lift = "-" if r["lift"] is None else f"{r['lift']:.1f}"
        lines.append(
            f"| {r['source']} | {r['condition']} | `{r['predicate']}` | {r['runs_inside']:,} "
            f"| {ci} | {_pct(r['target_rate_outside'], 2)} | {lift} "
            f"| {_pct(r['share_of_failures_inside'])} "
            f"| {r['ac01_events_inside']} / {r['ac01_events_total']} |")
    lines += ["", "## Comparison with the reference", "",
              "Overlap counts runs in both. Precision is the failure rate inside (above).", "",
              "| source | TC | overlap runs | share of predicate inside reference "
              "| share of reference covered | share of reference failures covered "
              "| boundary vs reference |", "|---|---|---|---|---|---|---|"]
    for r in rows[1:]:
        lines.append(
            f"| {r['source']} | {r['condition']} | {r['overlap_runs']:,} "
            f"| {_pct(r['share_inside_reference'])} | {_pct(r['share_of_reference_covered'])} "
            f"| {_pct(r['share_of_reference_failures_covered'])} "
            f"| {r['relation_to_reference']} |")
    (RESULTS_DIR / "posthoc_predicates.json").write_text(
        json.dumps(rows, indent=1, default=str), encoding="utf-8")
    path = RESULTS_DIR / "posthoc_predicates.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)
