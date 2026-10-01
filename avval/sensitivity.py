"""One-at-a-time sensitivity of the verdict to the main modelling assumptions.

Each variant changes exactly one assumption and re-runs the *same* exposure-weighted
estimation sample: identical cases and per-run seeds as the baseline, so any difference
comes from the assumption, not from resampling. Variants run in parallel, each in its own
in-memory store, so nothing is written to results/runs.duckdb.

Recorded per variant: the attentive preventable collision rate (with 95% Clopper-Pearson
interval), every acceptance criterion's value and status, and the overall verdict.
"""
from __future__ import annotations

import copy
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from . import RESULTS_DIR
from .config import load_driver
from .evaluation import clopper_pearson, evaluate_acceptance, overall_verdict
from .policy import ACCEL_MIN
from .sim import TOR_REQ_DECEL

# The ranges come from the review (docs/design_review/TASKS.md, T12). Each assumption is evaluated at three
# points spanning its range; the nominal value is the shared baseline run.
ASSUMPTIONS = {
    "attentive_takeover_mean_s": {"label": "Attentive mean takeover time (s)",
                                  "range": (1.0, 1.8)},
    "attentive_takeover_sd_s": {"label": "Attentive takeover-time SD (s)", "range": (0.4, 0.6)},
    "acc_authority_mps2": {"label": "ACC braking authority (m/s²)", "range": (3.0, 4.5)},
    "tor_req_decel_mps2": {"label": "TOR required-deceleration threshold (m/s²)",
                           "range": (2.5, 3.5)},
}
POINTS_PER_ASSUMPTION = 3


def nominal() -> dict:
    drv = load_driver()
    return {"attentive_takeover_mean_s": drv["states"]["attentive"]["takeover_mean_s"],
            "attentive_takeover_sd_s": drv["states"]["attentive"]["takeover_sd_s"],
            "acc_authority_mps2": -ACCEL_MIN,
            "tor_req_decel_mps2": TOR_REQ_DECEL}


def sim_kwargs(assumption: str | None, value: float | None) -> dict:
    """simulate() overrides for one assumption set to `value` (nothing else changes)."""
    if assumption is None:
        return {}
    if assumption in ("attentive_takeover_mean_s", "attentive_takeover_sd_s"):
        drv = copy.deepcopy(load_driver())
        key = "takeover_mean_s" if assumption == "attentive_takeover_mean_s" else "takeover_sd_s"
        drv["states"]["attentive"][key] = value  # the other parameter keeps its nominal value
        return {"driver_cfg": drv}
    if assumption == "acc_authority_mps2":
        return {"acc_authority": value}
    if assumption == "tor_req_decel_mps2":
        return {"tor_req_decel": value}
    raise KeyError(assumption)


def variants() -> list[tuple[str | None, float | None]]:
    """Baseline first, then each assumption at evenly spaced points over its range
    (a point equal to the nominal value reuses the baseline)."""
    nom = nominal()
    out: list[tuple[str | None, float | None]] = [(None, None)]
    for name, spec in ASSUMPTIONS.items():
        for v in np.linspace(*spec["range"], POINTS_PER_ASSUMPTION):
            v = round(float(v), 4)
            if not np.isclose(v, nom[name]):
                out.append((name, v))
    return out


ATTENTIVE_PREVENTABLE = "driver_state = 'attentive' AND preventable"


def run_variant(policy, n: int, seed: int, assumption: str | None, value: float | None) -> dict:
    from .estimation import run_estimation
    from .store import Store
    store = Store(":memory:")
    camp = run_estimation(store, policy, n, seed=seed, name="sensitivity",
                          sim_kwargs=sim_kwargs(assumption, value), method="sensitivity")
    row = store.query("SELECT count(*) AS n, count(*) FILTER (WHERE collision) AS k FROM runs "
                      f"WHERE {ATTENTIVE_PREVENTABLE}", camp.name).iloc[0]
    k, m = int(row["k"]), int(row["n"])
    lo, hi = clopper_pearson(k, m) if m else (np.nan, np.nan)
    acc = evaluate_acceptance(store, camp.name)
    return {"assumption": assumption or "baseline", "value": value, "attentive_runs": m,
            "attentive_preventable_collisions": k,
            "attentive_rate": k / m if m else np.nan, "attentive_ci_low": lo,
            "attentive_ci_high": hi, "verdict": overall_verdict(acc),
            **{f"{a['id']}_status": a["status"] for a in acc},
            **{f"{a['id']}_value": a["value"] for a in acc},
            **{f"{a['id']}_ci_low": a["ci_low"] for a in acc},
            **{f"{a['id']}_ci_high": a["ci_high"] for a in acc},
            **{f"{a['id']}_n": a["n"] for a in acc}}


def run_sensitivity(policy, n: int = 2000, seed: int = 0, workers: int | None = None
                    ) -> pd.DataFrame:
    jobs = variants()
    if workers == 1:
        rows = [run_variant(policy, n, seed, a, v) for a, v in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(run_variant, policy, n, seed, a, v) for a, v in jobs]
            rows = [f.result() for f in futures]
    df = pd.DataFrame(rows)
    nom = nominal()
    df.loc[df["assumption"] == "baseline", "value"] = np.nan
    df["nominal"] = df["assumption"].map(nom)
    return df


def _fmt_rate(k, n, lo, hi) -> str:
    return f"{k}/{n} = {k / n:.2%} [{lo:.2%}, {hi:.2%}]" if n else "-"


def _cell(r, base, i: str) -> str:
    """Status with its value and n, bold when the status differs from the baseline."""
    status = r[f"{i}_status"]
    val = r[f"{i}_value"]
    text = status if pd.isna(val) else f"{status} ({val:.3g}, n={r[f'{i}_n']})"
    return text if status == base[f"{i}_status"] else f"**{text}**"


def write_sensitivity(df: pd.DataFrame, n: int, seed: int) -> tuple[str, str]:
    """results/sensitivity.md (table) and results/sensitivity.png (small multiples)."""
    from .plots import sensitivity_figure
    from .report import _md_table
    base = df[df["assumption"] == "baseline"].iloc[0]
    ids = sorted(c[:-7] for c in df.columns if c.endswith("_status"))
    rows = []
    for _, r in pd.concat([df[df["assumption"] == "baseline"],
                           df[df["assumption"] != "baseline"]]).iterrows():
        rows.append({
            "assumption": ("baseline (nominal)" if r["assumption"] == "baseline"
                           else f"{r['assumption']} = {r['value']:g} (nominal {r['nominal']:g})"),
            "attentive preventable collisions": _fmt_rate(
                r["attentive_preventable_collisions"], r["attentive_runs"],
                r["attentive_ci_low"], r["attentive_ci_high"]),
            **{i: _cell(r, base, i) for i in ids},
            "verdict": r["verdict"]})
    fig = sensitivity_figure(df)
    lines = [
        "# Sensitivity of the verdict to modelling assumptions", "",
        f"One assumption at a time; every variant re-runs the same exposure-weighted sample "
        f"({n} runs, seed {seed}: identical cases and per-run seeds). Statuses that differ from "
        "the baseline are in bold. Each criterion shows status (value, n); the attentive rate has "
        "a 95% Clopper-Pearson interval. Full numbers: `sensitivity.csv`.", "",
        _md_table(pd.DataFrame(rows), max_rows=len(rows)), "",
        "![Sensitivity](sensitivity.png)", ""]
    df.to_csv(RESULTS_DIR / "sensitivity.csv", index=False)
    path = RESULTS_DIR / "sensitivity.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path), str(fig)
