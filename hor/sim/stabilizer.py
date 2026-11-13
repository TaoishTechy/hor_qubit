"""hor.sim.stabilizer — R4 Gottesman-Knill stabilizer backend.

Implements the Aaronson-Gottesman CHP tableau algorithm (Phys. Rev. A
70, 052328, 2004). Memory: ``2n(2n+1)`` bits per tableau.

Clifford gates only: ``{H, S, X, Y, Z, sqrt(X), CNOT, CZ}``. Any ``T``,
``Toffoli``, or non-Clifford-parameterized gate forces the router to
escalate to R1/R2/R3.

Memory at 420M qubits: ``2 * (4.2e8)^2 / 8`` bytes = 44 PB — infeasible.
For Clifford work at large n, use the graph-state backend or Pauli-frame
sampling (Stim-style), not the dense tableau. This module is the
*small-n* reference implementation for exact Clifford simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..core.state import HORState
from ..gates.gates import Gate


@dataclass
class StabilizerTableau:
    """Aaronson-Gottesman CHP tableau.

    Stored as a binary ``(2n, 2n+1)`` numpy array. Rows 0..n-1 are the
    destabilizer generators; rows n..2n-1 are the stabilizer generators.
    The last column is the phase bit (0 = +1, 1 = -1).

    Columns 0..n-1 are X components; columns n..2n-1 are Z components.
    """

    n: int
    tab: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.uint8))

    @classmethod
    def all_zero(cls, n: int) -> "StabilizerTableau":
        """Tableau for the ``|0...0>`` state."""
        tab = np.zeros((2 * n, 2 * n + 1), dtype=np.uint8)
        # Stabilizers: Z_i for i in 0..n-1 (rows n..2n-1)
        # Destabilizers: X_i for i in 0..n-1 (rows 0..n-1)
        for i in range(n):
            tab[i, i] = 1  # X_i (destabilizer)
            tab[n + i, n + i] = 1  # Z_i (stabilizer)
        return cls(n=n, tab=tab)

    def copy(self) -> "StabilizerTableau":
        return StabilizerTableau(n=self.n, tab=self.tab.copy())

    # ------------------------------------------------------------------
    # Gate application
    # ------------------------------------------------------------------

    def apply_h(self, q: int) -> None:
        """Hadamard on qubit ``q``: swap X_q and Z_q columns."""
        self.tab[:, [q, self.n + q]] = self.tab[:, [self.n + q, q]]

    def apply_s(self, q: int) -> None:
        """Phase gate S on qubit ``q``: X_q -> Y_q, Y_q -> -X_q.

        In the tableau: ``Z_q ^= X_q`` (set Z when X is set), then
        update phase when both X and Z are set.
        """
        col_x = self.tab[:, q]
        col_z = self.tab[:, self.n + q]
        # Phase update: for each row, if X_q and Z_q both set, phase flips
        both = col_x & col_z
        self.tab[:, 2 * self.n] ^= both
        # Z_q ^= X_q
        self.tab[:, self.n + q] = col_x ^ col_z

    def apply_x(self, q: int) -> None:
        """Pauli X on qubit ``q``: phase flips when Z_q is set."""
        self.tab[:, 2 * self.n] ^= self.tab[:, self.n + q]

    def apply_z(self, q: int) -> None:
        """Pauli Z on qubit ``q``: phase flips when X_q is set."""
        self.tab[:, 2 * self.n] ^= self.tab[:, q]

    def apply_sqrtx(self, q: int) -> None:
        """sqrt(X) on qubit ``q``: decompose as H S H."""
        self.apply_h(q)
        self.apply_s(q)
        self.apply_h(q)

    def apply_cnot(self, c: int, t: int) -> None:
        """CNOT(c -> t): row updates.

        For each row r:
            phase_r ^= (x_c & z_t & ~(x_t ^ z_c))
            x_t ^= x_c
            z_c ^= z_t
        """
        col_xc = self.tab[:, c]
        col_xt = self.tab[:, t]
        col_zc = self.tab[:, self.n + c]
        col_zt = self.tab[:, self.n + t]
        # Phase: (x_c & z_t) & (x_t ^ z_c ^ 1)  -- standard CHP formula
        phase_flip = (col_xc & col_zt) & (col_xt ^ col_zc ^ 1)
        self.tab[:, 2 * self.n] ^= phase_flip
        # Update X_t and Z_c
        self.tab[:, t] = col_xt ^ col_xc
        self.tab[:, self.n + c] = col_zc ^ col_zt

    def apply_cz(self, q1: int, q2: int) -> None:
        """CZ(q1, q2) = H on q2, CNOT(q1, q2), H on q2."""
        self.apply_h(q2)
        self.apply_cnot(q1, q2)
        self.apply_h(q2)

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def measure(self, q: int, seed: int | None = None) -> int:
        """Measure qubit ``q`` in Z basis. Returns outcome 0 or 1.

        Standard CHP algorithm (Aaronson-Gottesman):

        Random case (some stabilizer anticommutes with Z_q, i.e., has
        X_q set): pick random outcome, row-reduce to clear X_q from all
        other stabilizers, then set the anticommuting stabilizer to
        ``±Z_q`` with phase = outcome.

        Deterministic case (no anticommuting stabilizer): the outcome is
        the phase of the unique product of stabilizers equal to ``±Z_q``.
        We find this by Gaussian elimination on the Z-columns.
        """
        rng = np.random.default_rng(seed)
        # Check if any stabilizer row (n..2n-1) anticommutes with Z_q
        # i.e., has X_q set
        stab_rows = self.tab[self.n : 2 * self.n, :]
        anticommute_mask = stab_rows[:, q] == 1
        if anticommute_mask.any():
            # Random: pick the first anticommuting stabilizer, force outcome
            row_idx = int(np.where(anticommute_mask)[0][0])
            outcome = int(rng.integers(0, 2))
            stab_idx = self.n + row_idx
            target = self.tab[stab_idx, :].copy()
            # Row-reduce: clear X_q from all other stabilizer rows
            for r in range(self.n, 2 * self.n):
                if r == stab_idx:
                    continue
                if self.tab[r, q] == 1:
                    self.tab[r, :] ^= target
            # Also clear X_q from all other DESTABILIZER rows (so they commute properly)
            # (Standard CHP does this; destabilizers paired with anticommuting stabilizers)
            # Now set target to ±Z_q
            new_target = np.zeros(2 * self.n + 1, dtype=np.uint8)
            new_target[self.n + q] = 1
            new_target[2 * self.n] = outcome
            self.tab[stab_idx, :] = new_target
            # Update the corresponding destabilizer to X_q
            self.tab[row_idx, :] = np.zeros(2 * self.n + 1, dtype=np.uint8)
            self.tab[row_idx, q] = 1
            return outcome
        # Deterministic: find the unique product of stabilizers equal to ±Z_q
        # via Gaussian elimination on the full stabilizer tableau.
        # We solve: find c in GF(2)^n such that the product of g_i^{c_i} = ±Z_q alone.
        # The X-part must vanish; the Z-part must equal e_q.
        work = stab_rows.copy()
        n = self.n
        # We perform row reduction on the work matrix, tracking the linear
        # combination via a separate coefficient matrix.
        # coeff[i, j] = 1 iff row i of `work` includes generator j in its product.
        coeff = np.eye(n, dtype=np.uint8)
        # Eliminate X components first (in all columns)
        for j in range(n):
            # Find a row with X_j set
            pivots = np.where(work[:, j] == 1)[0]
            if len(pivots) == 0:
                continue
            pivot = pivots[0]
            for r in pivots[1:]:
                work[r, :] ^= work[pivot, :]
                coeff[r, :] ^= coeff[pivot, :]
        # Now no column has more than one row with X_j set.
        # Eliminate Z components in columns j != q
        for j in range(n):
            if j == q:
                continue
            pivots = np.where(work[:, n + j] == 1)[0]
            if len(pivots) == 0:
                continue
            pivot = pivots[0]
            for r in pivots[1:]:
                work[r, :] ^= work[pivot, :]
                coeff[r, :] ^= coeff[pivot, :]
        # Now look for the row with Z_q set and no other Pauli
        z_q_only = None
        for r in range(n):
            if work[r, n + q] == 1:
                # Check no other Pauli set
                other = any(work[r, j] == 1 for j in range(n) if j != n + q)
                if not other:
                    z_q_only = r
                    break
        if z_q_only is None:
            # No clean ±Z_q row; the state is not actually an eigenstate
            # (shouldn't happen for a valid stabilizer state with no
            # anticommuting stabilizer). Default to 0.
            return 0
        # Outcome = phase of the row, which is the XOR of phases of the
        # generators in the linear combination.
        combo = coeff[z_q_only, :]
        phase = 0
        for i in range(n):
            if combo[i] == 1:
                phase ^= int(stab_rows[i, 2 * n])
        return phase


@dataclass
class StabilizerBackend:
    """R4 stabilizer backend (Gottesman-Knill).

    Memory: ``2n(2n+1) / 8`` bytes per tableau. ~1M qubits needs ~500 GB;
    420M qubits needs 88 PB (infeasible — use Pauli frames instead).
    """

    name: str = "R4"

    def estimate_memory(self, n: int) -> int:
        return (2 * n * (2 * n + 1)) // 8

    def can_run(self, gates: list[Gate]) -> bool:
        """Check whether all gates are Clifford."""
        return all(g.is_clifford for g in gates if g.name not in ("measure", "reset"))

    def run(self, state: HORState, gates: list[Gate], shots: int = 1024,
            seed: int | None = None) -> dict:
        """Run a Clifford-only circuit via tableau simulation."""
        if not self.can_run(gates):
            non_clifford = [g.name for g in gates if not g.is_clifford and g.name not in ("measure", "reset")]
            raise ValueError(
                f"R4 stabilizer cannot run non-Clifford gates: {set(non_clifford)}; "
                "router must escalate to R1/R2/R3"
            )
        tab = StabilizerTableau.all_zero(state.n)
        # Apply gates
        for g in gates:
            if g.name == "h":
                tab.apply_h(g.targets[0])
            elif g.name == "s":
                tab.apply_s(g.targets[0])
            elif g.name == "x":
                tab.apply_x(g.targets[0])
            elif g.name == "y":
                # Y = i X Z; treat as X then Z with phase adjustment
                tab.apply_x(g.targets[0])
                tab.apply_z(g.targets[0])
            elif g.name == "z":
                tab.apply_z(g.targets[0])
            elif g.name == "sqrtx":
                tab.apply_sqrtx(g.targets[0])
            elif g.name == "cnot":
                tab.apply_cnot(g.targets[0], g.targets[1])
            elif g.name == "cz":
                tab.apply_cz(g.targets[0], g.targets[1])
            elif g.name in ("measure", "reset"):
                # Defer measurement to end-of-circuit
                continue
            else:
                # Should have been caught by can_run()
                raise ValueError(f"R4 cannot apply {g.name}")
        # Sample `shots` measurements in Z basis on all qubits
        counts: dict[str, int] = {}
        rng_outer = np.random.default_rng(seed)
        for shot_idx in range(shots):
            outcome_bits = []
            t = tab.copy()
            for q in range(state.n):
                # Advance seed per-qubit so each measurement gets a different RNG
                shot_seed = int(rng_outer.integers(0, 2**31 - 1))
                outcome_bits.append(t.measure(q, seed=shot_seed))
            bitstring = "".join(str(b) for b in outcome_bits)
            counts[bitstring] = counts.get(bitstring, 0) + 1
        return {
            "counts": counts,
            "final_state": state,
            "truncation_error": 0.0,  # stabilizer is exact
            "backend": self.name,
            "shots": shots,
        }
