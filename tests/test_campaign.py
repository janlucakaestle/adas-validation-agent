"""Campaign identity, deterministic random streams, resume and lifecycle."""
import pytest

from avval.campaign import Campaign, derive_seed
from avval.config import Release
from avval.estimation import eligibility, find_estimation, resume_estimation, run_estimation, run_planned
from avval.store import CampaignExistsError


def test_derived_seeds_are_stable_and_distinct():
    assert derive_seed(3, 7, "sim") == derive_seed(3, 7, "sim")
    seeds = {derive_seed(s, i, p) for s in range(3) for i in range(50) for p in ("sim", "case")}
    assert len(seeds) == 300 and all(0 <= s < 2 ** 63 for s in seeds)


def test_campaign_identity_is_unique(store, policy):
    Campaign("same", store, policy, 5)
    with pytest.raises(CampaignExistsError):
        Campaign("same", store, policy, 5)


def test_runs_are_unique_per_campaign(store, policy):
    import duckdb
    camp = Campaign("u", store, policy, 5)
    rows = camp.run([dict(scenario="cut_in", ego_speed=30.0, closing_speed=3.0, headway=1.5,
                          friction=1.0, driver_state="attentive")])
    with pytest.raises(duckdb.ConstraintException):
        store.insert(rows)


def test_resume_reproduces_the_uninterrupted_campaign_exactly(store, policy, monkeypatch):
    """A crash part-way through an estimation, then resume: the stored runs (cases, seeds,
    outcomes) are identical to an uninterrupted campaign; no stream restarts or repeats."""
    import avval.estimation as est
    run_estimation(store, policy, 30, seed=4, name="whole")
    monkeypatch.setattr(est, "CHUNK", 10)
    camp = Campaign("crashed", store, policy, 30, seed=4, method="estimate",
                    kind="nominal_estimation", case_source="exposure")
    real = Campaign._simulate_row

    def crashing(self, clean, run_idx):
        if run_idx == 15:
            raise RuntimeError("simulated crash")
        return real(self, clean, run_idx)

    monkeypatch.setattr(Campaign, "_simulate_row", crashing)
    with pytest.raises(RuntimeError):
        run_planned(camp)
    monkeypatch.setattr(Campaign, "_simulate_row", real)
    assert store.get_campaign("crashed")["status"] == "FAILED"
    assert store.n_runs("crashed") == 10
    resume_estimation(store, policy, "crashed")
    a = store.campaign_df("whole").drop(columns="campaign")
    b = store.campaign_df("crashed").drop(columns="campaign")
    assert a.equals(b)
    assert store.get_campaign("crashed")["status"] == "COMPLETE"
    assert store.get_campaign("crashed")["resumed"] == 1


def test_an_incomplete_campaign_is_never_release_evidence(store, policy):
    camp = Campaign("partial", store, policy, 50, method="estimate", kind="nominal_estimation",
                    case_source="exposure")
    camp.run([camp.release.exposure_model.sample(camp.case_rng(i)) for i in range(20)])
    assert find_estimation(store, policy) is None            # RUNNING
    with pytest.raises(ValueError, match="planned 50 runs but has 20"):
        camp.finish()
    rec = store.get_campaign("partial")
    assert rec["status"] == "FAILED" and find_estimation(store, policy) is None
    assert any("status is FAILED" in p for p in eligibility(store, rec, Release.build(policy)))


def test_a_complete_campaign_cannot_be_extended(store, policy):
    run_estimation(store, policy, 5, seed=1, name="done")
    with pytest.raises(ValueError, match="COMPLETE"):
        Campaign.resume("done", store, policy)


def test_resume_under_a_different_release_is_refused(store, policy):
    from avval.policy import train_policy
    camp = Campaign("r", store, policy, 10, method="estimate", kind="nominal_estimation",
                    case_source="exposure")
    camp.fail("stopped")
    other, _ = train_policy(n_samples=2_000, seed=1)
    with pytest.raises(ValueError, match="cannot be resumed"):
        Campaign.resume("r", store, other)


def test_search_budget_is_enforced_and_lifecycle_recorded(store, policy):
    from avval.campaign import random_case
    camp = Campaign("t", store, policy, budget=10)
    assert store.get_campaign("t")["status"] == "CREATED"
    camp.run([random_case(camp.case_rng(i)) for i in range(25)])
    assert store.n_runs("t") == 10 and camp.remaining == 0
    rec = camp.finish("budget spent")
    assert rec["status"] == "COMPLETE" and rec["completed_runs"] == 10
    assert rec["data_sha256"] == store.data_hash("t")
