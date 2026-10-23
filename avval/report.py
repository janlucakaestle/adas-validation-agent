"""Release-style validation reports (Markdown), rendered from stored records and evidence.

Every report states its scope: all quantitative conclusions are conditional on the
simulator, ODD, exposure model, driver model, controller and release manifest named in its
provenance section. Statistical terms are precise (one-sided bounds are called one-sided).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from . import RESULTS_DIR
from .config import Release, load_odd, scenario_param
from .evaluation import (INSUFFICIENT, cell_of, coverage, default_target, describe_cell,
                         evaluate_acceptance, failure_curve, target_predicate)

SCOPE = ("**Scope.** Every number below is conditional on this release's simulator, ODD, "
         "exposure model, driver model, controller and configuration (release ID above). "
         "Exposure weights, acceptance thresholds and several driver parameters are "
         "placeholders (`TODO(data)` in `config/`), so the numbers show the method, not "
         "real-world risk.")


def _md_table(df: pd.DataFrame, max_rows: int = 15) -> str:
    if df.empty:
        return "_(no rows)_"
    df = df.head(max_rows).copy()
    for col in df.select_dtypes("float").columns:
        df[col] = df[col].round(3)
    header = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep = "| " + " | ".join("---" for _ in df.columns) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join([header, sep, *body])


def _fmt(x) -> str:
    return "-" if x is None or (isinstance(x, float) and pd.isna(x)) else f"{x:.4g}"


def _bound(a: dict) -> str:
    if a["op"] is None:
        return f"[{_fmt(a['lower'])}, {_fmt(a['upper'])}]"
    side = "upper" if a["op"] == "<=" else "lower"
    return f"{_fmt(a[side])} ({side})"


def _target(a: dict) -> str:
    if a["threshold"] is None:
        return "none defined"
    t = f"{a['op']} {a['threshold']:g}" + (" (zero goal)" if a["zero_goal"] else "")
    return t + "".join(f"; {k} = {v:g}" for k, v in a.get("params", {}).items())


def decision_lines(decision: dict) -> list[str]:
    """The engineering verdict, requirement maturity and the formal decision, separately."""
    pending = decision["unapproved_requirements"]
    return [f"- **Engineering verdict** (evidence against the configured targets): "
            f"**{decision['engineering_verdict']}**",
            "- **Requirement maturity:** " + (
                "every gating requirement is approved." if not pending else
                f"not approved: {', '.join(pending)}. A provisional, illustrative or undefined "
                "requirement can never authorise release (a violation still counts as NO-GO)."),
            f"- **Formal release decision:** **{decision['formal_decision']}**"
            + ("" if decision["evidence_mode"] == "final" else
               " (only a `--final` campaign from a clean, committed tree can carry one)"), ""]


def acceptance_lines(acc: list[dict]) -> list[str]:
    gating = [a for a in acc if a["op"] is not None]
    info = [a for a in acc if a["op"] is None]
    conf = acc[0]["confidence"] if acc else 0.95
    table = pd.DataFrame([{
        "id": a["id"], "name": a["name"], "value": _fmt(a["value"]),
        f"one-sided {conf:.0%} bound": _bound(a), "n": a["n"],
        "n needed": "-" if a["n_needed"] is None else str(a["n_needed"]),
        "min_n": a["min_n"], "target": _target(a), "vs target": a["status"],
        "requirement": a["effective_requirement_status"],
        "supports formal GO": "yes" if a["supports_formal_go"] else "no"} for a in gating])
    lines = [_md_table(table, max_rows=len(table)), "",
             f"Statistical result: exact one-sided Clopper-Pearson bounds for rates and exact "
             f"distribution-free order-statistic bounds for quantiles, at {conf:.0%} one-sided "
             f"confidence. Engineering comparison ('vs target'): PASS needs the bound to meet "
             f"the target (in every stratum where strata are listed); FAIL means the point "
             f"estimate violates it (or a zero goal is falsified); NO REQUIREMENT means no "
             f"target exists. 'requirement' is the effective maturity (the weakest of the "
             f"criterion's own status and the definitions its population uses); only "
             f"'approved' can support a formal GO. 'n needed' is the smallest sample at which "
             f"a PASS is possible at all.", ""]
    for a in gating:
        notes = [x for x in (a["note"], a["robustness"]) if x]
        if notes:
            lines.append(f"- **{a['id']}:** " + " ".join(notes))
        if a["strata"]:
            st = pd.DataFrame([{"stratum": ", ".join(f"{k}={v}" for k, v in r["stratum"].items()),
                                "n": r["n"], "value": _fmt(r["value"]),
                                "lower": _fmt(r["lower"]), "upper": _fmt(r["upper"]),
                                "status": r["status"]} for r in a["strata"]])
            lines += ["", f"  {a['id']} by stratum:", "", _md_table(st, max_rows=len(st)), ""]
    if info:
        lines += ["", "**Descriptive measures (INFO, never gating).** Rows marked "
                  "*conditional* select runs by the system's own outputs and must not be read "
                  "as safety evidence.", ""]
        lines.append(_md_table(pd.DataFrame([{
            "id": a["id"], "name": a["name"], "value": _fmt(a["value"]),
            f"one-sided {conf:.0%} bounds [lower, upper]": _bound(a), "n": a["n"],
            "conditional on outputs": "yes" if a["conditional"] else "no"} for a in info]),
            max_rows=len(info)))
    return lines + [""]


def provenance_lines(store, campaign: str) -> list[str]:
    rec = store.get_campaign(campaign)
    lines = ["## Provenance", ""]
    if rec is None:
        return lines + ["_No campaign record found._", ""]
    prov = rec["provenance"]
    pkgs = ", ".join(f"{k} {v}" for k, v in prov["runtime"]["packages"].items())
    lines += [f"- Campaign `{campaign}`: kind `{rec['kind']}`, method `{rec['method']}`, status "
              f"**{rec['status']}**, {rec['completed_runs']} of {rec['planned_runs']} planned "
              f"runs, seed {rec['seed']}, created {rec['created']:%Y-%m-%d %H:%M:%S}"
              + (f", resumed {rec['resumed']} time(s)" if rec["resumed"] else ""),
              f"- Release ID: `{rec['release_id']}`"
              + ("" if prov["nominal"] else " (**variant**: overrides "
                 f"`{json.dumps(rec['overrides'], sort_keys=True)}`)"),
              f"- Runtime ID: `{rec['runtime_id']}`; exposure model ID: "
              f"`{rec['exposure_model_id']}`"
              + (f"; protocol ID: `{rec['protocol_id']}`" if rec["protocol_id"] else ""),
              f"- Data SHA-256: `{rec['data_sha256'] or 'not recorded (campaign not complete)'}`",
              f"- Policy SHA-256: `{prov['policy_sha256']}`; source code SHA-256: "
              f"`{prov['code_sha256']}`; git commit `{prov['git_commit']}` (traceability only)",
              f"- Python {prov['runtime']['python']} on {prov['runtime']['system']} "
              f"{prov['runtime']['machine']}; {pkgs}",
              "- Lock file: " + ("matches" if not prov["lock_mismatches"] else
                                 "**mismatch**: " + "; ".join(prov["lock_mismatches"])),
              *[f"- Parsed config `{n}` SHA-256: `{h}`"
                for n, h in prov["config_sha256"].items()], ""]
    return lines


def verdict_summary(acc: list[dict]) -> str:
    acc = [a for a in acc if a["op"] is not None]
    failed = [a["id"] for a in acc if a["status"] == "FAIL"]
    short = [f"{a['id']} (n={a['n']} < {a['min_n']})" if a["n"] else f"{a['id']} (no data)"
             for a in acc if a["status"] == INSUFFICIENT and a["n"] < (a["min_n"] or 0)]
    unclear = [a["id"] for a in acc if a["status"] == INSUFFICIENT
               and a["n"] >= (a["min_n"] or 0)]
    parts = ([f"criteria {', '.join(failed)} failed."] if failed else []) + (
        [f"insufficient evidence for {', '.join(short)}."] if short else []) + (
        [f"not demonstrated for {', '.join(unclear)}."] if unclear else [])
    nreq = [a["id"] for a in acc if a["status"] == "NO REQUIREMENT"]
    parts += [f"no requirement defined for {', '.join(nreq)}."] if nreq else []
    return " ".join(parts) or "every gating criterion passed."


def _header(store, campaign: str, author: str, kind: str) -> list[str]:
    return [f"# {kind}: {load_odd()['function_under_test']}", "",
            f"**Campaign:** `{campaign}` · **Author:** {author} · **Date:** {date.today()}", "",
            *provenance_lines(store, campaign), SCOPE, ""]


def coverage_lines(store, campaign: str) -> list[str]:
    cov = coverage(store, campaign)
    dims = ", ".join(cov["dimensions"])
    scope = ("over the full set of ODD coverage dimensions" if cov["complete_odd"] else
             "EXCLUDING dimensions " + ", ".join(f"{k} ({v})" for k, v in
                                                 cov["excluded_dimensions"].items()))
    return ["## Coverage", "",
            f"{cov['cells_covered']} / {cov['cells_total']} coverage cells "
            f"({cov['fraction']:.0%}) meet the minimum run count, {scope}: {dims}. Coverage "
            "is structural: it says nothing about how often the function fails in a cell.", ""]


def reference_lines(store, campaign: str) -> list[str]:
    return [
        "## Reference outcomes", "",
        "`avoidable_by_reference`: a fixed brake-only response, starting at hazard onset with "
        "perfect knowledge, no steering and no pre-hazard braking (`config/reference.yaml`), "
        "avoids contact. FALSE is not a proof of physical inevitability. `handback_required`: "
        "braking at a fixed deceleration (the nominal design authority, frozen) from hazard "
        "onset does not avoid contact (independent of the tested ACC's authority). Both "
        "are scenario properties, computed for every run independently of the system.", "",
        _md_table(store.query(
            "SELECT count(*) AS runs, "
            "count(*) FILTER (WHERE NOT avoidable_by_reference) AS not_avoided_by_reference, "
            "count(*) FILTER (WHERE handback_required) AS handback_required, "
            "count(*) FILTER (WHERE collision) AS collisions, "
            "count(*) FILTER (WHERE collision AND avoidable_by_reference) "
            "AS collisions_avoidable_by_reference, "
            "count(*) FILTER (WHERE end_state = 'horizon_unresolved') AS unresolved FROM runs",
            campaign)), ""]


def exposure_lines(release: Release) -> list[str]:
    d = release.exposure_model.describe()
    zero = d["zero_exposure_regions"]
    return ["## Exposure model", "",
            f"`{d['label']}` ({d['structure']}, status: **{d['status']}**). {d['assumption']} "
            "Every rate and quantile in this report is conditional on this model.", "",
            "Zero-exposure subregions (inside the ODD, explicitly weighted 0): "
            + (", ".join(f"`{z}`" for z in zero) if zero else "none") + ".", ""]


def failing_cells(store, campaign: str, target: str | None = None) -> pd.DataFrame:
    """Coverage cells with target runs, most first: candidate triggering conditions."""
    target = target or default_target()
    df = store.query(f"SELECT *, ({target_predicate(target)}) AS failed FROM runs", campaign,
                     max_rows=10**9)
    counts: dict[tuple, list[int]] = {}
    odd = load_odd()
    for rec in df.to_dict("records"):
        c = counts.setdefault(cell_of(rec, odd), [0, 0])
        c[0] += 1
        c[1] += bool(rec["failed"])
    rows = []
    for cell, (runs, fails) in counts.items():
        if fails:
            d = describe_cell(cell, odd)
            scen, drv = d.pop("scenario"), d.pop("driver_state", "-")
            own = scenario_param(scen)
            lo, hi = d.pop(own)
            rows.append({"scenario": scen, "driver_state": drv,
                         **{k: f"{a:g}-{b:g}" for k, (a, b) in d.items()},
                         "scenario_param": f"{own} {lo:g}-{hi:g}", "runs": runs,
                         target: fails})
    out = pd.DataFrame(rows)
    return out.sort_values([target, "runs"], ascending=[False, True]) if len(out) else out


def discovery_lines(store, campaign: str) -> list[str]:
    target = default_target()
    curve = failure_curve(store, campaign, target)
    n = len(curve)
    first = curve.loc[curve["failures"] > 0, "runs"].min() if n else None
    cells = failing_cells(store, campaign, target)
    return [
        "## Discovery", "",
        "Search campaigns choose where to look, so their rates say nothing about real-world "
        "risk and are not reported. What matters is what the search found and how fast. "
        f"Discovery target: `{target}` = `{target_predicate(target)}` "
        "(`config/discovery.yaml`; a search heuristic, not an acceptance criterion).", "",
        f"- Runs executed: {n}",
        f"- Target runs: {int(curve['failures'].iloc[-1]) if n else 0}",
        f"- Distinct target coverage cells: {len(cells)}",
        f"- Runs to first target run: {first if pd.notna(first) else 'none found'}",
        "", "### Coverage cells with target runs", "", _md_table(cells), ""]


def conditions_lines(bundle: dict | None) -> list[str]:
    lines = ["## Triggering conditions and evidence", ""]
    if not bundle or not bundle["conditions"]:
        return lines + ["_No triggering condition was claimed._", ""]
    lines += [f"Every condition below passed the mandatory evidence protocol "
              f"(`avval/evidence.py`). Evidence bundle SHA-256: `{bundle['bundle_sha256']}`.", ""]
    for i, tc in enumerate(bundle["conditions"], 1):
        t, e = tc["test"], tc["evidence"]
        r = t["result"]
        lo, hi = r["inside_rate_ci95"]
        lines += [f"### TC-{i:02d}: {tc['description']}", "",
                  f"Predicate: `{tc['predicate']}`", "",
                  f"- Condition SHA-256 `{tc['condition_sha256']}`",
                  f"- Predicate test `{t['id']}` (target `{t['target']}`, on {t['n_runs']} runs): "
                  f"{r['runs_inside']} runs inside, target rate inside {_fmt(r['target_rate_inside'])} "
                  f"[95% two-sided {_fmt(lo)}, {_fmt(hi)}], outside "
                  f"{_fmt(r['target_rate_outside'])}, lift {_fmt(r['lift'])}",
                  f"- Evidence query `{e['id']}` (result SHA-256 `{e['rows_sha256'][:16]}…`"
                  + (", truncated" if e["truncated"] else "") + "):", "",
                  "```sql", e["sql"].strip(), "```", "",
                  _md_table(pd.DataFrame(e["rows"]), max_rows=15), ""]
    return lines


def tests_lines(bundle: dict | None) -> list[str]:
    if not bundle:
        return []
    tests = [x for x in bundle["ledger"]["entries"] if x["kind"] == "test_predicate"]
    if not tests:
        return ["## Hypothesis tests", "", "_No test_predicate calls._", ""]
    rows = [{"#": x["seq"], "id": x["sha256"][:12], "where": f"`{x['where']}`",
             "target": x["target"], "runs": x["n_runs"],
             "inside": x["result"]["runs_inside"],
             "rate inside": _fmt(x["result"]["target_rate_inside"]),
             "rate outside": _fmt(x["result"]["target_rate_outside"]),
             "lift": _fmt(x["result"]["lift"])} for x in tests]
    return ["## Hypothesis tests", "", "Every `test_predicate` call, in order, over the "
            "agent's own runs (full records in the evidence bundle).", "",
            _md_table(pd.DataFrame(rows), max_rows=len(rows)), ""]


def _write(name: str, lines: list[str]) -> Path:
    path = RESULTS_DIR / f"report_{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_estimation_report(store, campaign: str, release: Release | None = None,
                            author: str = "estimation (automatic)", final: bool = False) -> Path:
    """Release verdict: acceptance criteria on a nominal estimation campaign. A campaign
    that is not eligible (lifecycle, release, runtime, data hash) gets a report without a
    verdict; with `final`, an ineligible or development campaign is refused outright."""
    from .estimation import eligibility
    from .evaluation import release_decision
    rec = store.get_campaign(campaign)
    if rec is None:
        raise LookupError(f"no campaign {campaign!r}")
    release = release or Release.build(policy_sha256=rec["provenance"]["policy_sha256"])
    problems = eligibility(store, rec, release, final=final)
    if final and problems:
        raise ValueError(f"{campaign!r} is not final release evidence: " + "; ".join(problems))
    acc = evaluate_acceptance(store, campaign, release.acceptance, release.reference)
    decision = release_decision(acc, rec["evidence_mode"])
    head = (f"## Verdict: {decision['formal_decision']}" if not problems else
            "## Verdict: none (this campaign is not eligible release evidence: "
            + "; ".join(problems) + ")")
    return _write(campaign, [
        *_header(store, campaign, author, "Validation report"), head, "",
        *decision_lines(decision),
        f"Evaluated on `{campaign}` ({store.n_runs(campaign)} runs sampled from the exposure "
        f"model): {verdict_summary(acc)}", "",
        "## Acceptance criteria", "", *acceptance_lines(acc),
        *exposure_lines(release), *reference_lines(store, campaign),
        *coverage_lines(store, campaign)])


def write_search_report(store, campaign: str, summary: str, author: str,
                        bundle: dict | None = None, verdict: dict | None = None,
                        include_verdict: bool = False) -> Path:
    """Search campaign report: discovery and (for the agent) evidence-backed conditions.

    With `include_verdict`, the release verdict of an estimation campaign of the SAME release
    and runtime is attached (`verdict`, from estimation.release_verdict); otherwise the
    report says why none is shown. Search reports never compute a verdict themselves.
    """
    lines = [*_header(store, campaign, author, "Search report"), "## Summary", "",
             summary.strip(), ""]
    if include_verdict:
        if verdict is None:
            lines += ["## Release verdict", "", "_No eligible estimation campaign of this "
                      "campaign's release and runtime exists, so no verdict is shown._", ""]
        else:
            lines += [f"## Release verdict (from estimation campaign "
                      f"`{verdict['estimation_campaign']}`): {verdict['verdict']}", "",
                      f"Not computed from this search campaign; same release ID "
                      f"`{verdict['release_id'][:16]}…`. {verdict_summary(verdict['criteria'])}",
                      "", *decision_lines(verdict["decision"]),
                      *acceptance_lines(verdict["criteria"])]
    lines += [*discovery_lines(store, campaign), *reference_lines(store, campaign),
              *coverage_lines(store, campaign), *conditions_lines(bundle), *tests_lines(bundle)]
    return _write(campaign, lines)
