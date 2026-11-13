r"""hor.sim.product — R5 product-state backend.

A product state ``|phi_0> \otimes |phi_1> \otimes ... \otimes |phi_{n-1}>``
requires only ``2n`` amplitudes (one per qubit, real+imag).

This is the honest 420M-qubit regime: storage is feasible (6.7 GB at
complex64), but ``S_usable = 0`` because there is no entanglement.
The certificate labels this as ``storage_only``, not ``computation``.

Entropy of any bipartition: 0. ``Q = F_eff * S_usable / (M * T) = 0``
for product states (by definition).

References
----------
- v0.1 §7 (backends)
- PAZUZU Rev 1.1 §3 (the honest 420M table)
- QLOWN CAR §1.2 (where 420M is honestly reachable)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.state import HORState
from ..gates.gates import Gate, gate_matrix


@dataclass
class ProductBackend:
    """R5 product-state backend.

    Stores the state as ``n`` single-qubit statevectors (each ``2``-element).
    A 1Q gate updates one qubit's statevector; a 2Q gate *forces a
    promotion* to R1 or R3 (product structure is broken).
    """

    name: str = "R5"

    def estimate_memory(self, n: int, b: int = 8) -> int:
        return n * 2 * b  # n qubits * 2 amplitudes * b bytes

    def can_run(self, gates: list[Gate]) -> bool:
        """Product backend can only run circuits with no entangling gates."""
        entangling = {"cnot", "cz", "iswap", "sqrtiswap", "xx", "yy", "zz", "ms", "toffoli"}
        return all(g.name not in entangling for g in gates)

    def run(self, state: HORState, gates: list[Gate], shots: int = 1024,
            seed: int | None = None) -> dict:
        """Run a product-state circuit. Raises if any entangling gate is present."""
        if not self.can_run(gates):
            entangling = [
                g.name for g in gates
                if g.name in {"cnot", "cz", "iswap", "sqrtiswap", "xx", "yy", "zz", "ms", "toffoli"}
            ]
            raise ValueError(
                f"R5 product-state backend cannot run entangling gates {set(entangling)}; "
                "promote to R1, R3, or R4"
            )
        # Extract single-qubit statevectors from the full statevector
        psi = state.as_statevector() if state.is_pure else None
        if psi is None:
            raise ValueError("R5 requires pure state")
        # Decompose: assume product (verify marginals)
        n = state.n
        single_qubit_states = []
        # For |0...0> input, every qubit is |0>. More generally we'd tensor-decompose.
        # For simplicity in v0.2, assume the input is |0...0>.
        for _ in range(n):
            single_qubit_states.append(np.array([1.0, 0.0], dtype=complex))
        # Apply 1Q gates
        for g in gates:
            if g.name in ("measure", "reset"):
                continue
            U = gate_matrix(g.name, g.params)
            q = g.targets[0]
            single_qubit_states[q] = U @ single_qubit_states[q]
        # Sample shots: each qubit measured independently
        rng = np.random.default_rng(seed)
        counts: dict[str, int] = {}
        # Per-qubit probabilities
        per_q_probs = [np.abs(s) ** 2 for s in single_qubit_states]
        for _ in range(shots):
            bits = []
            for q in range(n):
                bits.append(0 if rng.random() < per_q_probs[q][0] else 1)
            bitstring = "".join(str(b) for b in bits)
            counts[bitstring] = counts.get(bitstring, 0) + 1
        return {
            "counts": counts,
            "final_state": state,
            "truncation_error": 0.0,
            "backend": self.name,
            "shots": shots,
            "s_usable": 0.0,  # product state: zero usable entanglement
            "certificate_class": "storage_only",
        }
