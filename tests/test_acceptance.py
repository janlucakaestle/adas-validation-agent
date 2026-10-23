"""Acceptance semantics: one-sided exact bounds, order-statistic quantile bounds, zero goals,
system-independent populations and monotonicity. Mostly on synthetic rows (no simulation),
so each property is tested directly."""
import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats

from avval.config import Release, load_acceptance, load_reference
from avval.evaluation import (INSUFFICIENT, PENDING, check_acceptance, clopper_pearson,
                              clopper_pearson_lower, clopper_pearson_upper, evaluate_acceptance,
                              overall_verdict, quantile_bound_indices, quantile_bounds,
                              quantile_n_needed, rate_n_needed, release_decision)
from avval.frozen import freeze, thaw
from tests.helpers import register, row


def _acc(**changes):
    acc = thaw(load_acceptance())
    for c in acc["criteria"]:
        c.update(changes.get(c["id"], {}))
    return freeze(acc)


def _criterion(results, cid):
    return next(a for a in results if a["id"] == cid)


# ---- bounds -------------------------------------------------------------------------------
def test_one_sided_clopper_pearson_known_values():
    # k = 0: upper = 1 - alpha^(1/n) (one-sided), ~3/n: the rule of three
    for n in (10, 100, 3000):
        assert clopper_pearson_upper(0, n) == pytest.approx(1 - 0.05 ** (1 / n))
    assert clopper_pearson_upper(0, 3000) * 3000 == pytest.approx(-math.log(0.05), rel=1e-3)
    assert clopper_pearson_lower(5, 10) == pytest.approx(stats.beta.ppf(0.05, 5, 6))
    # the two-sided descriptive interval uses alpha/2 per tail and is wider
    lo, hi = clopper_pearson(5, 10)
    assert lo < clopper_pearson_lower(5, 10) and hi > clopper_pearson_upper(5, 10)
    assert clopper_pearson(5, 10) == pytest.approx((0.1871, 0.8129), abs=1e-4)


def test_one_sided_rate_bound_has_its_nominal_coverage():
    rng = np.random.default_rng(0)
    for p, n in ((0.01, 300), (0.05, 120), (0.2, 40)):
        k = rng.binomial(n, p, size=4000)
        cover = np.mean([clopper_pearson_upper(int(x), n) >= p for x in k])
        assert cover >= 0.95 - 3 * math.sqrt(0.05 * 0.95 / 4000)


@pytest.mark.parametrize("q, side", [(0.05, "lower"), (0.95, "upper"), (0.5, "lower")])
def test_order_statistic_bounds_have_finite_sample_coverage(q, side):
    """Exact coverage >= 95% at small n, checked by simulation for skewed data."""
    rng = np.random.default_rng(1)
    true_q = stats.lognorm(1.0).ppf(q)
    for n in (quantile_n_needed(q, side), 100, 250):
        hits = 0
        for _ in range(1500):
            lo, hi = quantile_bounds(rng.lognormal(0, 1, n), q)
            b = lo if side == "lower" else hi
            hits += (b <= true_q) if side == "lower" else (b >= true_q)
        assert hits / 1500 >= 0.95 - 3 * math.sqrt(0.05 * 0.95 / 1500), n


def test_order_statistic_bound_is_unavailable_below_the_minimum_n():
    n_lower = quantile_n_needed(0.05, "lower")
    assert n_lower == 59  # 1 - 0.95^59 >= 0.95 > 1 - 0.95^58
    assert quantile_bound_indices(n_lower - 1, 0.05)[0] is None
    assert quantile_bound_indices(n_lower, 0.05)[0] == 1
    assert quantile_bounds(np.arange(58.0), 0.05)[0] is None


def test_rate_n_needed():
    n = rate_n_needed(1e-4)
    assert clopper_pearson_upper(0, n) <= 1e-4 < clopper_pearson_upper(0, n - 1)


# ---- configuration --------------------------------------------------------------------------
def test_zero_rate_gating_threshold_is_rejected():
    with pytest.raises(ValueError, match="cannot be certified"):
        check_acceptance(_acc(**{"AC-01": {"threshold": 0.0}}))


