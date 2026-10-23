import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from avval.policy import train_policy  # noqa: E402
from avval.store import Store  # noqa: E402

RESULT_WRITERS = ("report", "benchmark", "plots", "sensitivity", "agent", "holdout",
                  "findings", "compat", "package", "diagnostics", "cli")


@pytest.fixture(scope="session")
def policy():
    p, _ = train_policy()  # production training config
    return p


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.duckdb")


@pytest.fixture(autouse=True)
def _no_writes_to_results(tmp_path, monkeypatch):
    """Reports, figures and bundles written by any test go to a temporary directory."""
    import importlib
    for name in RESULT_WRITERS:
        mod = importlib.import_module(f"avval.{name}")
        monkeypatch.setattr(mod, "RESULTS_DIR", tmp_path)
    import avval.benchmark as bm
    import avval.compat as compat
    import avval.holdout as ho
    import avval.sensitivity as sens
    import avval.store as store_mod
    monkeypatch.setattr(bm, "MANIFEST_PATH", tmp_path / "benchmark_manifest.json")
    monkeypatch.setattr(ho, "FROZEN_PATH", tmp_path / "frozen_predicates.json")
    monkeypatch.setattr(ho, "REFERENCE_PATH", tmp_path / "reference_predicates.json")
    monkeypatch.setattr(ho, "PROTOCOL_PATH", tmp_path / "holdout_protocol.json")
    monkeypatch.setattr(sens, "MANIFEST_PATH", tmp_path / "sensitivity_manifest.json")
    monkeypatch.setattr(compat, "COMPAT_DIR", tmp_path / "compat")
    monkeypatch.setattr(store_mod, "DB_PATH", tmp_path / "default.duckdb")


def pytest_sessionfinish(session, exitstatus):
    """Fail the run if any test wrote into the real results/ directory."""
    from avval import ROOT
    started = getattr(session, "_avval_start", None)
    if started is None:
        return
    leaked = [p for p in (ROOT / "results").rglob("*")
              if p.is_file() and p.stat().st_mtime >= started and "legacy" not in p.parts]
    if leaked:
        session.exitstatus = 1
        print("\nTESTS WROTE INTO results/: " + ", ".join(str(p) for p in leaked))


def pytest_sessionstart(session):
    import time
    session._avval_start = time.time()
