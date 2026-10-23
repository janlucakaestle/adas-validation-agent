"""Evidence packages: built from manifests and IDs, bound to one release, deeply verified."""
import json

import pytest

import avval.benchmark as bm
import avval.holdout as ho
import avval.sensitivity as sens
from avval.agent import ValidationAgent
from avval.baselines import run_strategy
from avval.benchmark import campaign_name, freeze_protocol, write_benchmark
from avval.campaign import Campaign
from avval.config import Release
from avval.estimation import run_estimation
from avval.frozen import canonical_json, content_hash, sha256_text, thaw
from avval.package import build_package, verify_package
from avval.provenance import sha256_file
from avval.report import write_estimation_report

CUT_IN = dict(scenario="cut_in", ego_speed=30.0, closing_speed=8.0, headway=0.4, friction=1.0,
              driver_state="attentive")
PRED = "scenario = 'cut_in' AND headway < 0.5"


def _agent(store, policy, pid, tmp_path):
    camp = Campaign("agent_s0", store, policy, 30, seed=0, method="agent", protocol_id=pid)
    agent = ValidationAgent(camp, client=object())
    agent.call_tool("run_scenarios", {"cases": [CUT_IN] * 4 + [{**CUT_IN, "headway": 1.8}] * 2})
    sql = f"SELECT count(*) AS n FROM runs WHERE {PRED}"
    t = json.loads(agent.call_tool("test_predicate", {"where": PRED}))
    q = json.loads(agent.call_tool("query_results", {"sql": sql}))
    out = json.loads(agent.call_tool("submit_report", {"summary": "s", "triggering_conditions": [{
        "description": "d", "predicate": PRED, "predicate_test_id": t["test_id"],
        "evidence_sql": sql, "evidence_query_id": q["query_id"]}]}))
    assert out["accepted"]
    (tmp_path / "usage_agent_s0.json").write_text(json.dumps({"models_returned": ["m-1"]}))
    (tmp_path / "transcript_agent_s0.json").write_text(json.dumps(agent.transcript))


@pytest.fixture
def world(store, policy, monkeypatch, tmp_path):
    """A small but complete development evidence set of one release."""
    rel = Release.build(policy)
    proto = thaw(bm.load_protocol())
    proto.update(budget=30, strategies=["agent", "random"])
    proto["seeds"] = {"agent": [0], "baselines": {"first": 0, "count": 1}}
    proto["primary"]["bootstrap_draws"] = 200
    monkeypatch.setattr(bm, "load_protocol", lambda: proto)
    sp = sens.load_protocol()
    sp["factors"] = {"tor_ttc_s": sp["factors"]["tor_ttc_s"]}
    sp["designs"] = {"oat": {"points": 2}, "factorial2": {"factors": ["tor_ttc_s"]},
                     "lhs": {"samples": 1, "seed": 0}}
    sp["n"] = 12
    monkeypatch.setattr(sens, "load_protocol", lambda: sp)

    run_estimation(store, policy, 60, seed=0)
    write_estimation_report(store, "estimate", rel)
    m = freeze_protocol(rel)
    _agent(store, policy, m["protocol_id"], tmp_path)
    run_strategy("random", Campaign(campaign_name("random", 0), store, policy, 30, seed=0,
                                    method="random", protocol_id=m["protocol_id"]))
    write_benchmark(store, m)
    frozen = ho.freeze_predicates(store, ["agent_s0"], rel)
    hp = ho.freeze_holdout_protocol(store, frozen, rel, 60, seed=11)
    ho.run_holdout(store, policy, frozen, hp)
    ho.write_holdout(store, frozen, hp, "holdout", rel)
    sm = sens.freeze_protocol(rel)
    for d in ("oat", "factorial2", "lhs"):
        df = sens.run_sensitivity(policy, d, workers=1, manifest=sm, store=store)
        sens.write_sensitivity(df, d, 12, 0, sm["protocol_id"])
    return rel


