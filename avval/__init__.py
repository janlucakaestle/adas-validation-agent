"""avval: validation of a learned ADAS function (ACC with driver hand-back), with
agent-assisted failure discovery separated from exposure-weighted estimation."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
# Outputs (database, reports, bundles). AVVAL_RESULTS_DIR redirects them, e.g. for smoke
# runs that must not touch the published results/ directory.
RESULTS_DIR = Path(os.environ.get("AVVAL_RESULTS_DIR", ROOT / "results"))