def test_gating_population_on_system_outputs_is_rejected():
    for where in ("tor_issued AND driver_state = 'distracted'", "NOT collision",
                  "NOT tor_issued", "max_jerk < 3"):
        with pytest.raises(ValueError, match="system outputs"):
            check_acceptance(_acc(**{"AC-03": {"where": where}}))
    with pytest.raises(ValueError, match="system outputs"):
        check_acceptance(_acc(**{"AC-02": {"strata": ["tor_issued"]}}))


def test_info_criteria_conditioned_on_outputs_must_say_so():
    with pytest.raises(ValueError, match="conditional_on_system_output"):
        check_acceptance(_acc(**{"AC-03-C": {"conditional_on_system_output": False}}))


def test_shipped_acceptance_config_is_valid(policy):
    Release.build(policy)  # validates acceptance.yaml among the rest


# ---- statuses on synthetic campaigns -------------------------------------------------------
def _attentive(store, name, n, k, **kw):
    register(store, name)
    store.insert([row(name, i, collision=i < k, **kw) for i in range(n)])
    return evaluate_acceptance(store, name)


def test_zero_events_never_certify_a_zero_rate(store):
    """With no events, AC-01 passes only via the bound on its POSITIVE tolerable rate, and
    only once n is large enough for that bound; never because 'nothing was observed'."""
    small = _criterion(_attentive(store, "s", 2000, 0), "AC-01")
    assert small["status"] == INSUFFICIENT and small["n_needed"] > 2000
    assert "does not" in small["note"]


def test_zero_goal_failure_is_permanent(store):
    a = _criterion(_attentive(store, "z", 5000, 1), "AC-01")
    assert a["status"] == "FAIL" and "zero goal falsified" in a["note"]
    assert "cannot be erased" in a["robustness"] or "Permanent" in a["robustness"]


def test_point_estimate_violation_is_fail_and_demonstration_is_reported(store):
    register(store, "d")
    rows = [row("d", i, driver_state="distracted", handback_required=True,
                collision=i < 30) for i in range(200)]
    store.insert(rows)
    a3 = _criterion(evaluate_acceptance(store, "d"), "AC-03")
    assert a3["status"] == "FAIL" and a3["demonstrated"]  # 15% vs 5%, lower bound > 5%
    assert "unlikely to reverse" in a3["robustness"]


def test_verdict_rules():
    def r(s, req="approved"):
        return {"status": s, "effective_requirement_status": req}
    assert overall_verdict([r("PASS"), r("PASS"), r("INFO")]) == "GO"
    assert overall_verdict([r("PASS"), r(INSUFFICIENT), r("INFO")]) == INSUFFICIENT
    assert overall_verdict([r("FAIL"), r(INSUFFICIENT)]) == "NO-GO"
    assert overall_verdict([r("INFO")]) == INSUFFICIENT  # nothing gating: never GO
    assert overall_verdict([{"status": "PASS"}]) == PENDING  # missing status: not approved


# ---- requirement maturity (item 1) -------------------------------------------------------
def _all_pass_campaign(store, name="ok"):
    """Synthetic data on which every gating criterion with a target passes statistically."""
    register(store, name)
    rows, i = [], 0
    for scen in ("lead_brake", "cut_in"):
        for drv in ("attentive", "distracted"):
            for hb in (False, True):
                for _ in range(400):
                    extra = ({"lead_decel": 2.0, "closing_speed": None}
                             if scen == "lead_brake" else {})
                    rows.append(row(name, i, scenario=scen, driver_state=drv,
                                    handback_required=hb, tor_issued=hb,
                                    tor_time=0.0 if hb else None, **extra))
                    i += 1
    store.insert(rows)
    return name


def _approve(**extra):
    acc = thaw(load_acceptance())
    for c in acc["criteria"]:
        if c.get("op") is not None:
            c["requirement_status"] = "approved"
    for cid, ch in extra.items():
        next(c for c in acc["criteria"] if c["id"] == cid).update(ch)
    return freeze(acc)


