"""hor.sim.statevector — R1 dense statevector backend.

Memory: ``b * 2^n`` bytes per statevector (b=8 c64, b=16 c128).

Limits (v0.1.5 §7, v0.2 §7):
    28 qubits dense in 8 GB complex128
    29 in complex64
    30 in 16 GB complex64
    30 in 32 GB complex128
    31+ does not fit on a single node

For n > 30 the router must refuse and emit a StructuredRefusal with
alternatives: R3 MPS, light-cone pruning, sampling, or cloud (R7 stub).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..core.state import HORState
from ..gates.gates import Gate, apply_gate_to_state


@dataclass
class StatevectorBackend:
    """R1 dense statevector / density-matrix backend.

    Internally stores ``rho_2`` as a dense ``2^n x 2^n`` numpy array.
    For pure states, the rank-1 outer product is kept (no separate
    statevector path in v0.2; v0.3 may add a true statevector for memory
    efficiency on pure states).
    """

    name: str = "R1"
    precision: str = "c128"  # or "c64"
    max_qubits_ram_gb: float = 8.0  # user-configurable RAM budget

    @property
    def bytes_per_amplitude(self) -> int:
        return 8 if self.precision == "c64" else 16

    def estimate_memory(self, n: int) -> int:
        """Bytes needed for an ``n``-qubit density matrix."""
        # Density matrix is 2^n x 2^n; for pure states we could use 2^n statevector.
        # v0.2 stores density matrix uniformly.
        return self.bytes_per_amplitude * (4**n)

    def fits(self, n: int) -> bool:
        """Whether ``n`` qubits fit in the configured RAM budget."""
        return self.estimate_memory(n) <= self.max_qubits_ram_gb * (2**30)

    def max_n(self) -> int:
        """Largest ``n`` that fits in RAM."""
        b = self.bytes_per_amplitude
        # 2^n * 2^n * b <= M
        # 2n log 2 <= log (M/b)  => n <= log2(M/b) / 2
        m_bytes = self.max_qubits_ram_gb * (2**30)
        if b >= m_bytes:
            return 0
        return int(math.log2(m_bytes / b) / 2)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, state: HORState, gates: list[Gate], shots: int = 1024,
            seed: int | None = None) -> dict:
        """Run a circuit on this backend.

        For final measurements (the common case), gates with name
        ``"measure"`` or ``"reset"`` are deferred to end-of-circuit
        processing: we sample from the final Born distribution. True
        mid-circuit measurement with classical feedforward is not
        supported in v0.2 (planned for v0.3.1).

        Returns a dict with ``counts``, ``final_state``, ``truncation_error``
        (always 0 for R1), and ``backend`` metadata.
        """
        if not self.fits(state.n):
            raise MemoryError(
                f"R1 cannot fit n={state.n} qubits in {self.max_qubits_ram_gb} GB "
                f"(needs {self.estimate_memory(state.n) / 2**30:.1f} GB)"
            )
        # Apply unitary gates (skip measure/reset; defer to sampling)
        for g in gates:
            if g.name in ("measure", "reset"):
                continue
            state.rho_2 = apply_gate_to_state(state.rho_2, g)
            state.vacuum = False
        # Sample from the final Born distribution
        probs = state.probabilities()
        # Ensure probs sum to 1 (numerical drift guard)
        total = probs.sum()
        if total > 0:
            probs = probs / total
        rng = np.random.default_rng(seed)
        # Sample `shots` bitstrings
        indices = rng.choice(2**state.n, size=shots, p=probs)
        counts: dict[str, int] = {}
        for idx in indices:
            bitstring = format(int(idx), f"0{state.n}b")
            counts[bitstring] = counts.get(bitstring, 0) + 1
        return {
            "counts": counts,
            "final_state": state,
            "truncation_error": 0.0,
            "backend": self.name,
            "shots": shots,
        }

    def _reset(self, state: HORState, qubit: int) -> None:
        """Reset ``qubit`` to ``|0>`` (non-unitary)."""
        P0 = state._projector(qubit, 0)
        post = P0 @ state.rho_2 @ P0
        norm = np.trace(post)
        if abs(norm) > 0:
            state.rho_2 = post / norm
        state.is_pure = False
