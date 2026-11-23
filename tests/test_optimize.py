"""Frontier computation and the surrogate integer program."""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from reapschema import optimize as opt
from reapschema.validate import OPTIONAL_ELEMENTS


def test_specification_enumeration_respects_dependencies():
    specs = opt.all_specifications()
    assert len(OPTIONAL_ELEMENTS) <= 16
    assert len(specs) == len(set(specs)) < 2 ** len(OPTIONAL_ELEMENTS)
    assert frozenset() in specs
    assert all(opt.feasible(s) for s in specs)
    assert not opt.feasible({"weather_normalization"})
    assert opt.feasible({"weather_normalization", "billing_dates"})
    assert not opt.feasible({"export_channel"})


@settings(max_examples=100, deadline=None)
@given(st.lists(st.tuples(st.floats(0, 100), st.floats(0, 1)), min_size=1, max_size=60))
def test_pareto_front_contains_exactly_the_nondominated_points(points):
    cost = np.array([p[0] for p in points])
    loss = np.array([p[1] for p in points])
    front = opt.pareto_front(cost, loss)
    # every point is weakly dominated by a point of the front
    for i in range(len(points)):
        assert any(cost[k] <= cost[i] and loss[k] <= loss[i] + 1e-12 for k in front)
    # along the front, cost increases and loss strictly decreases
    assert np.all(np.diff(cost[front]) >= 0)
    assert np.all(np.diff(loss[front]) < 0)
    budgets = np.linspace(0, 100, 11)
    best = opt.frontier_at_budgets(cost, loss, budgets)
    finite = best[~np.isnan(best)]
    assert np.all(np.diff(finite) <= 1e-12)


def test_surrogate_fit_is_exact_for_quadratic_functions():
    rng = np.random.default_rng(0)
    k = len(OPTIONAL_ELEMENTS)
    x = rng.integers(0, 2, (400, k)).astype(float)
    w = rng.normal(0, 1, k)
    y = 2.0 + x @ w + 0.7 * x[:, 0] * x[:, 3] - 0.4 * x[:, 2] * x[:, 5]
    s = opt.fit_surrogate(x, y)
    assert s.r2 == pytest.approx(1.0, abs=1e-6)
    assert opt.surrogate_value(s, x[7]) == pytest.approx(y[7], abs=1e-4)


def test_ilp_solution_equals_brute_force_optimum():
    rng = np.random.default_rng(1)
    k = len(OPTIONAL_ELEMENTS)
    specs = opt.all_specifications()
    x = np.array([opt.spec_vector(s) for s in specs])
    w = -np.abs(rng.normal(0.02, 0.02, k))
    y = 0.5 + x @ w + 0.03 * x[:, 0] * x[:, 1]
    surrogate = opt.fit_surrogate(x, y)
    tau = rng.uniform(1, 20, k)
    for budget in (10.0, 35.0, 80.0):
        sol = opt.solve_surrogate_ilp(surrogate, tau, budget, 1e-4)
        assert sol["status"] == "ok" and sol["condition"] == "optimal"
        assert sol["primal_feasible"]
        feasible = x @ tau <= budget + 1e-9
        assert sol["objective"] == pytest.approx(y[feasible].min(), abs=1e-5)


def test_rule_availability_grows_with_elements():
    from reapschema.validate import RULES

    for a, b in itertools.pairwise([frozenset(), frozenset({"billing_dates"}),
                                    frozenset(OPTIONAL_ELEMENTS)]):
        ra = {r.key for r in RULES if r.requires <= a}
        rb = {r.key for r in RULES if r.requires <= b}
        assert ra <= rb
