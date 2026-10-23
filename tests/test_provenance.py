"""Provenance: the identity recorded for a campaign is computed from exactly what it executes."""
import pytest

from avval.campaign import Campaign
from avval.config import (Release, load_acceptance, load_driver, load_exposure, load_odd,
                          load_reference, load_sim)
from avval.policy import train_policy
from avval.provenance import (RESULT_PACKAGES, policy_hash, runtime_fingerprint, runtime_id,
                              sha256_file)


@pytest.mark.parametrize("loader", [load_odd, load_driver, load_reference, load_exposure,
                                    load_acceptance, load_sim])
def test_cached_configuration_cannot_be_mutated(loader):
    cfg = loader()
    key = next(iter(cfg))
    with pytest.raises(TypeError):
        cfg[key] = "changed"
    with pytest.raises(TypeError):
        del cfg[key]
    nested = next(v for v in cfg.values() if hasattr(v, "keys") or isinstance(v, tuple))
    if hasattr(nested, "keys"):
        with pytest.raises(TypeError):
            nested[next(iter(nested))] = "changed"
    else:
        with pytest.raises((TypeError, AttributeError)):
            nested.append(1)


def test_mutation_attempt_cannot_create_a_provenance_mismatch(store, policy):
    """Whatever a caller tries on the cached config, the campaign executes with the release
    whose hash it records, and that release still equals the on-disk nominal one."""
    before = Release.build(policy).release_id
    with pytest.raises(TypeError):
        load_sim()["monitor"]["tor_required_decel_mps2"] = 99.0
    camp = Campaign("prov", store, policy, 5)
    assert camp.release.release_id == before == store.get_campaign("prov")["release_id"]
    assert camp.params.tor_req_decel == camp.release.sim["monitor"]["tor_required_decel_mps2"]


@pytest.mark.parametrize("patch", [
    {"sim": {"ego": {"accel_min_mps2": -3.0}}},                   # controller authority
    {"sim": {"monitor": {"tor_required_decel_mps2": 2.5}}},       # TOR thresholds
    {"sim": {"monitor": {"tor_ttc_s": 2.5}}},
    {"sim": {"time": {"dt_s": 0.025}}},                           # timestep
    {"sim": {"time": {"horizon_s": 25.0}}},                       # horizon
    {"sim": {"required_decel": {"margin_m": 1.0}}},               # safety margin
    {"sim": {"collision": {"contact_gap_m": 0.5}}},               # event definition
    {"sim": {"monitor": {"ttc_model": "constant_accel"}}},        # numerical/model choice
    {"driver": {"states": {"attentive": {"takeover_mean_s": 1.5}}}},  # driver model
    {"reference": {"ideal": {"decel_fraction_of_mu_g": 0.8}}},    # reference model
    {"exposure": {"factors": {"driver_state": {"weights": {"attentive": 0.7, "distracted": 0.3}}}}},
    {"acceptance": {"confidence": 0.9}},
])
def test_every_override_changes_the_release_identity(policy, patch):
    base = Release.build(policy)
    var = base.with_overrides(patch)
    assert var.release_id != base.release_id and not var.is_nominal
    assert var.manifest()["overrides"] == patch


def test_unknown_override_keys_are_rejected(policy):
    with pytest.raises(KeyError):
        Release.build(policy, overrides={"sim": {"monitor": {"tor_threshold": 2.0}}})
    with pytest.raises(KeyError):
        Release.build(policy, overrides={"simulator": {}})


def test_overridden_campaign_records_overrides_and_runs_them(store, policy):
    patch = {"sim": {"monitor": {"tor_required_decel_mps2": 0.5}}}
    camp = Campaign("var", store, policy, 3, kind="sensitivity", overrides=patch)
    rec = store.get_campaign("var")
    assert rec["overrides"] == patch and not rec["provenance"]["nominal"]
    assert camp.params.tor_req_decel == 0.5
    assert rec["release_id"] == camp.release.release_id != Release.build(policy).release_id


def test_nominal_estimation_refuses_overrides(store, policy):
    with pytest.raises(ValueError, match="cannot use simulation overrides"):
        Campaign("e", store, policy, 10, kind="nominal_estimation",
                 overrides={"sim": {"ego": {"accel_min_mps2": -3.0}}})


def test_policy_hash_matches_saved_file_and_changes_with_retraining(policy, tmp_path):
    path = tmp_path / "policy.json"
    policy.save(path)
    assert policy_hash(policy) == sha256_file(path)
    retrained, _ = train_policy(n_samples=2_000, seed=1)
    assert Release.build(retrained).release_id != Release.build(policy).release_id


def test_campaign_policy_must_match_its_release(store, policy):
    other, _ = train_policy(n_samples=2_000, seed=1)
    with pytest.raises(ValueError, match="policy"):
        Campaign("mismatch", store, other, 5, release=Release.build(policy))


def test_runtime_fingerprint_covers_material_dependencies():
    fp = runtime_fingerprint()
    for pkg in ("numpy", "scipy", "pandas", "pyarrow", "duckdb", "PyYAML", "scikit-learn",
                "matplotlib", "anthropic"):
        assert pkg in fp["packages"]
    assert set(RESULT_PACKAGES) <= set(fp["packages"])
    changed = {**fp, "packages": {**fp["packages"], "numpy": "0.0"}}
    assert runtime_id(changed) != runtime_id(fp)
    plot_only = {**fp, "packages": {**fp["packages"], "matplotlib": "0.0"}}
    assert runtime_id(plot_only) == runtime_id(fp)  # figures do not change stored results


def test_release_id_ignores_git_and_file_bytes_but_not_parsed_content(policy, tmp_path):
    rel = Release.build(policy)
    assert rel.release_id == Release.build(policy).release_id  # deterministic
    assert "git_commit" not in rel.manifest()


def test_text_hashes_ignore_line_endings(tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_bytes(bytes("x: 1\ny: 2\n", "ascii"))
    b.write_bytes(bytes("x: 1\ny: 2\n", "ascii").replace(bytes([10]), bytes([13, 10])))
    assert sha256_file(a, text=True) == sha256_file(b, text=True)
    assert sha256_file(a) != sha256_file(b)


def test_old_config_schema_is_refused(tmp_path, monkeypatch):
    import avval.config as cfg
    (tmp_path / "sim.yaml").write_text("time: {dt_s: 0.05}\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    cfg.load_file.cache_clear()
    try:
        with pytest.raises(ValueError, match="schema"):
            cfg.load_file("sim")
    finally:
        cfg.load_file.cache_clear()
