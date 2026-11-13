"""Tests for the shot planner: Hoeffding, Bernstein, MoM, Neyman, shadows."""

from __future__ import annotations

import math

import pytest

from hor.shots.planner import (
    ShotPlanner,
    hoeffding_shots,
    bernstein_shots,
    median_of_means_shots,
    neyman_allocation,
    shadow_norm,
)


def test_hoeffding_basic():
    """Hoeffding bound is positive and scales as 1/eps^2."""
    n = hoeffding_shots(eps=0.01, delta=0.001)
    assert n > 0
    # 4x tighter eps -> 16x more shots
    n_tight = hoeffding_shots(eps=0.005, delta=0.001)
    assert n_tight >= 4 * n - 10  # roughly 16x


def test_bernstein_tighter_than_hoeffding_for_low_variance():
    """Bernstein is tighter when variance is much smaller than (b-a)^2."""
    # Hoeffding for eps=0.01, delta=0.001: N = 1 * ln(2000) / 0.0002 ~ 50k
    n_h = hoeffding_shots(eps=0.01, delta=0.001)
    # Bernstein with small sigma=0.01
    n_b = bernstein_shots(eps=0.01, delta=0.001, sigma=0.01)
    assert n_b < n_h  # Bernstein should be tighter


def test_median_of_means_splits_into_groups():
    """Median-of-means splits shots into K groups."""
    n, k = median_of_means_shots(eps=0.01, delta=0.001, sigma=0.1)
    assert k > 0
    assert n > 0
    assert n >= k  # at least one shot per group


def test_neyman_allocation_proportional_to_sqrt_variance():
    """Neyman allocates shots proportional to sqrt(Var_j)."""
    variances = [1.0, 4.0, 9.0]  # sqrt: 1, 2, 3
    alloc = neyman_allocation(variances, total_shots=600)
    # Should be 100, 200, 300 (proportional to sqrt)
    assert alloc[0] == pytest.approx(100, abs=2)
    assert alloc[1] == pytest.approx(200, abs=2)
    assert alloc[2] == pytest.approx(300, abs=2)


def test_neyman_allocation_zero_variance():
    """Zero-variance groups get ~0 shots."""
    variances = [0.0, 1.0]
    alloc = neyman_allocation(variances, total_shots=100)
    assert alloc[0] == 0
    assert alloc[1] == 100


def test_shadow_norm_pauli_weight():
    """Shadow norm for weight-w Pauli is 3^w (Huang-Kueng-Preskill)."""
    assert shadow_norm(0) == 1.0
    assert shadow_norm(1) == 3.0
    assert shadow_norm(2) == 9.0
    assert shadow_norm(3) == 27.0


def test_shot_planner_returns_budget():
    """ShotPlanner returns a ShotBudget with per-observable counts."""
    planner = ShotPlanner(method="hoeffding", target_eps=0.1, target_delta=0.01)
    obs = [{"name": "Z0", "pauli_weight": 1}, {"name": "Z1", "pauli_weight": 1}]
    budget = planner.plan(obs)
    assert budget.total > 0
    assert "Z0" in budget.per_observable
    assert "Z1" in budget.per_observable


def test_shot_planner_shadow_correction():
    """High-weight observables get more shots (3^w factor)."""
    planner = ShotPlanner(method="hoeffding", target_eps=0.1, target_delta=0.01)
    obs_low = [{"name": "Z0", "pauli_weight": 1}]
    obs_high = [{"name": "ZZZZ", "pauli_weight": 4}]
    b_low = planner.plan(obs_low)
    b_high = planner.plan(obs_high)
    # 3^4 = 81x more shots for weight-4
    assert b_high.per_observable["ZZZZ"] > b_low.per_observable["Z0"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