def _approved_reference():
    ref = thaw(load_reference())
    ref["ideal"]["status"] = ref["handback_oracle"]["status"] = "approved"
    return freeze(ref)


def _defined_overall():
    """Test-only targets: AC-09/AC-10 get one, and AC-01 a looser one, so that every
    criterion can pass statistically on a few thousand synthetic runs."""
    return {**{cid: {"threshold": 0.05, "requirement_status": "approved"}
               for cid in ("AC-09", "AC-10")}, "AC-01": {"threshold": 0.01}}


def test_statistical_passes_with_provisional_requirements_cannot_be_go(store):
    name = _all_pass_campaign(store)
    acc = evaluate_acceptance(store, name, _approve(**_defined_overall()),
                              _approved_reference())
    assert all(a["status"] == "PASS" for a in acc if a["op"] is not None)
    assert overall_verdict(acc) == "GO"  # only with everything approved...
    for cid in ("AC-01", "AC-02", "AC-03", "AC-04", "AC-07", "AC-08"):
        changes = _defined_overall()
        changes[cid] = {**changes.get(cid, {}), "requirement_status": "provisional"}
        one = evaluate_acceptance(store, name, _approve(**changes), _approved_reference())
        assert all(a["status"] == "PASS" for a in one if a["op"] is not None)
        assert overall_verdict(one) == PENDING, cid  # ...one provisional blocks it
        assert release_decision(one, "final")["formal_decision"] == PENDING


def test_a_provisional_definition_blocks_formal_go(store):
    name = _all_pass_campaign(store)
    ref = thaw(_approved_reference())
    ref["handback_oracle"]["status"] = "provisional"
    acc = evaluate_acceptance(store, name, _approve(**_defined_overall()), freeze(ref))
    by = {a["id"]: a for a in acc}
    assert by["AC-07"]["status"] == "PASS"
    assert by["AC-07"]["effective_requirement_status"] == "provisional"
    assert overall_verdict(acc) == PENDING


def test_shipped_requirements_are_not_approved_and_overall_criteria_have_no_target(store):
    name = _all_pass_campaign(store)
    acc = evaluate_acceptance(store, name)
    by = {a["id"]: a for a in acc}
    assert all(a["effective_requirement_status"] != "approved" for a in acc
               if a["op"] is not None)
    assert by["AC-09"]["status"] == by["AC-10"]["status"] == "NO REQUIREMENT"
    assert overall_verdict(acc) != "GO"
    d = release_decision(acc, "final")
    assert not d["requirements_approved"] and "AC-09" in d["unapproved_requirements"]
    assert release_decision(acc, "development")["formal_decision"].startswith("NONE")


def test_provisional_targets_still_produce_no_go(store):
    register(store, "bad")
    store.insert([row("bad", i, collision=i < 3) for i in range(5000)])  # attentive collisions
    assert overall_verdict(evaluate_acceptance(store, "bad")) == "NO-GO"


def test_missing_requirement_status_is_a_configuration_error():
    acc = thaw(load_acceptance())
    del acc["criteria"][0]["requirement_status"]
    with pytest.raises(ValueError, match="requirement_status"):
        check_acceptance(freeze(acc))


def test_latency_is_a_named_parameter_not_a_hidden_literal():
    ac07 = next(c for c in load_acceptance()["criteria"] if c["id"] == "AC-07")
    assert "{max_tor_latency_s}" in ac07["event"] and ac07["params"]["max_tor_latency_s"] == 0.5
    assert "0.5" not in ac07["event"]
    acc = thaw(load_acceptance())
    next(c for c in acc["criteria"] if c["id"] == "AC-07")["params"] = {}
    with pytest.raises(ValueError, match="undefined params"):
        check_acceptance(freeze(acc))


# ---- distracted collisions cannot fall through (items 2, 3, 25) ---------------------------
def _gating_collision_criteria_counting(store, name, run_idx):
    """IDs of gating criteria whose population contains run `run_idx` and whose event is a
    collision event."""
    out = []
    for c in load_acceptance()["criteria"]:
        if c.get("op") is None or "collision" not in c.get("event", ""):
            continue
        where = c.get("where") or "TRUE"
        n = store.query(f"SELECT count(*) AS n FROM runs WHERE run_idx = {run_idx} "
                        f"AND ({where})", name).n[0]
        if n:
            out.append(c["id"])
    return out


