"""Non-agentic search baselines, run with the same budget and the same tools."""
from __future__ import annotations

import numpy as np

from .campaign import Campaign, random_case
from .config import load_odd
from .evaluation import all_cells, describe_cell
from .report import write_search_report


def random_search(campaign: Campaign) -> None:
    campaign.run([random_case(campaign.rng) for _ in range(campaign.remaining)])


def coverage_grid(campaign: Campaign) -> None:
    """One random point per coverage cell (shuffled), then random sampling for the rest."""
    drivers = load_odd()["parameters"]["driver_state"]["values"]
    cells = all_cells()
    campaign.rng.shuffle(cells)
    cases = []
    for cell in cells:
        d = describe_cell(cell)
        case = {"scenario": d["scenario"], "driver_state": str(campaign.rng.choice(drivers))}
        for k in list(d)[1:]:  # the scenario's binned parameters, in bin order
            case[k] = float(campaign.rng.uniform(*d[k]))
        cases.append(case)
    campaign.run(cases)
    random_search(campaign)


def auto_report(campaign: Campaign, method: str) -> str:
    """Search report for a baseline campaign: discovery metrics only, no verdict."""
    summary = (f"A **{method}** baseline search campaign. It reports what it found (discovery "
               "metrics, failing coverage cells) but no release verdict: verdicts come only from "
               "the exposure-weighted estimation campaign (`python -m avval.cli estimate`). "
               "No triggering-condition analysis is performed by the baseline.")
    return str(write_search_report(campaign.store, campaign.name, summary, [],
                                   author=f"baseline ({method})"))
