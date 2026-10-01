"""Preventability: collisions that an ideal friction-limited system also has are not the function's fault."""
import pytest

import avval.reference as ref
import avval.report as report_mod
from avval.baselines import auto_report
from avval.campaign import Campaign
from avval.evaluation import evaluate_acceptance
from avval.reference import ccd_preventable, ideal_preventable, reference_collides
from avval.sim import G, simulate

# A cut-in at a 0.3 s headway (4.5 m at 15 m/s) closing at 9 m/s on a wet road: the ideal
# system needs 9^2 / (2 * 0.9 * 0.5 * g) = 9.2 m to match speed, so nothing can avoid it.
CLOSE_CUT_IN = dict(scenario="cut_in", ego_speed=15.0, closing_speed=9.0, headway=0.3,
                    friction=0.5, driver_state="attentive")


@pytest.mark.parametrize("v, closing, mu", [(36, 9, 0.5), (30, 5, 1.0), (20, 3, 0.7)])
def test_cut_in_boundary_matches_analytic(v, closing, mu):
    boundary = closing ** 2 / (2 * 0.9 * mu * G)  # distance to shed the closing speed
    case = dict(scenario="cut_in", ego_speed=v, closing_speed=closing, friction=mu)
    assert reference_collides({**case, "headway": (boundary - 0.05) / v}, 0.9)
    assert not reference_collides({**case, "headway": (boundary + 0.05) / v}, 0.9)


@pytest.mark.parametrize("v, decel, mu", [(36, 9, 1.0), (30, 9, 0.5)])
def test_lead_brake_boundary_matches_analytic(v, decel, mu):
    # Both start braking at the lead's onset from equal speed: the ego (0.9 mu g) needs
    # v^2 / (2 * 0.9 mu g) to stop, the lead (capped at mu g) v^2 / (2 min(decel, mu g)).
    boundary = v ** 2 / (2 * 0.9 * mu * G) - v ** 2 / (2 * min(decel, mu * G))
    case = dict(scenario="lead_brake", ego_speed=v, lead_decel=decel, friction=mu)
    assert reference_collides({**case, "headway": (boundary - 0.05) / v}, 0.9)
    assert not reference_collides({**case, "headway": (boundary + 0.05) / v}, 0.9)


def test_lead_braking_below_ideal_decel_is_always_preventable():
    case = dict(scenario="lead_brake", ego_speed=36.0, lead_decel=8.0, friction=1.0,
                headway=5.0 / 36.0)
    assert ideal_preventable(case)  # 8 < 0.9 g: the ideal ego out-brakes the lead


def test_close_cut_in_is_marked_unpreventable(store, policy, tmp_path, monkeypatch):
    monkeypatch.setattr(report_mod, "RESULTS_DIR", tmp_path)
    assert simulate(CLOSE_CUT_IN, policy, 0)[0]["collision"]  # the system collides...
    assert not ideal_preventable(CLOSE_CUT_IN)                  # ...and so does the ideal
    far = {**CLOSE_CUT_IN, "headway": 2.0}
    camp = Campaign("prev", store, policy, 20)
    camp.run([CLOSE_CUT_IN] * 5 + [far] * 5)
    rows = store.query("SELECT headway, preventable, collision FROM runs ORDER BY run_idx", "prev")
    assert list(rows.preventable) == [False] * 5 + [True] * 5

    acc = {a["id"]: a for a in evaluate_acceptance(store, "prev")}
    assert acc["AC-01"]["n"] == 5 and acc["AC-01"]["value"] == 0.0  # only the far cut-ins
    assert acc["AC-06"]["status"] == "INFO" and acc["AC-06"]["value"] == pytest.approx(0.5)

    text = open(auto_report(camp, "random"), encoding="utf-8").read()
    assert "## Preventability" in text
    assert "| 5 | 0 | 5 | 5 |" in text  # collisions, preventable, unpreventable, unpreventable runs


def test_careful_competent_driver_is_disabled_by_default():
    assert ccd_preventable(CLOSE_CUT_IN) is None


def _with_ccd(monkeypatch, **ccd):
    cfg = {**ref.load_reference(), "careful_competent_driver": {"enabled": True, **ccd}}
    monkeypatch.setattr(ref, "load_reference", lambda: cfg)


def test_enabled_ccd_without_parameters_refuses_to_guess(monkeypatch):
    _with_ccd(monkeypatch, reaction_time_s=None, decel_fraction_of_mu_g=None, jerk_mps3=None)
    with pytest.raises(ValueError, match="TODO"):
        ccd_preventable(CLOSE_CUT_IN)


def test_slower_reference_can_only_find_fewer_cases_preventable(monkeypatch):
    # Test-only values, not R157 parameters.
    _with_ccd(monkeypatch, reaction_time_s=1.0, decel_fraction_of_mu_g=0.7, jerk_mps3=10.0)
    # Ideal needs 6^2 / (2 * 0.9 g) = 2 m; the CCD loses 6 m to reaction time alone.
    case = dict(scenario="cut_in", ego_speed=30.0, closing_speed=6.0, headway=8.0 / 30.0,
                friction=1.0,
                driver_state="attentive")
    assert ideal_preventable(case) and ccd_preventable(case) is False


def test_run_the_system_avoided_is_preventable_even_if_the_reference_collides(store, policy,
                                                                               monkeypatch):
    # A system that brakes before the hazard (e.g. at a short initial headway) can avoid a
    # collision the hazard-onset reference cannot. Such a run is still preventable. The
    # reference is stubbed to "always collides" so the rule is tested without an edge case.
    import avval.campaign as campaign_mod
    monkeypatch.setattr(campaign_mod, "ideal_preventable", lambda case: False)
    safe = dict(scenario="lead_brake", ego_speed=25.0, headway=2.4, lead_decel=1.5, friction=1.0,
                driver_state="attentive")
    camp = Campaign("early", store, policy, 5)
    camp.run([safe] * 5)
    rows = store.query("SELECT collision, preventable FROM runs", "early")
    assert not rows.collision.any() and rows.preventable.all()