@pytest.mark.parametrize("handback_required", [False, True])
@pytest.mark.parametrize("avoidable", [False, True])
def test_a_distracted_collision_is_always_gated(store, handback_required, avoidable):
    register(store, "x")
    store.insert([row("x", 0, driver_state="distracted", collision=True,
                      handback_required=handback_required, avoidable_by_reference=avoidable)])
    ids = _gating_collision_criteria_counting(store, "x", 0)
    assert "AC-10" in ids  # reference- and oracle-independent
    if avoidable:
        assert "AC-03" in ids  # independent of handback_required


@given(st.lists(st.tuples(st.booleans(), st.booleans()), min_size=150, max_size=250),
       st.data())
@settings(max_examples=15, deadline=None)
def test_making_a_distracted_run_collide_never_improves_misuse_criteria(tmp_path_factory, flags,
                                                                       data):
    """Converting a non-collision into a collision for a distracted driver never removes the
    run from AC-03/AC-10 and never improves their value, whatever handback_required is."""
    from avval.store import Store
    store = Store(tmp_path_factory.mktemp("mono") / "s.duckdb")
    i = data.draw(st.integers(0, len(flags) - 1))
    for name, hit in (("before", None), ("after", i)):
        register(store, name)
        store.insert([row(name, j, driver_state="distracted", handback_required=hb,
                          avoidable_by_reference=True, collision=(c or j == hit))
                      for j, (hb, c) in enumerate(flags)])
    a = {r["id"]: r for r in evaluate_acceptance(store, "before")}
    b = {r["id"]: r for r in evaluate_acceptance(store, "after")}
    for cid in ("AC-03", "AC-10"):
        assert a[cid]["n"] == b[cid]["n"]
        assert b[cid]["value"] >= a[cid]["value"]
        rank = {"FAIL": 0, INSUFFICIENT: 1, "NO REQUIREMENT": 1, "PASS": 2}
        assert rank[b[cid]["status"]] <= rank[a[cid]["status"]]


def test_changing_acc_authority_does_not_change_the_handback_population(policy):
    """The oracle uses a fixed capability: a design variant with different authority keeps
    the same hand-back-required population, so no unsafe run can leave a misuse criterion."""
    from avval.reference import References
    base = Release.build(policy)
    weak = base.with_overrides({"sim": {"ego": {"accel_min_mps2": -2.0}}})
    strong = base.with_overrides({"sim": {"ego": {"accel_min_mps2": -6.0}}})
    rng = np.random.default_rng(0)
    model = base.exposure_model
    cases = [model.sample(rng) for _ in range(300)]
    a, b, c = References(base), References(weak), References(strong)
    assert [a.handback_required(x) for x in cases] == [b.handback_required(x) for x in cases] \
        == [c.handback_required(x) for x in cases]


# ---- monotonicity: the system cannot improve a criterion by changing its denominator --------
def _misuse_rows(name, tor_flags, collide_flags):
    return [row(name, i, driver_state="distracted", handback_required=True, tor_issued=t,
                tor_time=0.0 if t else None, collision=c)
            for i, (t, c) in enumerate(zip(tor_flags, collide_flags))]


def test_suppressing_tors_cannot_improve_ac03(store):
    n = 300
    rng = np.random.default_rng(3)
    collide = rng.uniform(size=n) < 0.04
    register(store, "issued")
    store.insert(_misuse_rows("issued", [True] * n, collide))
    # Same scenarios; the worse system suppresses half the TORs and those runs now collide.
    worse = collide | (np.arange(n) % 2 == 0)
    register(store, "suppressed")
    store.insert(_misuse_rows("suppressed", [i % 2 == 1 for i in range(n)], worse))
    a = _criterion(evaluate_acceptance(store, "issued"), "AC-03")
    b = _criterion(evaluate_acceptance(store, "suppressed"), "AC-03")
    assert a["n"] == b["n"] == n          # the denominator does not shrink
    assert b["value"] >= a["value"] and b["status"] == "FAIL"
    a7 = _criterion(evaluate_acceptance(store, "suppressed"), "AC-07")
    assert a7["status"] == "FAIL"         # missed hand-backs are caught directly


