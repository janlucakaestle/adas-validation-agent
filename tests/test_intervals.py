"""Confidence intervals on acceptance criteria."""
import duckdb
import numpy as np
import pytest

import avval.report as report_mod
from avval.campaign import Campaign
from avval.evaluation import (INSUFFICIENT, NO_FAILURES, _quantile, _status,
                              bootstrap_quantile_ci, clopper_pearson, overall_verdict)
from avval.report import write_estimation_report


def test_clopper_pearson_known_values():
    # Textbook values for 5 events in 10 trials and 1 in 100.
    assert clopper_pearson(5, 10) == pytest.approx((0.1871, 0.8129), abs=1e-4)
    lo, hi = clopper_pearson(1, 100)
    assert lo == pytest.approx(0.000253, abs=1e-6) and hi == pytest.approx(0.0545, abs=1e-4)


@pytest.mark.parametrize("n", [10, 100, 300])
def test_clopper_pearson_closed_forms_at_the_edges(n):
    # k = 0: upper = 1 - (alpha/2)^(1/n); k = n: lower = (alpha/2)^(1/n).
    assert clopper_pearson(0, n) == pytest.approx((0.0, 1 - 0.025 ** (1 / n)))
    assert clopper_pearson(n, n) == pytest.approx((0.025 ** (1 / n), 1.0))


def test_zero_failure_bound_is_the_two_sided_rule_of_three():
    # -ln(0.025) = 3.69: the two-sided counterpart of the one-sided "3/n" rule of three.
    n = 5000
    assert clopper_pearson(0, n)[1] * n == pytest.approx(-np.log(0.025), rel=1e-3)


def test_quantile_matches_duckdb_quantile_cont_including_infinity():
    rng = np.random.default_rng(1)
    for x in (rng.normal(size=37), np.array([0.5, 3.0] + [np.inf] * 18),
              np.array([1.0, np.inf, np.inf])):
        for q in (0.05, 0.5, 0.95):
            got = float(_quantile(x, q))
            want = duckdb.sql(f"SELECT quantile_cont(x, {q}) FROM (SELECT unnest(?::DOUBLE[]) x)",
                              params=[list(x)]).fetchone()[0]
            assert got == pytest.approx(want)


def test_bootstrap_is_reproducible_and_calibrated():
    x = np.random.default_rng(2).normal(size=2000)
    ci = bootstrap_quantile_ci(x, 0.5)
    assert ci == bootstrap_quantile_ci(x, 0.5)                    # fixed seed
    assert ci[0] < np.median(x) < ci[1]
    # Asymptotic SE of the median of N(0,1) is 1.2533 / sqrt(n): 95% width about 0.11.
    assert ci[1] - ci[0] == pytest.approx(2 * 1.96 * 1.2533 / np.sqrt(2000), rel=0.25)


def _rate(threshold, min_n=100, op="<="):
    return {"kind": "rate", "op": op, "threshold": threshold, "min_n": min_n}


def _m(k, n):
    lo, hi = clopper_pearson(k, n)
    return {"n": n, "value": k / n, "ci_low": lo, "ci_high": hi}


def test_status_rules():
    assert _status(_rate(0.05), _m(0, 100))[0] == "PASS"            # upper 0.036 <= 0.05
    status, note = _status(_rate(0.05), _m(1, 100))                 # 1% but upper 0.0545
    assert status == INSUFFICIENT and "upper bound" in note
    assert _status(_rate(0.05), _m(10, 100))[0] == "FAIL"
    assert _status(_rate(0.05), _m(0, 50))[0] == INSUFFICIENT       # below min_n
    status, note = _status(_rate(0.0), _m(0, 300))
    assert status == NO_FAILURES and "upper bound = 0.0122" in note
    assert _status(_rate(0.0), _m(1, 300))[0] == "FAIL"
    quantile = {"kind": "quantile", "op": ">=", "threshold": 1.5, "min_n": 100}
    m = {"n": 200, "value": 1.6, "ci_low": 1.4, "ci_high": 1.8}
    assert _status(quantile, m)[0] == INSUFFICIENT                  # lower bound below 1.5
    assert _status(quantile, {**m, "ci_low": 1.55})[0] == "PASS"
    assert overall_verdict([{"status": NO_FAILURES}, {"status": "PASS"}]) == "GO"


def test_report_shows_intervals(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)
    camp = Campaign("ci", store, policy, 30)
    camp.run([dict(scenario="lead_brake", ego_speed=25.0, headway=2.4, lead_decel=1.5,
                   friction=1.0, driver_state="attentive")] * 30)
    text = open(write_estimation_report(store, "ci"), encoding="utf-8").read()
    assert "| 95% CI |" in text
    assert "| AC-01 | Collision-free with attentive supervision | 0 | [0, 0.116] |" in text
    assert "no failures observed in 30 runs; 95% upper bound = 0.1157" in text


def test_bootstrap_is_chunk_size_independent(monkeypatch):
    import avval.evaluation as ev
    x = np.random.default_rng(3).normal(size=997)
    whole = ev.bootstrap_quantile_ci(x, 0.95)  # 2,000 x 997 values: one chunk
    monkeypatch.setattr(ev, "BOOTSTRAP_CHUNK_ELEMENTS", 3 * 997 + 5)  # 3 resamples per chunk
    assert ev.bootstrap_quantile_ci(x, 0.95) == whole
