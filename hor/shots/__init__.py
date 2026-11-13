"""hor.shots — Shot planner.

Implements v0.1.5 §7 (measurement and readout), v0.2 §8 (shot planner):

    - Hoeffding bound (E122): N >= (b-a)^2 ln(2/delta) / (2 epsilon^2)
    - Bernstein bound (variance-aware): N >= 2 sigma^2 ln(3/delta)/eps^2 + ...
    - Median-of-means: split N into K groups, take median
    - Neyman allocation (E8.3): N_j proportional to sqrt(Var_j) for
      commuting groups
    - Classical shadows (Huang-Kueng-Preskill): N = O(log M / eps^2) for
      low-rank Pauli observables; weight-w Pauli scales as 3^w
"""

from __future__ import annotations

import math
from .planner import (
    ShotPlanner,
    hoeffding_shots,
    bernstein_shots,
    median_of_means_shots,
    neyman_allocation,
    shadow_norm,
)

__all__ = [
    "ShotPlanner",
    "hoeffding_shots",
    "bernstein_shots",
    "median_of_means_shots",
    "neyman_allocation",
    "shadow_norm",
]
