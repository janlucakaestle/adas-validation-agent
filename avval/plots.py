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
    """Collision probability over (gap, lead_decel) for lead_brake, attentive vs. distracted."""
    from .config import param_range
    headways = np.linspace(*param_range("headway", "lead_brake"), res)
    decels = np.linspace(1, 9, res)
    states = [("attentive", "Attentive driver"), ("distracted", "Distracted driver at hand-back")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True, constrained_layout=True)
    for ax, (state, title) in zip(axes, states):
        p = np.zeros((res, res))
        for i, h in enumerate(headways):
            for j, s in enumerate(decels):
                case = dict(scenario="lead_brake", ego_speed=ego_speed, headway=h, lead_decel=s,
                            friction=friction, driver_state=state)
                p[i, j] = np.mean([simulate(case, policy, k)[0]["collision"] for k in range(seeds)])
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
    return path


# Categorical slots 1-3 of the reference palette (validated for CVD separation on this
# surface); ink/grid tokens from the same system. Colour follows the strategy, not its rank.
SERIES = {"random": "#2a78d6", "grid": "#eb6834", "agent": "#1baf7a"}
SURFACE, INK, INK_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"


def sensitivity_figure(df):
    """Small multiples: one column per assumption, one row per quantity, 95% intervals.

    Each panel is a single series (no legend needed); the nominal value is the ringed point.
    """
    from .sensitivity import ASSUMPTIONS
    rows = [("attentive_rate", "attentive_ci_low", "attentive_ci_high",
             "Attentive preventable\ncollision rate", None),
            ("AC-03_value", "AC-03_ci_low", "AC-03_ci_high",
             "AC-03: misuse hand-back\ncollision rate", 0.05)]
    df = df.copy()
    for cols in rows:  # a criterion with no data holds None: plot it as a gap
        for c in cols[:3]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    base = df[df["assumption"] == "baseline"].iloc[0]
    fig, axes = plt.subplots(len(rows), len(ASSUMPTIONS), figsize=(12, 5.6), sharey="row",
                             constrained_layout=True, facecolor=SURFACE)
    color = SERIES["random"]  # categorical slot 1: one series per panel
    for j, (name, spec) in enumerate(ASSUMPTIONS.items()):
        sub = df[df["assumption"] == name]
        nom_x = float(sub["nominal"].iloc[0])
        x = np.r_[sub["value"].to_numpy(float), nom_x]  # the baseline sits at the nominal value
        order = np.argsort(x)
        for i, (val, lo, hi, ylabel, target) in enumerate(rows):
            ax = axes[i, j]
            ax.set_facecolor(SURFACE)
            y = np.r_[sub[val].to_numpy(float), base[val]][order]
            ylo = np.r_[sub[lo].to_numpy(float), base[lo]][order]
            yhi = np.r_[sub[hi].to_numpy(float), base[hi]][order]
            xs = x[order]
            ax.errorbar(xs, y, yerr=[y - ylo, yhi - y], color=color, lw=2, marker="o",
                        ms=6, capsize=3, elinewidth=1.2)
            ax.plot([nom_x], [base[val]], marker="o", ms=11, mfc="none", mec=INK_2, mew=1.2)
            if target is not None:
                ax.axhline(target, color=MUTED, lw=1, ls="--")
                if j == len(ASSUMPTIONS) - 1:
                    ax.annotate("target", (1, target), xycoords=("axes fraction", "data"),
                                xytext=(-2, 3), textcoords="offset points", ha="right",
                                color=MUTED, fontsize=8)
            ax.grid(color=GRID, lw=0.6)
            ax.tick_params(colors=MUTED, labelsize=8)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
            for side in ("left", "bottom"):
                ax.spines[side].set_color("#c3c2b7")
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
            if j == 0:
                ax.set_ylabel(ylabel, color=INK_2, fontsize=9)
            if i == len(rows) - 1:
                ax.set_xlabel(spec["label"], color=INK_2, fontsize=9)
            top = df[hi].max()  # NaN-skipping; NaN only if the whole row has no data
            ax.set_ylim(0, 1.08 * top if pd.notna(top) and top > 0 else 1.0)
    fig.suptitle("Sensitivity to one assumption at a time (same sample; 95% intervals; "
                 "ringed point = nominal)", color=INK, fontsize=11, x=0.01, ha="left")
    path = RESULTS_DIR / "sensitivity.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def discovery_curves(store, groups: dict[str, list[str]]):
    """Mean distinct-failing-cells curve per strategy across its seeds, with a min-max band.

    `groups` maps a strategy name to its campaigns (one per seed). Curves are truncated to
    the shortest campaign of each strategy so every point averages the same seeds.
    """
    fig, ax = plt.subplots(figsize=(7.5, 4.4), constrained_layout=True, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    extra = iter(["#eda100", "#e87ba4", "#008300"])  # slots 4-6 for any other strategy name
    for name, campaigns in groups.items():
        curves = [failure_curve(store, c)["distinct_failing_cells"].to_numpy() for c in campaigns]
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
    ax.set_ylabel("Distinct failing coverage cells found", color=INK_2)
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
