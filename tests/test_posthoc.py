"""Post-hoc re-evaluation of submitted predicates on a held-out campaign."""
import avval.posthoc as posthoc
from avval.baselines import random_search
from avval.campaign import Campaign

REPORT = """# Report

### TC-01: close cut-ins
Predicate: `scenario = 'cut_in' AND headway <= 0.5`

### TC-02: braking lead
Predicate: `scenario = 'lead_brake'`
"""


def test_posthoc_parses_reports_and_compares_with_reference(store, policy, tmp_path,
                                                            monkeypatch):
    monkeypatch.setattr(posthoc, "RESULTS_DIR", tmp_path)
    (tmp_path / "report_agent_s0.md").write_text(REPORT, encoding="utf-8")
    random_search(Campaign("holdout", store, policy, 60, seed=3, method="random"))

    assert posthoc.submitted_predicates("agent_s0") == [
        ("TC-01", "scenario = 'cut_in' AND headway <= 0.5"), ("TC-02", "scenario = 'lead_brake'")]
    rows = posthoc.evaluate(store, ["agent_s0"], holdout="holdout")
    ref, tc1, tc2 = rows
    assert ref["source"] == "reference" and ref["runs_inside"] + ref["runs_outside"] == 60
    assert tc2["relation_to_reference"].startswith("disjoint")
    assert tc2["overlap_runs"] == 0
    if tc1["overlap_runs"]:                     # headway <= 0.5 vs the reference's 0.73
        assert not tc1["relation_to_reference"].startswith("looser")
    text = open(posthoc.write_posthoc(store, ["agent_s0"], holdout="holdout"),
                encoding="utf-8").read()
    assert "TC-02" in text and "Clopper-Pearson" in text


def test_findings_are_written_from_stored_campaigns(store, policy, tmp_path, monkeypatch):
    import avval.findings as findings
    monkeypatch.setattr(findings, "RESULTS_DIR", tmp_path)
    for name in ("random", "random_s0", "grid_s0"):
        random_search(Campaign(name, store, policy, 20, seed=1, method="random"))
    random_search(Campaign("estimate", store, policy, 20, seed=2, method="estimate"))
    text = open(findings.write_findings(store), encoding="utf-8").read()
    assert "Across 2 benchmark campaigns (40 runs" in text
    assert "| `random` | 20 |" in text and "95th percentile of raw" in text


def test_posthoc_lists_campaigns_without_a_report(store, policy, tmp_path, monkeypatch):
    """A seed stopped before submitting (e.g. by its cost cap) is listed, not skipped silently."""
    monkeypatch.setattr(posthoc, "RESULTS_DIR", tmp_path)
    random_search(Campaign("holdout", store, policy, 30, seed=3, method="random"))
    assert posthoc.submitted_predicates("agent_s9") == []
    text = open(posthoc.write_posthoc(store, ["agent_s9"], holdout="holdout"),
                encoding="utf-8").read()
    assert "Campaigns with no submitted predicate: `agent_s9`." in text
