"""Hand-back diagnostics, findings and the command-line entry points (small smoke runs)."""
import json

import pytest

import avval.cli as cli
from avval.baselines import run_strategy
from avval.campaign import Campaign
from avval.diagnostics import REASONS, diagnose, write_diagnostics
from avval.estimation import run_estimation


@pytest.fixture
def cli_env(store, policy, monkeypatch):
    import avval.store as store_mod
    real = store_mod.Store
    monkeypatch.setattr(store_mod, "Store", lambda *a, **k: real(*a, **k) if a or k else store)
    monkeypatch.setattr("avval.policy.LearnedACC.load", classmethod(lambda cls: policy))
    return store


def test_diagnostics_decompose_hazardous_runs_without_handback(store, policy, tmp_path):
    run_strategy("boundary", Campaign("diag", store, policy, 120, seed=1, method="boundary"))
    d = diagnose(store, "diag", policy)
    assert set(d["reason"]) <= set(REASONS)
    if len(d):
        lb = d[d.reason == "req_below_threshold_lead_braking"]
        assert (lb["required_decel"] <= lb["req_threshold"]).all() and (lb["a_lead"] < 0).all()
    assert "Hand-back diagnostics" in open(write_diagnostics(store, "diag", policy),
                                           encoding="utf-8").read()


def test_cli_estimate_baseline_findings_and_package(cli_env, policy, tmp_path, capsys):
    cli.main(["estimate", "--n", "30", "--seed", "0"])
    out = capsys.readouterr().out
    assert "decision:" in out and "development run" in out
    assert cli_env.get_campaign("estimate")["status"] == "COMPLETE"
    assert cli_env.get_campaign("estimate")["evidence_mode"] == "development"
    cli.main(["baseline", "--method", "cem", "--budget", "40", "--seed", "3"])
    assert cli_env.get_campaign("cem_s3")["status"] == "COMPLETE"
    cli.main(["findings", "--estimation", "estimate", "cem_s3"])
    assert "Margin erosion" in (tmp_path / "findings.md").read_text(encoding="utf-8")
    cli.main(["package", "--out", str(tmp_path / "pkg"), "--require", "estimation"])
    with pytest.raises(SystemExit) as e:
        cli.main(["verify-package", str(tmp_path / "pkg")])
    assert e.value.code == 0


def test_findings_refuse_campaigns_of_another_release(cli_env, policy):
    from avval.config import Release
    from avval.findings import write_findings
    run_estimation(cli_env, policy, 20, seed=0)
    run_strategy("random", Campaign("r", cli_env, policy, 20, method="random"))
    cli_env.update_campaign("r", release_id="f" * 64)
    with pytest.raises(ValueError, match="r: .*different release"):
        write_findings(cli_env, "estimate", ["r"], Release.build(policy))


def test_every_campaign_named_report_checks_release_runtime_data_and_mode(cli_env, policy):
    """Diagnostics and the estimation report apply the same campaign checks as findings."""
    from avval.config import Release
    from avval.report import write_estimation_report
    rel = Release.build(policy)
    run_estimation(cli_env, policy, 20, seed=0)
    run_strategy("random", Campaign("r", cli_env, policy, 20, method="random"))
    with pytest.raises(ValueError, match="development run"):  # final needs final campaigns
        diagnose(cli_env, "r", policy, rel, final=True)
    with pytest.raises(ValueError, match="development run"):
        write_estimation_report(cli_env, "estimate", rel, final=True)
    cli_env.con.execute("UPDATE all_runs SET min_ttc = 0.5 WHERE campaign = 'r' AND run_idx = 0")
    cli_env._drop_snapshots("r")
    with pytest.raises(ValueError, match="data hash"):
        diagnose(cli_env, "r", policy, rel)
    cli_env.update_campaign("estimate", runtime_id="0" * 64)
    with pytest.raises(ValueError, match="different runtime"):
        write_estimation_report(cli_env, "estimate", rel, final=True)
    text = open(write_estimation_report(cli_env, "estimate", rel), encoding="utf-8").read()
    assert "not eligible release evidence" in text  # development: labelled, no verdict
    cli_env.update_campaign("r", release_id="f" * 64)
    with pytest.raises(ValueError, match="different release"):
        diagnose(cli_env, "r", policy, rel)


# ---- final evidence (item 18) ---------------------------------------------------------------
def test_final_evidence_needs_a_clean_committed_tree(store, policy, monkeypatch):
    monkeypatch.setattr("avval.provenance.final_evidence_problems",
                        lambda: ["uncommitted change: M avval/sim.py"])
    for kind in ("nominal_estimation", "search", "holdout_evaluation", "sensitivity"):
        with pytest.raises(RuntimeError, match="final-evidence campaign refused"):
            Campaign(f"f_{kind}", store, policy, 5, kind=kind, evidence_mode="final")
    camp = Campaign("dev", store, policy, 5)  # development runs stay possible
    assert camp.record["evidence_mode"] == "development"
    monkeypatch.setattr("avval.provenance.final_evidence_problems", lambda: [])
    fin = Campaign("fin", store, policy, 5, kind="nominal_estimation", evidence_mode="final")
    assert fin.record["evidence_mode"] == "final"


