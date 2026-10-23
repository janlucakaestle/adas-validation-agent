"""Historical evidence combines only when compatibility is machine-verified; packages verify."""

import pytest

from avval.compat import is_compatible, verify_compatibility
from avval.config import Release
from avval.estimation import run_estimation


@pytest.fixture
def est(store, policy):
    run_estimation(store, policy, 25, seed=2, name="est")
    return store


def test_same_release_is_compatible(est, policy):
    ok, why = is_compatible(est, "est", Release.build(policy))
    assert ok and "same release" in why


def test_incompatible_release_is_refused_without_verification(est, policy):
    target = Release.build(policy, overrides={"sim": {"monitor": {"tor_ttc_s": 2.5}}})
    ok, why = is_compatible(est, "est", target)
    assert not ok and "no verified compatibility declaration" in why


def test_replay_verification_proves_or_refutes_compatibility(est, policy):
    rel = Release.build(policy)
    # Same simulation semantics under a different release identity (e.g. a code change that
    # does not touch the simulation): the replay reproduces every column -> compatible.
    relabelled = Release(rel.configs, rel.policy_sha256, "0" * 64)
    est.update_campaign("est", release_id="f" * 64)  # recorded under "another" release
    res = verify_compatibility(est, "est", relabelled, policy)
    assert res["verified"] and res["runs_checked"] == 25
    assert is_compatible(est, "est", relabelled)[0]
    # A semantic change (a different monitor threshold) is caught by the replay.
    changed = rel.with_overrides({"sim": {"monitor": {"tor_ttc_s": 3.0}}})
    bad = verify_compatibility(est, "est", changed, policy, write=False)
    assert not bad["verified"] and bad["mismatching_runs"] > 0


def test_tampered_data_invalidates_a_declaration(est, policy):
    rel = Release.build(policy)
    relabelled = Release(rel.configs, rel.policy_sha256, "0" * 64)
    est.update_campaign("est", release_id="f" * 64)
    verify_compatibility(est, "est", relabelled, policy)
    est.con.execute("UPDATE all_runs SET min_ttc = 0.1 WHERE campaign = 'est' AND run_idx = 0")
    assert not is_compatible(est, "est", relabelled)[0]


def test_rerender_script_refuses_incompatible_campaigns(est, policy, monkeypatch, capsys):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import rerender_agent_reports as rr
    monkeypatch.setattr(rr, "Store", lambda: est)
    monkeypatch.setattr(rr.LearnedACC, "load", classmethod(lambda cls: policy))
    from avval.campaign import Campaign
    Campaign("old_agent", est, policy, 5, method="agent").finish()
    est.update_campaign("old_agent", release_id="a" * 64)
    assert rr.main(["old_agent"]) == 1
    assert "REFUSED old_agent" in capsys.readouterr().err