def _rebless(out):
    """What an attacker would do after editing a file: re-hash it into MANIFEST.json."""
    m = json.loads((out / "MANIFEST.json").read_text())
    m["files"] = {k: sha256_file(out / k) for k in m["files"]}
    m.pop("package_sha256")
    m["package_sha256"] = content_hash(m)
    (out / "MANIFEST.json").write_text(json.dumps(m))
    return m


def test_package_builds_verifies_and_detects_every_tampering(store, world, tmp_path):
    import shutil
    out = tmp_path / "pkg"
    m = build_package(store, world, out, final=False)
    assert set(m["components"]) == {"estimation", "benchmark", "holdout", "sensitivity"}
    files = set(m["files"])
    assert {"runs/random_s0.parquet", "runs/agent_s0.parquet", "runs/holdout.parquet",
            "runs/estimate.parquet", "benchmark/benchmark_manifest.json",
            "benchmark/evidence_agent_s0.json", "holdout/holdout_protocol.json",
            "sensitivity/sensitivity_manifest.json", "estimation/acceptance.json"} <= files
    assert any(f.startswith("runs/sens_lhs_") for f in files)  # persisted variant data
    assert any(f.startswith("source/avval/") for f in files)
    assert verify_package(out) == []

    # a campaign relabelled to another release, re-blessed into the manifest
    p1 = tmp_path / "p1"
    shutil.copytree(out, p1)
    recs = json.loads((p1 / "campaigns.json").read_text())
    next(r for r in recs if r["campaign_id"] == "random_s0")["release_id"] = "f" * 64
    (p1 / "campaigns.json").write_text(json.dumps(recs))
    _rebless(p1)
    assert any("random_s0: recorded under release" in p for p in verify_package(p1))

    # forged evidence inside a bundle, with every hash recomputed and re-blessed
    p2 = tmp_path / "p2"
    shutil.copytree(out, p2)
    path = p2 / "benchmark" / "evidence_agent_s0.json"
    b = json.loads(path.read_text())
    c = b["conditions"][0]
    c["evidence"]["rows"] = [{"n": 999}]
    c["evidence"]["rows_sha256"] = content_hash(c["evidence"]["rows"])
    c.pop("condition_sha256")
    c["condition_sha256"] = content_hash(c)
    body = {k: v for k, v in b.items() if k != "bundle_sha256"}
    b["bundle_sha256"] = sha256_text(canonical_json(body))
    path.write_text(json.dumps(b))
    _rebless(p2)
    assert any("evidence query is not the ledger entry" in p or "does not reproduce" in p
               for p in verify_package(p2))

    # development runs dressed up as a final package
    p3 = tmp_path / "p3"
    shutil.copytree(out, p3)
    mm = json.loads((p3 / "MANIFEST.json").read_text())
    mm["final"] = True
    (p3 / "MANIFEST.json").write_text(json.dumps(mm))
    _rebless(p3)
    assert any("development run inside a final package" in p for p in verify_package(p3))

    # an extra, unlisted file
    p4 = tmp_path / "p4"
    shutil.copytree(out, p4)
    (p4 / "runs" / "extra.parquet").write_bytes(b"x")
    assert any("unlisted file" in p for p in verify_package(p4))


def test_package_construction_refuses_foreign_or_stale_inputs(store, world, tmp_path):
    other = Release(world.configs, world.policy_sha256, "0" * 64)  # another (nominal) release
    with pytest.raises(ValueError, match="package refused") as e:
        build_package(store, other, tmp_path / "pkg", final=False)
    assert "release" in str(e.value)
    with pytest.raises(ValueError, match="package refused"):  # development runs, final package
        build_package(store, world, tmp_path / "pkg", final=True)
    (tmp_path / "findings.md").write_text("# findings of release deadbeefdeadbeef\n")
    (tmp_path.parent / "legacy_report.md").write_text("legacy v0.2 report")  # outside the dir
    with pytest.raises(ValueError, match="findings.md does not carry the ID"):
        build_package(store, world, tmp_path / "pkg", final=False)
    (tmp_path / "findings.md").unlink()
    (tmp_path / "report_estimate.md").write_text("stale report without the data hash")
    with pytest.raises(ValueError, match="report_estimate.md does not carry the ID"):
        build_package(store, world, tmp_path / "pkg", final=False)
