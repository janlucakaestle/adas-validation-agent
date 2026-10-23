"""Campaigns: the shared execution layer, with immutable identity and an explicit lifecycle.

Identity. A campaign is created once under a unique name (primary key in `campaigns`);
creating it again fails. Its release (policy, parsed configuration including any overrides,
code), runtime, exposure model and protocol are recorded at creation and cannot change: a
campaign can be resumed only by code and configuration with the same release and runtime
IDs.

Randomness. Every random stream is derived from immutable keys,
`derive_seed(campaign_seed, run_idx, purpose)`, never from a generator whose state lives
in memory. Run i therefore gets the same case and the same simulation seed whether the
campaign runs in one go or is resumed after a crash, and resuming cannot replay or shift a
stream.

Lifecycle. CREATED -> RUNNING -> COMPLETE (or FAILED). A campaign with a fixed plan
(estimation, hold-out) is COMPLETE only when every planned run is stored, and only then is
its data hash recorded. Only a COMPLETE campaign can be release evidence.
"""
from __future__ import annotations

import hashlib

import numpy as np

from .config import Release, driver_attributes, validate_case
from .provenance import provenance, runtime_id
from .reference import References
from .sim import simulate
from .store import Store

FIXED_PLAN_KINDS = ("nominal_estimation", "holdout_evaluation", "sensitivity",
                    "compatibility_replay")


FINAL_KINDS = ("search", "nominal_estimation", "holdout_evaluation", "sensitivity")


def require_final_evidence(kind: str) -> None:
    """Final-evidence campaigns need a clean, committed source tree and the locked
    environment. Development runs may be dirty, but are never final evidence."""
    from .provenance import final_evidence_problems
    if kind not in FINAL_KINDS:
        raise ValueError(f"kind {kind!r} cannot be final evidence")
    problems = final_evidence_problems()
    if problems:
        raise RuntimeError("final-evidence campaign refused: " + "; ".join(problems))


def derive_seed(campaign_seed: int, run_idx: int, purpose: str) -> int:
    """63-bit seed from immutable keys (SHA-256), stable across processes and platforms."""
    h = hashlib.sha256(f"avval/v3:{int(campaign_seed)}:{int(run_idx)}:{purpose}".encode())
    return int.from_bytes(h.digest()[:8], "big") >> 1


def stream(campaign_seed: int, run_idx: int, purpose: str) -> np.random.Generator:
    return np.random.default_rng(derive_seed(campaign_seed, run_idx, purpose))


