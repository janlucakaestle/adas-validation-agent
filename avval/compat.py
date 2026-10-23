"""Machine-verifiable compatibility of stored campaigns with a release.

Historical evidence may be combined with (or rendered next to) the evidence of a release
only if compatibility is proven by a tool, never by a prose assertion:

- trivially, when the campaign was recorded under the same release ID and runtime ID; or
- by a compatibility declaration written by `verify_compatibility`, which re-simulates
  EVERY stored run of the campaign under the target release and checks that every stored
  column is reproduced exactly. The declaration records the campaign's data hash, both
  release IDs, the runtime, the number of runs checked and a hash of the evidence; it is
  only valid while all of these still match.
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np

from . import RESULTS_DIR
from .config import Release
from .frozen import content_hash
from .provenance import runtime_id
from .reference import References
from .replay import replay, same_value
from .store import COLUMNS

COMPAT_DIR = RESULTS_DIR / "compat"


def _path(campaign: str, release_id: str):
    return COMPAT_DIR / f"{campaign}__{release_id[:16]}.json"


def verify_compatibility(store, campaign: str, release: Release, policy,
                         write: bool = True) -> dict:
    rec = store.get_campaign(campaign)
    if rec is None or rec["status"] != "COMPLETE":
        raise ValueError(f"{campaign!r} is not a COMPLETE campaign")
    if rec["overrides"]:
        release = release.with_overrides(rec["overrides"])
    df = store.campaign_df(campaign)
    refs = References(release)
    mismatches = []
    for row in df.replace({np.nan: None}).to_dict("records"):
        again, _ = replay(row, policy, release, refs)
        bad = [c for c in COLUMNS if not same_value(row[c], again[c])]
        if bad:
            mismatches.append({"run_idx": int(row["run_idx"]), "columns": bad})
    result = {"schema": "compatibility/v3", "campaign": campaign,
              "campaign_data_sha256": rec["data_sha256"],
              "source_release_id": rec["release_id"], "target_release_id": release.release_id,
              "runtime_id": runtime_id(), "runs_checked": len(df),
              "mismatching_runs": len(mismatches), "first_mismatches": mismatches[:20],
              "verified": not mismatches and len(df) == rec["completed_runs"],
              "checked_at": datetime.now().isoformat(timespec="seconds")}
    result["evidence_sha256"] = content_hash({k: v for k, v in result.items()
                                              if k != "checked_at"})
    if write and result["verified"]:
        COMPAT_DIR.mkdir(parents=True, exist_ok=True)
        _path(campaign, release.release_id).write_text(json.dumps(result, indent=1),
                                                       encoding="utf-8")
    return result


def is_compatible(store, campaign: str, release: Release) -> tuple[bool, str]:
    """(compatible, reason) for combining `campaign` with evidence of `release`."""
    rec = store.get_campaign(campaign)
    if rec is None:
        return False, "no such campaign"
    if rec["status"] != "COMPLETE":
        return False, f"campaign status {rec['status']}"
    if rec["release_id"] == release.release_id and rec["runtime_id"] == runtime_id():
        return True, "same release and runtime ID"
    p = _path(campaign, release.release_id)
    if not p.exists():
        return False, ("recorded under release " + rec["release_id"][:12] + "; no verified "
                       "compatibility declaration for release " + release.release_id[:12])
    d = json.loads(p.read_text(encoding="utf-8"))
    body = {k: v for k, v in d.items() if k not in ("evidence_sha256", "checked_at")}
    ok = (content_hash(body) == d["evidence_sha256"] and d["verified"]
          and d["campaign_data_sha256"] == rec["data_sha256"] == store.data_hash(campaign)
          and d["target_release_id"] == release.release_id and d["runtime_id"] == runtime_id())
    return ok, ("verified by replay of every run (" + p.name + ")" if ok else
                "compatibility declaration does not match the current data, release or runtime")
