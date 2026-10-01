"""Traceability: every campaign and report records which policy, config and code produced it."""
import avval.report as report_mod
from avval.baselines import auto_report
from avval.campaign import Campaign
from avval.policy import train_policy
from avval.provenance import policy_hash, provenance, sha256_file


def test_provenance_fields_exist(policy):
    p = provenance(policy)
    assert set(p) == {"policy_sha256", "config_sha256", "code_sha256", "git_commit", "python",
                      "packages"}
    assert len(p["code_sha256"]) == 64
    assert len(p["policy_sha256"]) == 64
    assert {"odd.yaml", "acceptance.yaml"} <= set(p["config_sha256"])
    assert all(len(h) == 64 for h in p["config_sha256"].values())
    assert p["git_commit"] == "uncommitted" or len(p["git_commit"]) == 40
    assert set(p["packages"]) == {"numpy", "scikit-learn", "duckdb"}


def test_policy_hash_matches_saved_file(policy, tmp_path):
    path = tmp_path / "policy.json"
    policy.save(path)
    assert policy_hash(policy) == sha256_file(path)


def test_campaign_records_provenance(store, policy):
    Campaign("prov", store, policy, budget=7, seed=3, method="random")
    [reg] = store.campaign_info("prov")
    assert (reg["method"], reg["budget"], reg["seed"]) == ("random", 7, 3)
    assert reg["provenance"]["policy_sha256"] == policy_hash(policy)
    Campaign("prov", store, policy, budget=7)  # fresh campaign replaces the old record
    assert len(store.campaign_info("prov")) == 1


def test_retraining_changes_hash_in_report(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)
    retrained, _ = train_policy(n_samples=2_000, seed=1)
    texts = []
    for p in (policy, retrained):
        camp = Campaign("r", store, p, budget=2, method="random")
        texts.append(open(auto_report(camp, "random"), encoding="utf-8").read())
    for p, text in zip((policy, retrained), texts):
        assert "## Provenance" in text
        assert text.index("## Provenance") < text.index("## Summary")
        assert policy_hash(p) in text
        assert "odd.yaml" in text and "acceptance.yaml" in text
    assert policy_hash(policy) != policy_hash(retrained)
    assert policy_hash(retrained) not in texts[0]


def test_release_match_ignores_git_commit_but_not_code(policy):
    from avval.provenance import same_release
    p = provenance(policy)
    assert same_release(p, {**p, "git_commit": "0" * 40})       # docs-only commit
    assert not same_release(p, {**p, "code_sha256": "0" * 64})  # code changed
    assert not same_release(p, {**p, "config_sha256": {}})      # config changed


def test_text_hashes_ignore_line_endings(tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_bytes(bytes("x: 1\ny: 2\n", "ascii"))
    b.write_bytes(bytes("x: 1\ny: 2\n", "ascii").replace(bytes([10]), bytes([13, 10])))
    assert sha256_file(a, text=True) == sha256_file(b, text=True)
    assert sha256_file(a) != sha256_file(b)