def test_development_estimation_is_never_final_evidence(store, policy, monkeypatch):
    from avval.estimation import find_estimation, release_verdict
    run_estimation(store, policy, 20, seed=0)
    assert find_estimation(store, policy) == "estimate"
    assert find_estimation(store, policy, final=True) is None
    with pytest.raises(LookupError):
        release_verdict(store, policy, final=True)


def test_cli_final_refuses_a_dirty_tree(cli_env, monkeypatch):
    monkeypatch.setattr("avval.provenance.final_evidence_problems",
                        lambda: ["uncommitted change: M config/sim.yaml"])
    with pytest.raises(SystemExit) as e:
        cli.main(["--final", "estimate", "--n", "10", "--seed", "0"])
    assert "final evidence refused" in str(e.value)
    with pytest.raises(SystemExit, match="development command"):
        cli.main(["--final", "baseline", "--method", "random"])


def test_source_tree_check_sees_tracked_and_untracked_changes(monkeypatch):
    import subprocess
    from avval import provenance

    class R:
        def __init__(self, out, code=0):
            self.stdout, self.returncode = out, code

    def fake(args, **kw):
        if args[1] == "rev-parse":
            return R("abc\n")
        if "--untracked-files=no" in args:
            return R(" M avval/sim.py\n")
        return R("?? avval/new_module.py\n")
    monkeypatch.setattr(subprocess, "run", fake)
    problems = provenance.source_tree_problems()
    assert any("avval/sim.py" in p for p in problems)
    assert any("untracked source file: avval/new_module.py" in p for p in problems)


def test_final_mode_uses_a_release_addressed_directory(policy):
    from avval.config import Release
    rid = Release.build(policy).release_id
    d = cli.final_dir(rid)
    assert d.name == f"final_{rid[:16]}" and d.parent.name == "results"


# ---- policy handling (item 22) ---------------------------------------------------------------
def test_train_never_silently_replaces_the_release_policy(tmp_path, monkeypatch):
    import avval.policy as pol
    target = tmp_path / "policy.json"
    target.write_text("{}")
    monkeypatch.setattr(pol, "POLICY_PATH", target)
    with pytest.raises(SystemExit, match="policy-verify"):
        cli.main(["train"])
    assert target.read_text() == "{}"


def test_policy_verify_compares_without_overwriting(policy, tmp_path, monkeypatch, capsys):
    import avval.policy as pol
    target, meta = tmp_path / "policy.json", tmp_path / "policy_meta.json"
    policy.save(target)
    before = target.read_bytes()
    monkeypatch.setattr(pol, "POLICY_PATH", target)
    monkeypatch.setattr(pol, "POLICY_META_PATH", meta)
    monkeypatch.setattr("avval.provenance.POLICY_PATH", target)
    with pytest.raises(SystemExit) as e:
        cli.main(["policy-verify", "--write-meta"])
    assert e.value.code == 0 and target.read_bytes() == before
    m = json.loads(meta.read_text())
    assert m["reproduced"] and m["committed_policy_sha256"] == m["retrained_policy_sha256"]


# ---- agent infrastructure retry (item 20) ---------------------------------------------------
class _FakeAgent:
    """Stand-in for ValidationAgent: `plan` maps attempt number to behaviour."""
    plan: dict = {}
    calls: list = []

    def __init__(self, camp, **kw):
        import avval.agent as agent_mod
        self.camp, self.kw, self.transcript = camp, kw, []
        self.usage = agent_mod.Usage(kw["model"])

    from avval.agent import ValidationAgent as _Real
    record_client_provenance = _Real.record_client_provenance  # the real one, not patched
    del _Real

    @property
    def campaign(self):
        return self.camp

    @property
    def model(self):
        return self.kw["model"]

    def run(self):
        import avval.agent as agent_mod
        n = len(_FakeAgent.calls)
        _FakeAgent.calls.append(self.camp.name)
        what = _FakeAgent.plan.get(n, "ok")
        if what == "runs_then_fail":
            self.camp.run([dict(scenario="cut_in", ego_speed=30.0, closing_speed=3.0,
                                headway=1.5, friction=1.0, driver_state="attentive")])
            raise ConnectionError("network down after a run")
        if what == "infra":
            raise ConnectionError("network down")
        if what == "bug":
            raise ValueError("a bug")
        self.camp.finish(what if what != "ok" else "max_turns")
        return agent_mod.AgentResult(False, 1, None, [], self.usage.summary(), "max_turns")


@pytest.fixture
def fake_agent(cli_env, monkeypatch):
    import avval.agent as agent_mod
    monkeypatch.setattr(agent_mod, "ValidationAgent", _FakeAgent)
    _FakeAgent.calls = []
    return cli_env


