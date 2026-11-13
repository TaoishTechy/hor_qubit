r"""hor.core.state — The HOR cq-state and its evolution law.

The state is::

    rho_HOR = sum_c p_c rho_2^{(c)} \otimes |c><c|_HGR

with the vacuum::

    rho_HOR^vac = rho_2 \otimes |0><0|_HGR
    Tr_{HGR}[rho_HOR^vac] = rho_2

Quantum evolution: ``rho_2 -> U rho_2 U^dagger`` (unitary) or Lindblad.
Classical update: ``c -> f_classical(c, U)`` (deterministic classical
channel conditioned on gate type and measurement outcome).

**Proof that classical updates do not create entanglement** (v0.1.5
supplement §4.2): the post-update state is::

    rho'_HOR = sum_c p_c (U rho_2^{(c)} U^dagger)
                   \otimes |f(c, U)><f(c, U)|

which is still a cq-state (diagonal in the classical basis) because
``f`` is a deterministic function, not a quantum channel. No off-diagonal
terms in the classical register can appear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from .registers import (
    GenericRecord,
    HollowRecord,
    ResonantRecord,
)


# --------------------------------------------------------------------------
# State representation
# --------------------------------------------------------------------------


@dataclass
class HORState:
    """A HOR cq-state.

    Attributes
    ----------
    rho_2 : np.ndarray
        The ``2^n x 2^n`` quantum density matrix. For pure states,
        ``is_pure=True`` and the state can also be accessed as a statevector
        via :meth:`as_statevector`.
    n : int
        Number of qubits.
    c_h, c_g, c_r : classical registers
        Always allocated, even in vacuum. Vacuum is ``c_h=h_0, c_g=g_0,
        c_r=r_0`` (empty sheaf, bottom forcing, zero reservoir).
    is_pure : bool
        Whether ``rho_2`` is rank-1 (statevector mode).
    vacuum : bool
        True iff all classical registers are at their vacuum values.
    """

    rho_2: np.ndarray
    n: int
    c_h: HollowRecord = field(default_factory=HollowRecord)
    c_g: GenericRecord = field(default_factory=GenericRecord)
    c_r: ResonantRecord = field(default_factory=ResonantRecord)
    is_pure: bool = True
    vacuum: bool = True

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_statevector(cls, psi: np.ndarray, n: int) -> "HORState":
        """Build a pure HOR state from a statevector ``psi`` of length ``2^n``."""
        if psi.shape != (2**n,):
            raise ValueError(f"statevector must have shape ({2**n},); got {psi.shape}")
        psi = psi.astype(complex)
        norm = np.linalg.norm(psi)
        if abs(norm - 1.0) > 1e-10:
            psi = psi / norm
        rho = np.outer(psi, psi.conj())
        return cls(rho_2=rho, n=n, is_pure=True, vacuum=True)

    @classmethod
    def from_density(cls, rho: np.ndarray, n: int) -> "HORState":
        """Build a mixed HOR state from a density matrix ``rho``."""
        expected = (2**n, 2**n)
        if rho.shape != expected:
            raise ValueError(f"density matrix must have shape {expected}; got {rho.shape}")
        rho = rho.astype(complex)
        # Normalize trace
        tr = np.trace(rho)
        if abs(tr - 1.0) > 1e-6:
            rho = rho / tr
        return cls(
            rho_2=rho,
            n=n,
            is_pure=False,
            vacuum=True,
        )

    def as_statevector(self) -> np.ndarray:
        """Return the statevector if pure; else raise."""
        if not self.is_pure:
            raise ValueError("state is mixed; cannot return a statevector")
        # Take the first column of the rank-1 density matrix
        eigs, vecs = np.linalg.eigh(self.rho_2)
        idx = int(np.argmax(eigs))
        return vecs[:, idx]

    # ------------------------------------------------------------------
    # Quantum evolution (only thing that touches rho_2)
    # ------------------------------------------------------------------

    def apply_unitary(self, U: np.ndarray) -> None:
        """Apply a unitary to the quantum part: ``rho_2 -> U rho_2 U^dagger``.

        The classical registers are *not* touched here; gate-specific
        classical updates happen in :mod:`hor.gates`. This is the type
        correction from v0.1.5 §2: the quantum and classical dynamics are
        split, never summed (v0.1's ``H_HOR = H_2 + Delta_F + H_force +
        H_res`` was ill-typed).
        """
        self.rho_2 = U @ self.rho_2 @ U.conj().T
        self.vacuum = False  # any quantum op breaks vacuum (unless identity)

    def apply_channel(self, kraus: list[np.ndarray]) -> None:
        """Apply a CPTP channel ``E(rho) = sum_k K_k rho K_k^dagger``.

        Converts pure state to mixed. Used for depolarizing, dephasing,
        amplitude damping, leakage (v0.3).
        """
        new_rho = np.zeros_like(self.rho_2)
        for K in kraus:
            new_rho += K @ self.rho_2 @ K.conj().T
        self.rho_2 = new_rho
        self.is_pure = False
        self.vacuum = False

    # ------------------------------------------------------------------
    # Measurement (the only quantum-to-classical channel)
    # ------------------------------------------------------------------

    def measure(self, qubit: int, seed: int | None = None) -> int:
        """Measure qubit ``qubit`` in the computational (Z) basis.

        Updates ``rho_2`` by projective collapse AND updates the classical
        reservoir register ``c_r`` with the measurement outcome (v0.1.5
        §4.3: measurement is the *only* place quantum information flows to
        the classical register).

        Returns the outcome bit ``x in {0, 1}``.
        """
        rng = np.random.default_rng(seed)
        # Projectors P_0, P_1 on qubit `qubit`
        P0 = self._projector(qubit, 0)
        P1 = self._projector(qubit, 1)
        p0 = float(np.real(np.trace(P0 @ self.rho_2)))
        p1 = float(np.real(np.trace(P1 @ self.rho_2)))
        # Sanity: p0 + p1 = trace = 1
        if abs(p0 + p1 - 1.0) > 1e-9:
            # Numerical drift; renormalize
            total = p0 + p1
            p0, p1 = p0 / total, p1 / total
        outcome = 0 if rng.random() < p0 else 1
        P = P0 if outcome == 0 else P1
        # Collapse: rho -> P rho P / Tr[P rho]
        post = P @ self.rho_2 @ P
        norm = np.trace(post)
        if abs(norm) > 0:
            self.rho_2 = post / norm
        # Feed outcome to reservoir
        u = np.zeros(1)
        u[0] = float(outcome)
        self.c_r.step(u)
        self.vacuum = False
        return outcome

    def _projector(self, qubit: int, value: int) -> np.ndarray:
        """Build the projector ``|value><value|`` on ``qubit`` (tensor with
        identity on all others). Returns a ``2^n x 2^n`` matrix.
        """
        n = self.n
        # Build via tensor product
        op = np.array([[1.0, 0.0], [0.0, 0.0]]) if value == 0 else np.array([[0.0, 0.0], [0.0, 1.0]])
        full = np.eye(1, dtype=complex)
        for i in range(n):
            full = np.kron(full, op if i == qubit else np.eye(2, dtype=complex))
        return full

    # ------------------------------------------------------------------
    # Compatibility helpers
    # ------------------------------------------------------------------

    def probabilities(self) -> np.ndarray:
        """Diagonal of ``rho_2`` — the Born distribution over computational basis."""
        return np.real(np.diag(self.rho_2)).copy()

    def trace_distance_to(self, other_rho: np.ndarray) -> float:
        """Trace distance ``T(rho, sigma) = 0.5 * ||rho - sigma||_1``."""
        diff = self.rho_2 - other_rho
        s = np.linalg.svd(diff, compute_uv=False)
        return float(0.5 * np.sum(np.abs(s)))


# --------------------------------------------------------------------------
# Vacuum constructor
# --------------------------------------------------------------------------


def make_vacuum(n: int, N_res: int = 128) -> HORState:
    """Construct the vacuum HOR state on ``n`` qubits.

    Quantum part: ``|0...0><0...0|``.
    Classical registers: all at their vacuum values (empty sheaf, bottom
    forcing, zero reservoir).

    For ``n > 16`` we don't allocate the full ``2^n x 2^n`` density
    matrix; instead we use a sparse ``(1, 1)`` block at index ``[0, 0]``
    and tag the state as ``is_pure=True``. The router / backends are
    responsible for allocating full storage when needed.
    """
    if n <= 16:
        rho = np.zeros((2**n, 2**n), dtype=complex)
        rho[0, 0] = 1.0
    else:
        # Sparse vacuum: only the (0, 0) element is non-zero
        # We use a small (1, 1) array and rely on the backend to know
        # the state is |0...0><0...0|. This avoids 2^n * 2^n allocation.
        rho = np.array([[1.0 + 0j]])
    return HORState(
        rho_2=rho,
        n=n,
        c_h=HollowRecord(),
        c_g=GenericRecord(),
        c_r=ResonantRecord(x=np.zeros(N_res)),
        is_pure=True,
        vacuum=True,
    )
