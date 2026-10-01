"""Write a release-style validation report (Markdown) for a campaign."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from . import RESULTS_DIR
from .config import load_odd, scenario_param
from .evaluation import (INSUFFICIENT, cell_of, coverage, describe_cell, evaluate_acceptance,
                         failure_curve, failure_predicate, overall_verdict)
from .provenance import provenance


def _md_table(df: pd.DataFrame, max_rows: int = 15) -> str:
    if df.empty:
        return "_(no rows)_"
    df = df.head(max_rows).copy()
    for col in df.select_dtypes("float").columns:
        df[col] = df[col].round(2)
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, sep, *body])


def _fmt(x) -> str:
    return "-" if x is None or pd.isna(x) else f"{x:.3g}"


def _acceptance_lines(acc: list[dict]) -> list[str]:
    """Criteria table with value, 95% interval, n and status, plus a note per criterion."""
    table = pd.DataFrame([{
        "id": a["id"], "name": a["name"], "value": _fmt(a["value"]),
        "95% CI": "-" if a["ci_low"] is None else f"[{_fmt(a['ci_low'])}, {_fmt(a['ci_high'])}]",
        "target": "-" if a["op"] is None else f"{a['op']} {a['threshold']}",
        "n": a["n"], "min_n": a["min_n"], "status": a["status"]} for a in acc])
    notes = [f"- **{a['id']}:** {a['note']}" for a in acc if a["note"]]
    return [_md_table(table, max_rows=len(table)), "",
            "Rates use a 95% Clopper-Pearson interval, quantiles a 95% percentile bootstrap "
            "(fixed seed). A PASS needs the conservative end of the interval to meet the target.",
            "", *notes, *([""] if notes else [])]


def _provenance_lines(store, campaign: str) -> list[str]:
    """What was tested: the policy, config and code recorded when the campaign was created."""
    regs = store.campaign_info(campaign)
    lines = ["## Provenance", ""]
    if regs:
        reg = regs[-1]
        prov = reg["provenance"]
        lines += [f"Recorded when the campaign was created ({reg['created']:%Y-%m-%d %H:%M:%S}); "
                  f"method `{reg['method']}`, budget {reg['budget']}, seed {reg['seed']}.", ""]
        if len({json.dumps(r["provenance"], sort_keys=True) for r in regs}) > 1:
            lines += ["**Warning:** this campaign was reopened with a different policy, config or "
                      "code version, so its runs do not all come from the release shown here.", ""]
    else:
        prov = provenance()
        lines += ["_No campaign record found; showing the provenance at report time._", ""]
    pkgs = ", ".join(f"{k} {v}" for k, v in prov["packages"].items())
    lines += [f"- Policy (`results/policy.json`) SHA-256: `{prov['policy_sha256']}`",
              f"- Source code (`avval/*.py`) SHA-256: `{prov.get('code_sha256', 'not recorded')}`",
              f"- Git commit: `{prov['git_commit']}`",
              f"- Python {prov['python']}; {pkgs}",
              *[f"- Config `{name}` SHA-256: `{h}`" for name, h in prov["config_sha256"].items()],
              ""]
    return lines


def verdict_summary(acc: list[dict]) -> str:
    failed = [a["id"] for a in acc if a["status"] == "FAIL"]
    short = [f"{a['id']} (n={a['n']} < {a['min_n']})" if a["n"] else f"{a['id']} (no data)"
             for a in acc if a["status"] == INSUFFICIENT and a["n"] < a["min_n"]]
    unclear = [a["id"] for a in acc if a["status"] == INSUFFICIENT and a["n"] >= a["min_n"]]
    parts = ([f"criteria {', '.join(failed)} failed."] if failed else []) + (
        [f"insufficient evidence for {', '.join(short)}."] if short else []) + (
        [f"interval too wide to pass for {', '.join(unclear)}."] if unclear else [])
    return " ".join(parts) or "all criteria passed."


def _header(store, campaign: str, author: str, kind: str) -> list[str]:
    return [f"# {kind}: {load_odd()['function_under_test']}", "",
            f"**Campaign:** `{campaign}` · **Author:** {author} · **Date:** {date.today()}", "",
            *_provenance_lines(store, campaign)]


def _coverage_lines(store, campaign: str) -> list[str]:
    cov = coverage(store, campaign)
    return ["## Coverage", "", f"{cov['cells_covered']} / {cov['cells_total']} coverage cells "
            f"({cov['fraction']:.0%}) meet the minimum run count.", ""]


def _preventability_lines(store, campaign: str) -> list[str]:
    return [
        "## Preventability", "",
        "A collision is *unpreventable* if an ideal system braking at 0.9 μg from the moment "
        "the hazard appears also collides (`config/reference.yaml`). AC-01 and AC-03 "
        "count preventable runs only.", "",
        _md_table(store.query(
            "SELECT count(*) FILTER (WHERE collision) AS collisions, "
            "count(*) FILTER (WHERE collision AND preventable) AS preventable_collisions, "
            "count(*) FILTER (WHERE collision AND NOT preventable) AS unpreventable_collisions, "
            "count(*) FILTER (WHERE NOT preventable) AS unpreventable_runs FROM runs", campaign)),
        ""]


def failing_cells(store, campaign: str) -> pd.DataFrame:
    """Coverage cells with failing runs, most failures first: candidate triggering conditions."""
    df = store.query(f"SELECT *, ({failure_predicate()}) AS failed FROM runs", campaign,
                     max_rows=10**9)
    counts: dict[tuple, list[int]] = {}
    for rec in df.to_dict("records"):
        c = counts.setdefault(cell_of(rec), [0, 0, 0])
        c[0] += 1
        c[1] += bool(rec["failed"])
        c[2] += bool(rec["collision"] and rec["preventable"])
    rows = []
    for cell, (runs, fails, prev) in counts.items():
        if fails:
            d = describe_cell(cell)
            scen = d.pop("scenario")
            own = scenario_param(scen)
            lo, hi = d.pop(own)
            rows.append({"scenario": scen,
                         **{k: f"{a:g}-{b:g}" for k, (a, b) in d.items()},
                         "scenario_param": f"{own} {lo:g}-{hi:g}",
                         "runs": runs, "failing": fails, "preventable_collisions": prev})
    out = pd.DataFrame(rows)
    return out.sort_values(["failing", "runs"], ascending=[False, True]) if len(out) else out


def _discovery_lines(store, campaign: str) -> list[str]:
    curve = failure_curve(store, campaign)
    n = len(curve)
    first_fail = curve.loc[curve["failures"] > 0, "runs"].min() if n else None
    cells = failing_cells(store, campaign)
    return [
        "## Discovery", "",
        "Search campaigns choose where to look, so their failure *rates* say nothing about "
        "real-world risk and are not reported. What matters is what the search found and how "
        "fast.", "",
        f"- Runs executed: {n}",
        f"- Failing runs (`{failure_predicate()}`): {int(curve['failures'].iloc[-1]) if n else 0}",
        f"- Distinct failing coverage cells: {len(cells)}",
        f"- Runs to first failure: {first_fail if pd.notna(first_fail) else 'none found'}",
        "", "### Failing coverage cells", "", _md_table(cells), ""]


def _tc_lines(store, campaign: str, triggering_conditions: list[dict]) -> list[str]:
    lines = ["## Triggering conditions and evidence", ""]
    if not triggering_conditions:
        lines.append("_None reported._")
    for i, tc in enumerate(triggering_conditions, 1):
        lines += [f"### TC-{i:02d}: {tc['description']}", ""]
        if tc.get("predicate"):
            lines += [f"Predicate: `{tc['predicate'].strip()}`", ""]
        lines += ["```sql", tc["evidence_sql"].strip(), "```", ""]
        try:
            lines.append(_md_table(store.query(tc["evidence_sql"], campaign)))
        except Exception as e:
            lines.append(f"_Evidence query failed: {e}_")
        lines.append("")
    return lines


def _norm_sql(sql: str) -> str:
    return " ".join(sql.split()).lower()


def _predicate_test_lines(tests: list[dict], triggering_conditions: list[dict]) -> list[str]:
    """How the agent tested its candidate conditions (TASKS4:T38)."""
    if not tests:
        return ["## Hypothesis tests", "", "_No conditions were tested with `test_predicate`._",
                ""]
    rows = [{"#": i, "where": f"`{t['where']}`", "target": t["target"],
             "inside": t["runs_inside"], "outside": t["runs_outside"],
             "rate inside": _fmt(t["target_rate_inside"]),
             "rate outside": _fmt(t["target_rate_outside"]), "lift": _fmt(t["lift"])}
            for i, t in enumerate(tests, 1)]
    lines = ["## Hypothesis tests", "",
             "Every `test_predicate` call, in order, over the agent's own runs.", "",
             _md_table(pd.DataFrame(rows), max_rows=len(rows)), ""]
    for i, tc in enumerate(triggering_conditions, 1):
        pred = tc.get("predicate")
        if not pred:
            lines.append(f"- TC-{i:02d}: no predicate given.")
            continue
        hits = [j for j, t in enumerate(tests, 1) if _norm_sql(t["where"]) == _norm_sql(pred)]
        lines.append(f"- TC-{i:02d}: submitted predicate tested {len(hits)} time(s)"
                     + (f" (tests {', '.join(map(str, hits))})." if hits else "."))
    return lines + [""]


def _write(campaign: str, lines: list[str]) -> Path:
    path = RESULTS_DIR / f"report_{campaign}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_estimation_report(store, campaign: str,
                            author: str = "estimation (automatic)") -> Path:
    """Release verdict: acceptance criteria on an exposure-weighted estimation campaign."""
    acc = evaluate_acceptance(store, campaign)
    return _write(campaign, [
        *_header(store, campaign, author, "Validation report"),
        f"## Verdict: {overall_verdict(acc)}", "",
        f"Evaluated on the exposure-weighted estimation campaign `{campaign}` "
        f"({store.n_runs(campaign)} runs sampled from `config/exposure.yaml`, whose weights are "
        f"illustrative placeholders): {verdict_summary(acc)}", "",
        "## Acceptance criteria", "", *_acceptance_lines(acc),
        *_preventability_lines(store, campaign), *_coverage_lines(store, campaign)])


def write_search_report(store, campaign: str, summary: str, triggering_conditions: list[dict],
                        author: str, estimation: str | None = None,
                        include_verdict: bool = False,
                        predicate_tests: list[dict] | None = None) -> Path:
    """Search campaign report: discovery metrics and triggering conditions, no verdict of its own.

    With `include_verdict` (used by the agent), the release verdict of the matching estimation
    campaign is shown, attributed to it, so findings and verdict appear together.
    """
    lines = [*_header(store, campaign, author, "Search report"), "## Summary", "",
             summary.strip(), ""]
    if include_verdict:
        if estimation is None:
            lines += ["## Release verdict", "",
                      "_No estimation campaign matches this release's provenance, so no verdict "
                      "is available. Run `python -m avval.cli estimate`._", ""]
        else:
            acc = evaluate_acceptance(store, estimation)
            lines += [f"## Release verdict (from estimation campaign `{estimation}`): "
                      f"{overall_verdict(acc)}", "",
                      f"Not computed from this search campaign: {verdict_summary(acc)} "
                      f"See `report_{estimation}.md` for the full report.", "",
                      *_acceptance_lines(acc)]
    lines += [*_discovery_lines(store, campaign), *_preventability_lines(store, campaign),
              *_coverage_lines(store, campaign),
              *_tc_lines(store, campaign, triggering_conditions)]
    if predicate_tests is not None:
        lines += _predicate_test_lines(predicate_tests, triggering_conditions)
    return _write(campaign, lines)