def test_issuing_more_tors_cannot_shrink_ac04s_population(store):
    n = 150
    register(store, "few")
    store.insert([row("few", i, max_jerk_automated=4.0 + 2.0 * (i % 10 == 0)) for i in range(n)])
    register(store, "many")
    store.insert([row("many", i, tor_issued=True, tor_time=0.0, handback_required=False,
                      max_jerk_automated=4.0 + 2.0 * (i % 10 == 0)) for i in range(n)])
    a = _criterion(evaluate_acceptance(store, "few"), "AC-04")
    b = _criterion(evaluate_acceptance(store, "many"), "AC-04")
    assert a["n"] == b["n"] == n and a["value"] == b["value"]
    assert _criterion(evaluate_acceptance(store, "many"), "AC-08")["status"] == "FAIL"


def test_too_short_automated_interval_counts_against_ac04(store):
    register(store, "short")
    store.insert([row("short", i, max_jerk_automated=None if i < 10 else 1.0)
                  for i in range(100)])
    a = _criterion(evaluate_acceptance(store, "short"), "AC-04")
    assert a["n"] == 100 and a["value"] == math.inf and a["status"] == "FAIL"


@given(st.lists(st.floats(0.05, 8.0), min_size=60, max_size=120), st.data())
@settings(max_examples=25, deadline=None)
def test_turning_near_misses_into_collisions_never_improves_ac02(tmp_path_factory, ttcs, data):
    from avval.store import Store
    store = Store(tmp_path_factory.mktemp("ac02") / "s.duckdb")
    k = data.draw(st.integers(1, len(ttcs)))
    order = np.argsort(ttcs)[:k]  # the k closest calls become collisions
    register(store, "before")
    store.insert([row("before", i, min_ttc=t) for i, t in enumerate(ttcs)])
    register(store, "after")
    store.insert([row("after", i, min_ttc=t, collision=i in set(order))
                  for i, t in enumerate(ttcs)])
    a = _criterion(evaluate_acceptance(store, "before"), "AC-02")
    b = _criterion(evaluate_acceptance(store, "after"), "AC-02")
    assert b["n"] == a["n"]
    assert b["value"] <= a["value"] + 1e-12
    assert (b["lower"] or -1) <= (a["lower"] or -1) + 1e-12
    rank = {"FAIL": 0, INSUFFICIENT: 1, "PASS": 2}
    assert rank[b["status"]] <= rank[a["status"]]


def test_strata_protect_a_rare_hazardous_scenario(store):
    """Globally fine, but the rare cut-in stratum fails: AC-02 must FAIL."""
    register(store, "strat")
    rows = [row("strat", i, scenario="lead_brake", lead_decel=2.0, closing_speed=None,
                min_ttc=5.0) for i in range(950)]
    rows += [row("strat", 950 + i, min_ttc=0.8) for i in range(40)]  # 4% cut-ins, all < 1.5 s
    store.insert(rows)
    a2 = _criterion(evaluate_acceptance(store, "strat"), "AC-02")
    assert a2["value"] >= 1.5                     # the pooled 5th percentile looks fine...
    assert a2["status"] == "FAIL" and "stratum" in a2["note"]  # ...the stratum does not
    by = {r["stratum"]["scenario"]: r["status"] for r in a2["strata"]}
    assert by == {"cut_in": "FAIL", "lead_brake": "PASS"}


def test_missing_stratum_is_insufficient_not_pass(store):
    register(store, "one")
    store.insert([row("one", i, scenario="lead_brake", lead_decel=2.0, closing_speed=None)
                  for i in range(500)])
    a2 = _criterion(evaluate_acceptance(store, "one"), "AC-02")
    assert a2["status"] == INSUFFICIENT
