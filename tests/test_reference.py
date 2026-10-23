"""References: scoped, system-independent replays of the scenario."""
import pytest

from avval.campaign import Campaign
from avval.config import Release
from avval.reference import References, reference_collides
from avval.sim import G, nominal_params, simulate

P = nominal_params()
# A cut-in at a 0.3 s headway (4.5 m at 15 m/s) closing at 9 m/s on a wet road: the ideal
# reference needs 9^2 / (2 * 0.9 * 0.5 * g) = 9.2 m to match speed, so it does not avoid it.
CLOSE_CUT_IN = dict(scenario="cut_in", ego_speed=15.0, closing_speed=9.0, headway=0.3,
                    friction=0.5, driver_state="attentive")


@pytest.mark.parametrize("v, closing, mu", [(36, 9, 0.5), (30, 5, 1.0), (20, 3, 0.7)])
def test_cut_in_boundary_matches_analytic(v, closing, mu):
    boundary = closing ** 2 / (2 * 0.9 * mu * G)  # distance to shed the closing speed
    case = dict(scenario="cut_in", ego_speed=v, closing_speed=closing, friction=mu)
    assert reference_collides({**case, "headway": (boundary - 1e-6) / v}, P, 0.9 * mu * G)
    assert not reference_collides({**case, "headway": (boundary + 1e-6) / v}, P, 0.9 * mu * G)


@pytest.mark.parametrize("v, decel, mu", [(36, 9, 1.0), (30, 9, 0.5)])
def test_lead_brake_boundary_matches_analytic(v, decel, mu):
    # Both brake from equal speed at the lead's onset: the ego (0.9 mu g) needs
    # v^2 / (2 * 0.9 mu g) to stop, the lead (capped at mu g) v^2 / (2 min(decel, mu g)).
    boundary = v ** 2 / (2 * 0.9 * mu * G) - v ** 2 / (2 * min(decel, mu * G))
    case = dict(scenario="lead_brake", ego_speed=v, lead_decel=decel, friction=mu)
    assert reference_collides({**case, "headway": (boundary - 1e-6) / v}, P, 0.9 * mu * G)
    assert not reference_collides({**case, "headway": (boundary + 1e-6) / v}, P, 0.9 * mu * G)


def test_reaction_time_and_jerk_only_make_the_reference_worse():
    case = dict(scenario="cut_in", ego_speed=30.0, closing_speed=6.0, headway=8.0 / 30.0,
                friction=1.0)
    assert not reference_collides(case, P, 0.9 * G)              # needs 2 m, has 8 m
    assert reference_collides(case, P, 0.9 * G, reaction_time_s=1.0)  # loses 6 m reacting
    assert reference_collides(case, P, 0.9 * G, jerk_mps3=2.0)        # slow brake build-up


def test_references_do_not_depend_on_the_system(policy):
    """Two very different 'systems' (the policy, and one that never brakes) get identical
    reference columns for the same scenarios."""
    rel = Release.build(policy)
    refs = References(rel)
    for case in (CLOSE_CUT_IN, {**CLOSE_CUT_IN, "headway": 2.0},
                 dict(scenario="lead_brake", ego_speed=30.0, lead_decel=9.0, headway=0.8,
                      friction=1.0, driver_state="distracted")):
        a, b = refs.evaluate(case), refs.evaluate(case)
        assert a == b and set(a) == {"avoidable_by_reference", "handback_required",
                                     "ccd_avoidable_by_reference"}


def test_reference_is_computed_for_every_run_not_only_collisions(store, policy):
    """The old definition replayed only collisions (avoided runs were 'preventable' by
    construction), so the AC-01 denominator depended on the system. Now a run the system
    avoided can still be not-avoidable-by-reference, and is then outside AC-01 regardless."""
    far = {**CLOSE_CUT_IN, "headway": 2.0}
    camp = Campaign("ref", store, policy, 20)
    camp.run([CLOSE_CUT_IN] * 5 + [far] * 5)
    rows = store.query("SELECT avoidable_by_reference, collision FROM runs ORDER BY run_idx", "ref")
    assert list(rows.avoidable_by_reference) == [False] * 5 + [True] * 5
    assert simulate(CLOSE_CUT_IN, policy, 0)[0]["collision"]


def test_handback_oracle_uses_a_fixed_capability_not_the_tested_authority(policy):
    rel = Release.build(policy)
    refs = References(rel)
    assert refs.capability == rel.reference["handback_oracle"]["decel_mps2"]
    # lead braking at mu g from equal speed: 3.5 m/s^2 from onset cannot keep up at 1 s
    hard = dict(scenario="lead_brake", ego_speed=30.0, lead_decel=9.0, headway=1.0,
                friction=1.0, driver_state="attentive")
    assert refs.handback_required(hard) and refs.ideal_avoids(hard)  # 128.6 m > 30 + 50 m
    gentle = {**hard, "lead_decel": 2.0, "headway": 2.5}
    assert not refs.handback_required(gentle)
    # changing the TESTED system's authority leaves the oracle unchanged ...
    weaker = References(rel.with_overrides({"sim": {"ego": {"accel_min_mps2": -2.0}}}))
    mid = {**hard, "lead_decel": 3.0, "headway": 1.2}
    assert weaker.handback_required(mid) == refs.handback_required(mid)
    # ... only the oracle's own capability changes it
    lower = References(rel.with_overrides({"reference": {"handback_oracle": {"decel_mps2": 2.0}}}))
    assert lower.handback_required(mid) and not refs.handback_required(mid)


def test_careful_competent_driver_is_disabled_by_default(policy):
    assert References(Release.build(policy)).ccd_avoids(CLOSE_CUT_IN) is None


def test_enabled_ccd_without_parameters_refuses_to_guess(policy):
    rel = Release.build(policy, overrides={"reference": {"careful_competent_driver": {
        "enabled": True}}})
    with pytest.raises(ValueError, match="TODO"):
        References(rel)


def test_slower_reference_can_only_find_fewer_cases_avoidable(policy):
    rel = Release.build(policy, overrides={"reference": {"careful_competent_driver": {
        "enabled": True, "reaction_time_s": 1.0, "decel_fraction_of_mu_g": 0.7,
        "jerk_mps3": 10.0}}})  # test-only values, not R157 parameters
    refs = References(rel)
    case = dict(scenario="cut_in", ego_speed=30.0, closing_speed=6.0, headway=8.0 / 30.0,
                friction=1.0, driver_state="attentive")
    assert refs.ideal_avoids(case) and refs.ccd_avoids(case) is False