def test_infrastructure_failure_before_any_run_is_retried_once(fake_agent):
    _FakeAgent.plan = {0: "infra"}
    cli.main(["agent", "--no-protocol", "--first-seed", "3"])
    assert _FakeAgent.calls == ["agent_s3", "agent_s3_retry1"]
    first, retry = fake_agent.get_campaign("agent_s3"), fake_agent.get_campaign("agent_s3_retry1")
    assert first["status"] == "FAILED" and first["stop_reason"].startswith("infrastructure")
    assert retry["status"] == "COMPLETE" and retry["seed"] == 3


def test_at_most_one_retry(fake_agent):
    _FakeAgent.plan = {0: "infra", 1: "infra"}
    with pytest.raises(ConnectionError):
        cli.main(["agent", "--no-protocol", "--first-seed", "4"])
    assert _FakeAgent.calls == ["agent_s4", "agent_s4_retry1"]


@pytest.mark.parametrize("what", ["runs_then_fail", "bug"])
def test_no_retry_after_a_run_or_for_other_errors(fake_agent, what):
    _FakeAgent.plan = {0: what}
    with pytest.raises((ConnectionError, ValueError)):
        cli.main(["agent", "--no-protocol", "--first-seed", "5"])
    assert _FakeAgent.calls == ["agent_s5"]
    assert not fake_agent.get_campaign("agent_s5")["stop_reason"].startswith("infrastructure")


def test_protocol_endings_are_never_retried(fake_agent):
    _FakeAgent.plan = {0: "cost_cap"}
    cli.main(["agent", "--no-protocol", "--first-seed", "6"])
    assert _FakeAgent.calls == ["agent_s6"]
    assert fake_agent.get_campaign("agent_s6")["stop_reason"] == "cost_cap"


def test_cli_release_and_db_info(cli_env, policy, capsys):
    cli.main(["release"])
    out = json.loads(capsys.readouterr().out)
    assert len(out["release_id"]) == 64
    run_estimation(cli_env, policy, 5, seed=1, name="tiny")
    cli.main(["db-info"])
    assert "tiny" in capsys.readouterr().out


def test_cli_benchmark_run_requires_a_frozen_protocol(cli_env):
    with pytest.raises(FileNotFoundError):
        cli.main(["benchmark-run", "--strategy", "random", "--count", "1"])


def test_cli_env_check_reports_lock_status(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["env-check"])
    assert e.value.code in (0, 1)
    assert "runtime_id" in capsys.readouterr().out


def test_selection_from_the_benchmark_refuses_an_incomplete_protocol(cli_env, policy):
    from avval.benchmark import freeze_protocol
    from avval.config import Release
    freeze_protocol(Release.build(policy))  # nothing has run under it
    with pytest.raises(SystemExit, match="incomplete"):
        cli.main(["freeze-predicates", "--from-benchmark"])
    with pytest.raises(SystemExit, match="incomplete"):
        cli.main(["findings", "--from-benchmark"])


# ---- rehearsal mode (v4 review, Part G) -----------------------------------------------------
def _fresh_config(monkeypatch, rehearsal: bool):
    import avval.config as cfg
    if rehearsal:
        monkeypatch.setenv("AVVAL_REHEARSAL", "1")
    else:
        monkeypatch.delenv("AVVAL_REHEARSAL", raising=False)
    cfg.load_file.cache_clear()


def test_rehearsal_patches_only_protocol_sizes_never_the_release(policy, monkeypatch):
    import avval.config as cfg
    from avval.config import Release
    _fresh_config(monkeypatch, False)
    nominal_release = Release.build(policy).release_id
    bench, sens = cfg.load_file("benchmark"), cfg.load_file("sensitivity")
    try:
        _fresh_config(monkeypatch, True)
        assert Release.build(policy).release_id == nominal_release  # release files untouched
        rb, rs = cfg.load_file("benchmark"), cfg.load_file("sensitivity")
        assert rb["budget"] == 30 and list(rb["seeds"]["agent"]) == [0]
        assert rb["agent"]["cost_cap_usd_per_seed"] <= 0.5 and rb["agent"]["model"] == \
            bench["agent"]["model"]
        assert rs["n"] == 100 and rs["factors"] == sens["factors"]
        assert cfg.load_file("discovery") is not None  # never patched
    finally:
        _fresh_config(monkeypatch, False)


def test_final_evidence_is_refused_in_rehearsal_mode(monkeypatch):
    from avval.provenance import final_evidence_problems
    monkeypatch.setenv("AVVAL_REHEARSAL", "1")
    assert any("rehearsal" in p for p in final_evidence_problems())
    with pytest.raises(SystemExit, match="rehearsal"):
        cli.main(["--final", "release"])
    monkeypatch.delenv("AVVAL_REHEARSAL")
    with pytest.raises(SystemExit, match="rehearsal"):
        cli.main(["--final", "--rehearsal", "release"])
