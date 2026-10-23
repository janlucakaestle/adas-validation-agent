"""Figures: failure-boundary maps (characterisation) and failure-discovery curves."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import RESULTS_DIR  # noqa: E402
from .evaluation import failure_curve  # noqa: E402
from .sim import simulate  # noqa: E402


def failure_boundary(policy, ego_speed=30.0, friction=0.7, seeds=8, res=24):
    """Collision probability over (headway, lead_decel) for lead_brake, attentive vs.
    distracted, under the current nominal release (a characterisation figure, not evidence).
    Writes the figure and its data (failure_boundary.json, with the release ID) so any claim
    read off the figure can be audited."""
    import json

    from .config import Release, param_range
    release = Release.build(policy)
    params = release.sim_params
    headways = np.linspace(*param_range("headway", "lead_brake"), res)
    decels = np.linspace(1, 9, res)
    states = [("attentive", "Attentive driver"), ("distracted", "Distracted driver at hand-back")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, constrained_layout=True)
    data = {"release_id": release.release_id, "ego_speed": ego_speed, "friction": friction,
            "seeds": list(range(seeds)), "headways": headways.tolist(),
            "lead_decels": decels.tolist(), "p_collision": {}}
    for ax, (state, title) in zip(axes, states):
        p = np.zeros((res, res))
        for i, h in enumerate(headways):
            for j, s in enumerate(decels):
                case = dict(scenario="lead_brake", ego_speed=ego_speed, headway=h, lead_decel=s,
                            friction=friction, driver_state=state)
                p[i, j] = np.mean([simulate(case, policy, k, params)[0]["collision"]
                                   for k in range(seeds)])
        data["p_collision"][state] = p.tolist()
        im = ax.imshow(p, origin="lower", aspect="auto", cmap="Reds", vmin=0, vmax=1,
                       extent=[decels[0], decels[-1], headways[0], headways[-1]])
        ax.set_title(title)
        ax.set_xlabel("Lead vehicle deceleration (m/s²)")
    axes[0].set_ylabel("Initial time headway (s)")
    fig.colorbar(im, ax=axes, label="P(collision)")
    fig.suptitle(f"Lead-vehicle braking at {ego_speed:.0f} m/s, friction μ = {friction}")
    path = RESULTS_DIR / "failure_boundary.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    (RESULTS_DIR / "failure_boundary.json").write_text(json.dumps(data), encoding="utf-8")
    return path


# Categorical slots 1-7 of the reference palette, in fixed order (validated with
# validate_palette.js on this surface; contrast relief: direct end labels + legend); ink/grid tokens from the same system. Colour follows the strategy, not its rank.
SERIES = {"random": "#2a78d6", "grid": "#eb6834", "agent": "#1baf7a", "cem": "#eda100",
          "evolutionary": "#e87ba4", "boundary": "#008300", "bayesopt": "#4a3aa7"}
SURFACE, INK, INK_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"


def sensitivity_figure(df, proto):
    """One-at-a-time design: small multiples, one column per factor, one row per quantity.
    The first rows are primary responses as paired differences from the nominal variant (Δ,
    95% paired-bootstrap intervals); the last row is a secondary rare-event rate with its
    Clopper-Pearson interval. The nominal value is the ringed point."""
    factors = list(proto["factors"])
    rows = [("eff_ttc_p05_diff", "eff_ttc_p05_diff_lo", "eff_ttc_p05_diff_hi",
             "Δ 5th pct. effective\nTTC [s] (primary)", False),
            ("required_decel_exceedance_diff", "required_decel_exceedance_diff_lo",
             "required_decel_exceedance_diff_hi", "Δ req. decel > 3.5\n(primary)", True),
            ("near_miss_1p5s_diff", "near_miss_1p5s_diff_lo", "near_miss_1p5s_diff_hi",
             "Δ near miss < 1.5 s\n(primary)", True),
            ("attentive_rate", "attentive_ci_low", "attentive_ci_high",
             "Attentive collision rate\n(secondary)", True)]
    rows = [r for r in rows if r[0] in df]
    df = df.copy()
    base = df.iloc[0]
    fig, axes = plt.subplots(len(rows), len(factors), figsize=(2.1 * len(factors),
                                                               2.6 * len(rows)),
                             sharey="row", constrained_layout=True, facecolor=SURFACE,
                             squeeze=False)
    color = SERIES["random"]
    for j, name in enumerate(factors):
        col = f"factor:{name}"
        sub = df.iloc[1:][df.iloc[1:][col] != base[col]] if col in df else df.iloc[0:0]
        x = np.r_[sub[col].to_numpy(float), float(base[col])] if col in df else np.array([0.0])
        order = np.argsort(x)
        for i, (val, lo, hi, ylabel, pct) in enumerate(rows):
            ax = axes[i, j]
            ax.set_facecolor(SURFACE)
            y = pd.to_numeric(np.r_[sub[val].to_numpy(), base[val]], errors="coerce")[order]
            if lo:
                ylo = pd.to_numeric(np.r_[sub[lo].to_numpy(), base[lo]], errors="coerce")[order]
                yhi = pd.to_numeric(np.r_[sub[hi].to_numpy(), base[hi]], errors="coerce")[order]
                ax.errorbar(x[order], y, yerr=[y - ylo, yhi - y], color=color, lw=2, marker="o",
                            ms=5, capsize=3, elinewidth=1.2)
            else:
                ax.plot(x[order], y, color=color, lw=2, marker="o", ms=5)
            ax.plot([float(base[col])] if col in df else [0.0], [base[val]], marker="o", ms=10,
                    mfc="none", mec=INK_2, mew=1.2)
            ax.grid(color=GRID, lw=0.6)
            ax.tick_params(colors=MUTED, labelsize=7)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            if pct:
                ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
            if j == 0:
                ax.set_ylabel(ylabel, color=INK_2, fontsize=8)
            if i == len(rows) - 1:
                ax.set_xlabel(name, color=INK_2, fontsize=7)
    fig.suptitle("Sensitivity, one factor at a time (same sample; ringed point = nominal)",
                 color=INK, fontsize=11, x=0.01, ha="left")
    path = RESULTS_DIR / "sensitivity_oat.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def discovery_curves(store, groups: dict[str, list[str]], target: str | None = None):
    """Mean distinct-failing-cells curve per strategy across its seeds, with a min-max band.

    `groups` maps a strategy name to its campaigns (one per seed). Curves are truncated to
    the shortest campaign of each strategy so every point averages the same seeds.
    """
    fig, ax = plt.subplots(figsize=(7.5, 4.4), constrained_layout=True, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    extra = iter(["#e34948"])  # slot 8; a ninth series folds into small multiples
    for name, campaigns in groups.items():
        curves = [failure_curve(store, c, target)["distinct_failing_cells"].to_numpy()
                  for c in campaigns]
        curves = [c for c in curves if len(c)]
        if not curves:
            continue
        n = min(len(c) for c in curves)
        y = np.vstack([c[:n] for c in curves])
        x = np.arange(1, n + 1)
        color = SERIES.get(name) or next(extra)
        label = f"{name} (mean of {len(curves)} seed{'s' if len(curves) > 1 else ''})"
        if len(curves) > 1:
            ax.fill_between(x, y.min(0), y.max(0), color=color, alpha=0.15, lw=0)
        ax.plot(x, y.mean(0), color=color, lw=2, label=label)
        ax.annotate(name, (x[-1], y.mean(0)[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", color=INK_2, fontsize=9)
    ax.set_xlabel("Simulation runs", color=INK_2)
    ax.set_ylabel("Distinct target coverage cells found", color=INK_2)
    ax.set_title("How fast does each strategy find distinct failure modes?\n"
                 "Line: mean across seeds · band: min–max across seeds",
                 color=INK, fontsize=11, loc="left")
    ax.grid(color=GRID, lw=0.6)
    ax.tick_params(colors=MUTED)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.set_ylim(bottom=0)
    ax.margins(x=0.08)
    ax.legend(frameon=False, labelcolor=INK_2, loc="upper left")
    path = RESULTS_DIR / "discovery_curves.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path
