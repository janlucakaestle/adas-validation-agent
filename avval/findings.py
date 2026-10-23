"""Numbers behind the README's findings, recomputed from stored campaigns.

Every figure the README quotes about margin erosion, comfort and hand-back behaviour comes
from `results/findings.md`, written here from named campaigns, so each claim traces to a
file and to the release that produced it.
"""
from __future__ import annotations

from . import RESULTS_DIR
from .config import Release


def margin_erosion(store, campaigns: list[str], release: Release) -> list[str]:
    """Runs whose stop-aware acceleration TTC fell below the monitor's TTC threshold with no
    hand-back and no collision, across the given search campaigns."""
    if not campaigns:
        return ["_No campaigns._"]
    p = release.sim_params
    marks = ", ".join("?" * len(campaigns))
    base = (f"FROM all_runs WHERE campaign IN ({marks}) AND NOT collision AND NOT tor_issued "
            f"AND min_ttc_accel < {p.tor_ttc_s}")
    con = store.con
    n_runs = con.execute(f"SELECT count(*) FROM all_runs WHERE campaign IN ({marks})",
                         campaigns).fetchone()[0]
    n, lo, lead = con.execute(f"SELECT count(*), min(min_ttc_accel), count(*) FILTER "
                              f"(WHERE scenario = 'lead_brake') {base}", campaigns).fetchone()
    return [f"Across {len(campaigns)} campaigns ({n_runs:,} runs): runs without collision or "
            f"hand-back whose stop-aware acceleration TTC fell below the monitor's "
            f"{p.tor_ttc_s:g} s: **{n}**" + (f" ({lead} lead braking), minimum **{lo:.2f} s**"
                                              if n else ""),
            "", "Why the monitor stayed silent in these runs is decomposed by "
            "`python -m avval.cli diagnose` (`results/handback_diagnostics_<campaign>.md`)."]


def comfort(store, campaign: str, release: Release) -> list[str]:
    """AC-04's population (all runs; automated-control jerk) with whole-run and raw jerk."""
    if not store.n_runs(campaign):
        return [f"_No campaign `{campaign}`._"]
    thr = next(c["threshold"] for c in release.acceptance["criteria"] if c["id"] == "AC-04")
    r = store.query(
        "SELECT count(*) AS n, quantile_cont(coalesce(max_jerk_automated, 'Infinity'::DOUBLE), "
        "0.95) AS p95_auto, quantile_cont(max_jerk, 0.95) AS p95_run, "
        "quantile_cont(max_jerk_raw, 0.95) AS p95_raw, "
        f"count(*) FILTER (WHERE max_jerk_automated > {thr}) AS over, "
        f"count(*) FILTER (WHERE max_jerk_automated > {thr} AND scenario = 'cut_in') AS over_ci "
        "FROM runs", campaign).iloc[0]
    return [f"All {int(r['n']):,} runs of `{campaign}` (AC-04's population):", "",
            f"- 95th percentile of automated-control jerk (0.5 s moving average): "
            f"**{r['p95_auto']:.2f} m/s³**",
            f"- whole-run filtered jerk (includes the driver phase): {r['p95_run']:.2f} m/s³",
            f"- raw sample-difference jerk: {r['p95_raw']:.2f} m/s³",
            f"- runs above {thr:g} m/s³ (automated control): {int(r['over']):,}, of which "
            f"cut-ins {int(r['over_ci']):,}"]


def write_findings(store, estimation: str, search_campaigns: list[str],
                   release: Release, final: bool = False) -> str:
    """Refuses any campaign not COMPLETE under this release and runtime with intact data
    (and, with `final`, not final evidence): findings never mix releases."""
    from .estimation import require_campaigns
    require_campaigns(store, [estimation], release, kind="nominal_estimation", final=final)
    require_campaigns(store, search_campaigns, release, kind="search", final=final,
                      full_plan=False)
    lines = ["# Findings: supporting numbers", "",
             f"Recomputed by `python -m avval.cli findings` under release "
             f"`{release.release_id[:16]}…`. Conditional on this release's simulator, models "
             "and exposure model.", "",
             "## Margin erosion without hand-back", "",
             *margin_erosion(store, search_campaigns, release), "",
             "## Comfort and the jerk definition", "", *comfort(store, estimation, release), ""]
    path = RESULTS_DIR / "findings.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
