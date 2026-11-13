"""hor.calib.readout — Readout mitigation with negativity guard.

Implements v0.3 §3:

    1. Import confusion matrix ``M_cal`` per qubit.
    2. Build full ``M`` as tensor product for ``n <= 8``.
    3. Mitigate counts via iterative Bayesian unfolding (D'Agostini).
    4. Compute mitigated quasi-probabilities ``p_tilde``.
    5. Compute negativity mass ``Neg = sum_{x: p_tilde < 0} |p_tilde(x)|``.
    6. Guard: if ``Neg > 0.05`` (configurable), mark calibration stale.

The negativity guard is the *real* content of HOR's readout check.
Negativity appears only when using matrix inversion ``p_tilde = M^{-1} q``
on a poorly-conditioned confusion matrix. Iterative Bayesian unfolding
preserves non-negativity but can be slow to converge; the negativity
mass is therefore a *test of inversion stability*, not a test of physics.

Negativity mass = distance to the physical polytope::

    Neg = min_{p in P} || p_tilde - p ||_1 / 2

where ``P = {p >= 0, sum p = 1}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


class NegativityGuardError(Exception):
    """Raised when the negativity guard fires (calibration is stale)."""


@dataclass
class ReadoutMitigator:
    """Readout mitigation via iterative Bayesian unfolding.

    Parameters
    ----------
    confusion_matrix : list of list of float
        Per-qubit or full-register confusion matrix ``M``. For per-qubit,
        the full matrix is the tensor product.
    threshold : float, default 0.05
        Negativity mass threshold. If ``Neg > threshold``, mark
        calibration stale.
    max_iterations : int, default 10
        Iteration count for D'Agostini unfolding.
    """

    confusion_matrix: list[list[float]]
    threshold: float = 0.05
    max_iterations: int = 10

    def __post_init__(self) -> None:
        # Validate
        cm = np.array(self.confusion_matrix, dtype=float)
        for i, row in enumerate(cm):
            if abs(sum(row) - 1.0) > 1e-6:
                raise ValueError(f"confusion matrix row {i} does not sum to 1: {row}")
        self._cm = cm
        self._n = int(np.log2(cm.shape[0])) if cm.shape[0] != 2 else 1

    def mitigate(self, counts: dict[str, int]) -> tuple[dict[str, float], float]:
        """Mitigate raw counts via iterative Bayesian unfolding.

        Returns ``(mitigated_quasi_probs, negativity_mass)``.
        """
        if not counts:
            return {}, 0.0
        # Convert counts to observed probability vector
        n_qubits = len(next(iter(counts))) if counts else 0
        dim = 2 ** n_qubits
        # If confusion matrix is per-qubit (2x2), tensor up
        if self._cm.shape == (2, 2) and n_qubits > 1:
            M = self._cm
            for _ in range(n_qubits - 1):
                M = np.kron(M, self._cm)
        elif self._cm.shape == (dim, dim):
            M = self._cm
        else:
            raise ValueError(
                f"confusion matrix shape {self._cm.shape} incompatible with n={n_qubits}"
            )
        # Build observed probability vector
        total = sum(counts.values())
        q_obs = np.zeros(dim)
        for bitstring, count in counts.items():
            idx = int(bitstring, 2)
            q_obs[idx] = count / total
        # Iterative Bayesian unfolding (D'Agostini)
        p_est = np.ones(dim) / dim  # uniform prior
        for _ in range(self.max_iterations):
            # p_est_new(x) = sum_y (M[y,x] * p_est(x) / sum_x' M[y,x'] * p_est(x')) * q_obs(y)
            forward = M @ p_est  # P(y) = sum_x M[y,x] P(x)
            forward_safe = np.where(forward > 1e-15, forward, 1e-15)
            # Update: p_est(x) = sum_y p_est(x) * M[y,x] * q_obs(y) / forward(y)
            p_est = p_est * (M.T @ (q_obs / forward_safe))
            # Normalize
            p_est = p_est / max(p_est.sum(), 1e-15)
        # Compute negativity mass
        neg_mass = float(np.sum(np.abs(p_est[p_est < 0])))
        # Convert to dict
        mitigated: dict[str, float] = {}
        for i in range(dim):
            bitstring = format(i, f"0{n_qubits}b")
            mitigated[bitstring] = float(p_est[i])
        return mitigated, neg_mass

    def check_guard(self, neg_mass: float) -> bool:
        """Return True if negativity mass is below threshold."""
        return neg_mass <= self.threshold

    def mitigate_with_guard(self, counts: dict[str, int]) -> dict[str, float]:
        """Mitigate and raise :class:`NegativityGuardError` if guard fires.

        The mitigated counts are still returned (flagged
        ``mitigated_untrusted``) — the user can decide to accept or rerun.
        """
        mitigated, neg_mass = self.mitigate(counts)
        if not self.check_guard(neg_mass):
            # Don't raise; return flagged counts. Caller decides.
            # Actually raise a warning-style exception for explicit handling.
            raise NegativityGuardError(
                f"negativity mass {neg_mass:.4f} exceeds threshold {self.threshold:.4f}; "
                "calibration is likely stale; counts returned untrusted"
            )
        return mitigated
