r"""hor.core — Type-corrected cq-state core (v0.1.5).

The HOR-Qubit state is a classical-quantum (cq) state. The quantum part is
a standard ``2^n x 2^n`` density matrix (or pure statevector). The classical
part is three finite registers — Hollow (H), Generic (G), Resonant (R) —
stored diagonally. **No entanglement** is ever created between the quantum
and classical parts; this is enforced by construction.

The vacuum state is::

    rho_HOR^vac = rho_2 \otimes |0><0|_HGR

so ``Tr_{HGR}[rho_HOR^vac] = rho_2`` exactly. This is the type correction
that v0.1 lacked: v0.1 wrote a naive tensor product of a quantum state with
three "metadata" Hilbert spaces, which conflated classical records with
quantum amplitudes and would have broken the Born rule whenever the
metadata entangled with the qubit.

References
----------
- HOR-Qubit v0.1.5 specification, §1 (cq-state formalism)
- HOR-Qubit v0.2 blueprint, §2 (core simulator)
- Nielsen & Chuang, §8.2 (open quantum systems, cq-states)
"""

from __future__ import annotations

from .state import HORState, make_vacuum
from .registers import (
    HollowRecord,
    GenericRecord,
    ResonantRecord,
    ForcingStep,
    ForcingCondition,
    ResourceBudgets,
    ShotBudget,
)
from .compatibility import backwards_compatible, strip_hor_pragmas

__all__ = [
    "HORState",
    "make_vacuum",
    "HollowRecord",
    "GenericRecord",
    "ResonantRecord",
    "ForcingStep",
    "ForcingCondition",
    "ResourceBudgets",
    "ShotBudget",
    "backwards_compatible",
    "strip_hor_pragmas",
]
