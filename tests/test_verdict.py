"""Never say GO without enough evidence."""
import avval.report as report_mod
from avval.campaign import Campaign
from avval.config import load_acceptance
from avval.evaluation import INSUFFICIENT, evaluate_acceptance, overall_verdict
from avval.report import write_estimation_report


def _r(status):
    return {"status": status}


def test_verdict_rules():
    assert overall_verdict([_r("PASS"), _r("PASS"), _r("INFO")]) == "GO"
    assert overall_verdict([_r("PASS"), _r(INSUFFICIENT), _r("INFO")]) == INSUFFICIENT
    assert overall_verdict([_r("FAIL"), _r(INSUFFICIENT)]) == "NO-GO"


def test_every_criterion_has_min_n():
    assert all("min_n" in c for c in load_acceptance()["criteria"])


# Gentle lead braking at long gaps with a phone-using driver: no collisions, no hand-back, so
# every rate criterion that has data passes, but there are no attentive runs at all.
SAFE = dict(scenario="lead_brake", ego_speed=25.0, headway=2.4, lead_decel=1.5, friction=1.0,
            driver_state="distracted")


def test_criterion_without_data_blocks_go(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)
    camp = Campaign("nodata", store, policy, 150)
    camp.run([SAFE] * 150)
    acc = {a["id"]: a for a in evaluate_acceptance(store, "nodata")}
    assert acc["AC-01"]["n"] == 0 and acc["AC-01"]["status"] == INSUFFICIENT
    assert "FAIL" not in {a["status"] for a in acc.values()}  # nothing fails...
    assert overall_verdict(list(acc.values())) == INSUFFICIENT  # ...but it is not a GO
    text = open(write_estimation_report(store, "nodata"), encoding="utf-8").read()
    assert "## Verdict: INSUFFICIENT EVIDENCE" in text and "AC-01 (no data)" in text


def test_pass_below_min_n_is_insufficient(store, policy):
    camp = Campaign("few", store, policy, 10)
    camp.run([{**SAFE, "driver_state": "attentive"}] * 10)
    ac01 = next(a for a in evaluate_acceptance(store, "few") if a["id"] == "AC-01")
    assert ac01["value"] == 0.0 and ac01["n"] == 10 < ac01["min_n"]
    assert ac01["status"] == INSUFFICIENT

