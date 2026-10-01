"""Numbers behind the README's findings, recomputed from the stored campaigns.

Every figure the README quotes about margin erosion, comfort and the single seed-0 baseline
campaigns comes from `results/findings.md`, written here, so each claim traces to a file.
"""
from __future__ import annotations

from . import RESULTS_DIR
from .benchmark import REGIONS, seed_campaigns

ATTENTIVE_PREVENTABLE = REGIONS["attentive_preventable_collision"]


def _one(con, sql: str, params=()):
    return con.execute(sql, list(params)).fetchone()


def margin_erosion(store) -> list[str]:
    """Hand-back monitor vs. acceleration-aware TTC across all benchmark seed campaigns."""
    names = seed_campaigns(store, "random") + seed_campaigns(store, "grid")
    if not names:
        return ["_No benchmark campaigns._"]
    marks = ", ".join("?" * len(names))
    base = f"FROM all_runs WHERE campaign IN ({marks}) AND NOT collision AND NOT tor_issued"
    con = store.con
    n_runs = _one(con, f"SELECT count(*) FROM all_runs WHERE campaign IN ({marks})", names)[0]
    plain = _one(con, f"SELECT count(*) {base} AND min_ttc < 2.0", names)[0]
    n, lo, lead = _one(con, f"SELECT count(*), min(min_ttc_accel), "
                            f"count(*) FILTER (WHERE scenario = 'lead_brake') "
                            f"{base} AND min_ttc_accel < 2.0", names)
    wet, dry = _one(con, f"SELECT count(*) FILTER (WHERE friction < 0.75), "
                         f"count(*) FILTER (WHERE friction >= 0.75) "
                         f"{base} AND min_ttc_accel < 2.0", names)
    return [
        f"Across {len(names)} benchmark campaigns ({n_runs:,} runs; `random_s*` and `grid_s*`):",
        "",
        f"- runs without collision or hand-back whose constant-speed TTC fell below 2 s: "
        f"**{plain}**",
        f"- runs without collision or hand-back whose acceleration-aware TTC fell below 2 s: "
        f"**{n}** ({lead} of them lead braking), minimum **{lo:.2f} s**" if n else
        "- runs without collision or hand-back whose acceleration-aware TTC fell below 2 s: 0",
        f"- of those, friction below 0.75: {wet}; friction 0.75 or above: {dry}"]


def comfort(store, campaign: str = "estimate") -> list[str]:
    """AC-04's population (no hand-back) with filtered and raw jerk, on the estimation."""
    if not store.n_runs(campaign):
        return [f"_No campaign `{campaign}`._"]
    row = store.query(
        "SELECT count(*) AS n, quantile_cont(max_jerk, 0.95) AS p95, "
        "quantile_cont(max_jerk_raw, 0.95) AS p95_raw, "
        "count(*) FILTER (WHERE max_jerk > 5.0) AS over, "
        "count(*) FILTER (WHERE max_jerk > 5.0 AND scenario = 'cut_in') AS over_cut_in, "
        "max(max_jerk) AS worst FROM runs WHERE NOT tor_issued", campaign).iloc[0]
    return [
        f"Runs without a hand-back in `{campaign}` (AC-04's population): {int(row['n']):,}.",
        "",
        f"- 95th percentile of filtered jerk (`max_jerk`, 0.5 s moving average): "
        f"**{row['p95']:.2f} m/s³**",
        f"- 95th percentile of raw 20 Hz sample-difference jerk (`max_jerk_raw`): "
        f"**{row['p95_raw']:.2f} m/s³**",
        f"- runs above 5 m/s³ (filtered): {int(row['over']):,}, of which cut-ins "
        f"{int(row['over_cut_in']):,}; largest {row['worst']:.2f} m/s³"]


def single_baselines(store) -> list[str]:
    """The single seed-0 baseline campaigns `random` and `grid`."""
    lines = ["| campaign | runs | attentive runs | collisions | unpreventable "
             "| attentive preventable collisions |", "|---|---|---|---|---|---|"]
    for name in ("random", "grid"):
        if not store.n_runs(name):
            continue
        r = store.query(
            "SELECT count(*) AS n, count(*) FILTER (WHERE driver_state = 'attentive') AS att, "
            "count(*) FILTER (WHERE collision) AS col, "
            "count(*) FILTER (WHERE collision AND NOT preventable) AS unprev, "
            f"count(*) FILTER (WHERE {ATTENTIVE_PREVENTABLE}) AS ap FROM runs", name).iloc[0]
        lines.append(f"| `{name}` | {int(r['n'])} | {int(r['att'])} | {int(r['col'])} "
                     f"| {int(r['unprev'])} | {int(r['ap'])} |")
    return lines


def write_findings(store) -> str:
    lines = ["# Findings: supporting numbers", "",
             "Recomputed from the stored campaigns by `python -m avval.cli findings`.", "",
             "## Silent margin erosion", "", *margin_erosion(store), "",
             "## Comfort and the jerk definition", "", *comfort(store), "",
             "## Single seed-0 baseline campaigns", "", *single_baselines(store), ""]
    path = RESULTS_DIR / "findings.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)
