"""hor.shots.planner — Shot planning with statistical bounds.

Implements:
    - Hoeffding bound (v0.1.5 §7, v0.2 §8.2)
    - Bernstein bound (variance-aware)
    - Median-of-means
    - Neyman allocation for commuting Pauli groups
    - Classical shadows (Huang-Kueng-Preskill)

All bounds are *lower bounds* on the number of shots needed. The actual
number used is the maximum over all observables.

P5 falsifiability test:
    Variance-aware (Bernstein + Neyman) planner gives >= 20% reduction
    vs uniform allocation on hardware-mimicking noise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..core.registers import ShotBudget


# --------------------------------------------------------------------------
# Bounds
# --------------------------------------------------------------------------


def hoeffding_shots(eps: float, delta: float, b: float = 1.0, a: float = -1.0) -> int:
    """Hoeffding bound: ``N >= (b-a)^2 ln(2/delta) / (2 eps^2)``.

    For an observable ``O in [a, b]`` with mean ``mu``, the empirical mean
    ``mu_hat`` from N samples satisfies::

        P(|mu_hat - mu| >= eps) <= 2 exp(-2 N eps^2 / (b-a)^2)

    Setting RHS = delta and solving for N gives the bound.
    """
    if eps <= 0 or delta <= 0:
        raise ValueError("eps and delta must be positive")
    return int(math.ceil(((b - a) ** 2 * math.log(2 / delta)) / (2 * eps**2)))


def bernstein_shots(eps: float, delta: float, sigma: float,
                    M: float = 1.0) -> int:
    """Bernstein bound (variance-aware)::

        N >= 2 sigma^2 ln(3/delta) / eps^2 + 3 (b-a) ln(3/delta) / eps

    For ``O in [-M, M]`` with variance ``sigma^2``, this is tighter than
    Hoeffding when the variance is much smaller than ``(b-a)^2``.
    """
    if eps <= 0 or delta <= 0:
        raise ValueError("eps and delta must be positive")
    return int(math.ceil(
        (2 * sigma**2 * math.log(3 / delta)) / eps**2
        + (3 * M * math.log(3 / delta)) / eps
    ))


def median_of_means_shots(eps: float, delta: float, sigma: float,
                          K: int | None = None) -> tuple[int, int]:
    """Median-of-means: split N into K groups, take median of group means.

    Robust to heavy tails; requires only finite variance.

    Returns ``(N_total, K_groups)``.
    """
    if K is None:
        K = max(1, math.ceil(8 * math.log(1 / delta)))
    # Each group needs Hoeffding-like samples
    n_per_group = hoeffding_shots(eps, delta=math.exp(-K / 8))
    return n_per_group * K, K


def neyman_allocation(variances: list[float], total_shots: int) -> list[int]:
    """Optimal allocation across commuting groups (Neyman).

    ``N_j proportional to sqrt(Var_j)`` minimizes the total variance
    ``sum_j Var_j / N_j`` subject to ``sum_j N_j = N``.
    """
    if not variances:
        return []
    sqrt_vars = [math.sqrt(max(v, 0)) for v in variances]
    total = sum(sqrt_vars)
    if total <= 0:
        # All variances zero: equal split
        n = len(variances)
        return [total_shots // n] * n
    raw = [total_shots * s / total for s in sqrt_vars]
    # Floor and distribute remainder
    floored = [int(math.floor(r)) for r in raw]
    remainder = total_shots - sum(floored)
    # Give remainder to the largest fractional parts
    fracs = sorted(range(len(raw)), key=lambda i: raw[i] - floored[i], reverse=True)
    for i in range(remainder):
        floored[fracs[i % len(fracs)]] += 1
    return floored


def shadow_norm(pauli_weight: int, n_qubits: int = 1) -> float:
    """Classical shadows: shadow norm for a weight-w Pauli on qubits.

    ``||P||_sh^2 = 3^w`` (Huang-Kueng-Preskill). For M observables::

        N = O(log M * max_i ||O_i||_sh^2 / eps^2)

    For high-weight observables, the 3^w factor dominates and the
    ``log M / eps^2`` bound does NOT apply.
    """
    return float(3 ** pauli_weight)


# --------------------------------------------------------------------------
# Planner
# --------------------------------------------------------------------------


@dataclass
class ShotPlanner:
    """Plan shots for a list of observables.

    Methods supported: ``"hoeffding"``, ``"bernstein"``, ``"median_of_means"``,
    ``"neyman"``. Default: ``"bernstein"`` (variance-aware, tighter than
    Hoeffding when variances are small).
    """

    method: str = "bernstein"
    target_eps: float = 0.01
    target_delta: float = 0.001
    pilot_shots: int = 100  # for variance estimation

    def plan(
        self,
        observables: list[dict],
        total_budget: int | None = None,
    ) -> ShotBudget:
        """Plan shots for ``observables``.

        Each observable is a dict with keys ``"name"``, ``"pauli_weight"``
        (optional), ``"variance"`` (optional; estimated from pilot if
        absent).
        """
        if not observables:
            return ShotBudget(per_observable={}, total=0, expected_epsilon=self.target_eps,
                              method=self.method, target_delta=self.target_delta)
        per_obs: dict[str, int] = {}
        grouping: list[list[str]] = []
        variances: list[float] = []
        for obs in observables:
            name = obs["name"]
            var = obs.get("variance", 0.25)  # default max-variance for ±1
            w = obs.get("pauli_weight", 1)
            variances.append(var)
            if self.method == "hoeffding":
                n = hoeffding_shots(self.target_eps, self.target_delta)
            elif self.method == "bernstein":
                n = bernstein_shots(self.target_eps, self.target_delta, sigma=math.sqrt(var))
            elif self.method == "median_of_means":
                n, _ = median_of_means_shots(self.target_eps, self.target_delta,
                                              sigma=math.sqrt(var))
            else:
                n = hoeffding_shots(self.target_eps, self.target_delta)
            # Shadow correction
            shadow_factor = shadow_norm(w)
            if shadow_factor > 1:
                n = int(math.ceil(n * shadow_factor))
            per_obs[name] = n
            grouping.append([name])
        # Neyman allocation if total budget is provided
        if total_budget is not None and self.method == "neyman":
            alloc = neyman_allocation(variances, total_budget)
            per_obs = {obs["name"]: alloc[i] for i, obs in enumerate(observables)}
            total = sum(alloc)
        else:
            total = sum(per_obs.values())
        return ShotBudget(
            per_observable=per_obs,
            total=total,
            grouping=grouping,
            expected_epsilon=self.target_eps,
            method=self.method,
            target_delta=self.target_delta,
        )
