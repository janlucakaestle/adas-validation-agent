"""Estimation campaigns: measure rates on an exposure-weighted sample of the ODD.

Search campaigns (random, grid, adaptive, agent) choose where to look, so their rates reflect
the search strategy, not the exposure distribution. They report discovery metrics only.
Acceptance criteria and the release verdict are computed on a NOMINAL estimation campaign:

- sampled from the release's exposure model (cases from per-run streams, so a resumed
  campaign draws exactly the cases an uninterrupted one would);
- with no simulation overrides (a variant is a `sensitivity` campaign and is never eligible);
- COMPLETE, with every planned run stored and its data hash recorded;
- recorded under the current release ID (policy, parsed configs, code) and runtime ID, with
  a data hash that still matches the stored rows.

`find_estimation` returns only a campaign meeting all of these; a crashed fragment, a
variant or a campaign from another release can never become release evidence.
"""
from __future__ import annotations

from .campaign import Campaign
from .config import Release
from .evaluation import evaluate_acceptance
from .provenance import runtime_id

KIND = "nominal_estimation"
CHUNK = 500  # runs per stored batch: bounds the work lost to a crash


def _cases(camp: Campaign, start: int, stop: int) -> list[dict]:
    model = camp.release.exposure_model
    return [model.sample(camp.case_rng(i)) for i in range(start, stop)]


def run_planned(camp: Campaign, progress=None) -> dict:
    """Run the remaining planned runs of an exposure-sampled campaign, then finish it."""
    while camp.remaining > 0:
        start = camp.used
        camp.run(_cases(camp, start, min(start + CHUNK, camp.budget)))
        if progress:
            progress(camp.used, camp.budget)
    return camp.finish()


def run_estimation(store, policy, n: int, seed: int = 0, name: str = "estimate",
                   kind: str = KIND, overrides: dict | None = None,
                   release: Release | None = None, protocol_id: str | None = None,
                   progress=None, evidence_mode: str = "development") -> Campaign:
    """Create and run an exposure-weighted campaign of n runs. kind='nominal_estimation'
    refuses overrides; use kind='sensitivity' (or a hold-out kind) otherwise."""
    camp = Campaign(name, store, policy, n, seed=seed, method="estimate", kind=kind,
                    overrides=overrides, release=release, protocol_id=protocol_id,
                    case_source="exposure", evidence_mode=evidence_mode)
    run_planned(camp, progress)
    return camp


def resume_estimation(store, policy, name: str, progress=None) -> Campaign:
    camp = Campaign.resume(name, store, policy)
    if camp.record["case_source"] != "exposure":
        raise ValueError(f"{name!r} is not an exposure-sampled campaign")
    run_planned(camp, progress)
    return camp


def campaign_problems(store, rec: dict | None, release: Release, *, kind: str | None = None,
                      protocol_id: str | None = None, final: bool = False,
                      check_data: bool = True, full_plan: bool = True) -> list[str]:
    """Why a stored campaign may NOT be combined with evidence of `release` (empty = ok):
    lifecycle, release and runtime identity, run count, data hash, and optionally kind,
    protocol and final-evidence mode. Every report generator that takes campaign names uses
    this, so campaigns are never aggregated just because they share a database."""
    if rec is None:
        return ["no such campaign"]
    name = rec["campaign_id"]
    problems = []
    if kind is not None and rec["kind"] != kind:
        problems.append(f"kind is {rec['kind']}, not {kind}")
    if rec["status"] != "COMPLETE":
        problems.append(f"status is {rec['status']}")
    if rec["release_id"] != release.release_id:
        problems.append("recorded under a different release ID")
    if rec["runtime_id"] != runtime_id():
        problems.append("recorded under a different runtime ID")
    if protocol_id is not None and rec["protocol_id"] != protocol_id:
        problems.append("recorded under a different protocol ID")
    if final and rec["evidence_mode"] != "final":
        problems.append("development run (not final evidence)")
    n = store.n_runs(name)
    if rec["completed_runs"] != n or (full_plan and rec["planned_runs"] != n):
        problems.append(f"planned {rec['planned_runs']}, completed {rec['completed_runs']}, "
                        f"stored {n}")
    if check_data and not problems and store.data_hash(name) != rec["data_sha256"]:
        problems.append("stored rows do not match the recorded data hash")
    return problems


def require_campaigns(store, names: list[str], release: Release, **kw) -> None:
    """Raise listing every campaign that is not compatible with `release` (see above)."""
    bad = {n: campaign_problems(store, store.get_campaign(n), release, **kw) for n in names}
    bad = {n: p for n, p in bad.items() if p}
    if bad:
        raise ValueError("incompatible campaigns: " + "; ".join(
            f"{n}: {', '.join(p)}" for n, p in bad.items()))


def eligibility(store, rec: dict, release: Release, check_data: bool = True,
                final: bool = False) -> list[str]:
    """Reasons why a campaign record is NOT eligible as release evidence (empty = eligible).
    With `final`, only final-evidence campaigns qualify."""
    name = rec["campaign_id"]
    problems = []
    if rec["kind"] != KIND:
        problems.append(f"kind is {rec['kind']}, not {KIND}")
    if final and rec["evidence_mode"] != "final":
        problems.append("development run (not final evidence)")
    if rec["status"] != "COMPLETE":
        problems.append(f"status is {rec['status']}")
    if rec["overrides"]:
        problems.append("has simulation overrides")
    if rec["release_id"] != release.release_id:
        problems.append("recorded under a different release ID")
    if rec["runtime_id"] != runtime_id():
        problems.append("recorded under a different runtime ID")
    n = store.n_runs(name)
    if not rec["planned_runs"] == rec["completed_runs"] == n:
        problems.append(f"planned {rec['planned_runs']}, completed {rec['completed_runs']}, "
                        f"stored {n}")
    if check_data and not problems and store.data_hash(name) != rec["data_sha256"]:
        problems.append("stored rows do not match the recorded data hash")
    return problems


def find_estimation(store, policy=None, release: Release | None = None,
                    final: bool = False) -> str | None:
    """Most recent eligible nominal estimation for the current release, or None. With
    `final`, only a final-evidence estimation qualifies."""
    release = release or Release.build(policy)
    if not release.is_nominal:
        raise ValueError("release evidence is only defined for the nominal release")
    for rec in store.list_campaigns(kind=KIND, status="COMPLETE"):
        if not eligibility(store, rec, release, final=final):
            return rec["campaign_id"]
    return None


MISSING_HELP = ("No COMPLETE nominal estimation campaign matches the current release "
                "(policy, parsed configuration, code) and runtime. Run "
                "`python -m avval.cli estimate --n <N> --seed <S>` first. Acceptance criteria "
                "are evaluated only on such a campaign, never on a search, sensitivity or "
                "incomplete campaign.")


def release_verdict(store, policy=None, release: Release | None = None,
                    final: bool = False) -> dict:
    """The verdict layers for the current release, from its estimation campaign (with
    `final`, only a final-evidence estimation is used). Used by code and reports only; the
    search agent never sees it."""
    from .evaluation import release_decision
    release = release or Release.build(policy)
    est = find_estimation(store, release=release, final=final)
    if est is None:
        raise LookupError(MISSING_HELP)
    acc = evaluate_acceptance(store, est, release.acceptance, release.reference)
    decision = release_decision(acc, store.get_campaign(est)["evidence_mode"])
    return {"estimation_campaign": est, "estimation_runs": store.n_runs(est),
            "release_id": release.release_id, "verdict": decision["engineering_verdict"],
            "decision": decision, "criteria": acc}