class Campaign:
    """A campaign of simulated runs. Construct to CREATE a new one; use `resume` to continue."""

    def __init__(self, name: str, store: Store, policy, budget: int, seed: int = 0,
                 method: str = "manual", kind: str = "search", overrides: dict | None = None,
                 release: Release | None = None, protocol_id: str | None = None,
                 case_source: str = "adaptive", evidence_mode: str = "development",
                 _record: dict | None = None):
        self.name, self.store, self.policy = name, store, policy
        if _record is not None:  # resume path
            self.release, self.budget, self.seed = release, _record["planned_runs"], _record["seed"]
            self.kind, self.method = _record["kind"], _record["method"]
            self.evidence_mode = _record["evidence_mode"]
            self._init_runtime()
            return
        if evidence_mode not in ("final", "development"):
            raise ValueError(f"unknown evidence_mode {evidence_mode!r}")
        if evidence_mode == "final":
            require_final_evidence(kind)
        self.evidence_mode = evidence_mode
        self.release = release or Release.build(policy, overrides)
        if release is not None and overrides:
            self.release = release.with_overrides(overrides)
        if kind == "nominal_estimation" and not self.release.is_nominal:
            raise ValueError("a nominal estimation campaign cannot use simulation overrides; "
                             "use kind='sensitivity' for variants")
        if budget <= 0:
            raise ValueError("budget (planned runs) must be positive")
        self.budget, self.seed, self.kind, self.method = int(budget), int(seed), kind, method
        self._init_runtime()
        store.create_campaign({
            "campaign_id": name, "kind": kind, "method": method, "seed": self.seed,
            "planned_runs": self.budget, "release_id": self.release.release_id,
            "runtime_id": runtime_id(), "exposure_model_id": self.release.exposure_model_id,
            "protocol_id": protocol_id, "case_source": case_source,
            "overrides": self.release.manifest()["overrides"],
            "evidence_mode": evidence_mode,
            "provenance": provenance(self.release, evidence_mode)})

    def _init_runtime(self) -> None:
        if self.release.policy_sha256 is None:
            raise ValueError("the release has no policy hash")
        from .provenance import policy_hash
        if self.policy is not None and policy_hash(self.policy) != self.release.policy_sha256:
            raise ValueError("the policy object does not match the release's policy hash")
        self.params = self.release.sim_params
        self.references = References(self.release)

    @classmethod
    def resume(cls, name: str, store: Store, policy, release: Release | None = None
               ) -> "Campaign":
        """Continue an incomplete campaign under the identical release and runtime."""
        rec = store.get_campaign(name)
        if rec is None:
            raise LookupError(f"no campaign {name!r}")
        if rec["status"] == "COMPLETE":
            raise ValueError(f"campaign {name!r} is COMPLETE; it cannot be extended")
        release = release or Release.build(policy)
        if rec["overrides"]:
            release = release.with_overrides(rec["overrides"])
        if release.release_id != rec["release_id"]:
            raise ValueError(f"campaign {name!r} was created under release "
                             f"{rec['release_id'][:12]}, the current one is "
                             f"{release.release_id[:12]}: it cannot be resumed")
        if runtime_id() != rec["runtime_id"]:
            raise ValueError(f"campaign {name!r} was created under a different runtime "
                             "(Python, platform or result-relevant package versions)")
        if rec["evidence_mode"] == "final":
            require_final_evidence(rec["kind"])
        n = store.n_runs(name)
        if n != rec["completed_runs"] or store.max_run_idx(name) != n - 1:
            raise ValueError(f"campaign {name!r} is inconsistent: {n} stored runs, "
                             f"{rec['completed_runs']} recorded, run indices not 0..n-1")
        camp = cls(name, store, policy, rec["planned_runs"], release=release, _record=rec)
        store.update_campaign(name, resumed=rec["resumed"] + 1, status="RUNNING",
                              stop_reason=None)
        return camp

    # ------------------------------------------------------------ state
    @property
    def record(self) -> dict:
        return self.store.get_campaign(self.name)

    @property
    def used(self) -> int:
        return self.store.n_runs(self.name)

    @property
    def remaining(self) -> int:
        return self.budget - self.used

    def case_rng(self, run_idx: int, purpose: str = "case") -> np.random.Generator:
        """Random stream for choosing case `run_idx` (search baselines, estimation)."""
        return stream(self.seed, run_idx, purpose)

    # ------------------------------------------------------------ execution
    def run(self, cases: list[dict]) -> list[dict]:
        """Validate, simulate and store cases. Stops silently when the budget is exhausted.
        Any exception marks the campaign FAILED and is re-raised."""
        if self.record["status"] in ("COMPLETE", "FAILED"):
            raise ValueError(f"campaign {self.name!r} is {self.record['status']}")
        rows, start = [], self.used
        try:
            for case in cases:
                if start + len(rows) >= self.budget:
                    break
                rows.append(self._simulate_row(validate_case(case, self.release.odd),
                                               start + len(rows)))
            self.store.insert(rows)
            self.store.update_campaign(self.name, status="RUNNING",
                                       completed_runs=start + len(rows))
        except Exception:
            self.store.update_campaign(self.name, status="FAILED",
                                       stop_reason="exception during run()")
            raise
        return rows

    def _simulate_row(self, clean: dict, run_idx: int) -> dict:
        seed = derive_seed(self.seed, run_idx, "sim")
        metrics, _ = simulate(clean, self.policy, seed, self.params)
        return {"campaign": self.name, "run_idx": run_idx, "seed": seed, **clean,
                "initial_gap_m": clean["headway"] * clean["ego_speed"],
                **driver_attributes(clean["driver_state"], self.release.odd),
                **self.references.evaluate(clean), **metrics}

    def finish(self, stop_reason: str = "completed") -> dict:
        """Mark the campaign COMPLETE (fixed-plan kinds need every planned run) and record
        its data hash. Returns the final record."""
        n = self.used
        if self.kind in FIXED_PLAN_KINDS and n != self.budget:
            self.store.update_campaign(self.name, status="FAILED",
                                       stop_reason=f"incomplete: {n} of {self.budget} runs")
            raise ValueError(f"campaign {self.name!r} planned {self.budget} runs but has {n}; "
                             "it is marked FAILED and cannot be release evidence")
        self.store.update_campaign(self.name, status="COMPLETE", completed_runs=n,
                                   stop_reason=stop_reason,
                                   data_sha256=self.store.data_hash(self.name))
        return self.record

    def fail(self, reason: str) -> None:
        self.store.update_campaign(self.name, status="FAILED", stop_reason=reason)


def random_case(rng: np.random.Generator, odd=None) -> dict:
    """A case drawn uniformly from the ODD (search baselines; not exposure-weighted)."""
    from .config import CONTINUOUS, load_odd, param_range, scenario_param
    p = (odd or load_odd())["parameters"]
    case = {k: str(rng.choice(list(p[k]["values"]))) for k in ("scenario", "driver_state")}
    for k in (CONTINUOUS[0], CONTINUOUS[1], scenario_param(case["scenario"]), CONTINUOUS[2]):
        lo, hi = param_range(k, case["scenario"], odd)
        case[k] = float(rng.uniform(lo, hi))
    return case
