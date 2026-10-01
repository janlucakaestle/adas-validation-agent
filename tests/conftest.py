import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from avval.policy import LearnedACC, train_policy  # noqa: E402
from avval.store import Store  # noqa: E402


@pytest.fixture(scope="session")
def policy():
    p, _ = train_policy()  # production training config
    return p


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.duckdb")


@pytest.fixture(autouse=True)
def _no_writes_to_results(tmp_path, monkeypatch):
    """Reports and figures written by any test go to a temporary directory, never to results/."""
    import avval.benchmark as benchmark_mod
    import avval.plots as plots_mod
    import avval.report as report_mod
    import avval.sensitivity as sensitivity_mod
    for mod in (report_mod, benchmark_mod, plots_mod, sensitivity_mod):
        monkeypatch.setattr(mod, "RESULTS_DIR", tmp_path)
