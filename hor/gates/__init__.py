"""hor.gates — Full v0.1.5 gate set + HOR meta-operations.

Quantum gates (act on ``rho_2`` via ``U rho_2 U^dagger``):

Clifford:
    H, S, X, Y, Z, sqrtX, CNOT, CZ

Non-Clifford:
    T, Toffoli

Parameterized (for VQE/QAOA):
    RX(theta), RY(theta), RZ(theta), U3(theta, phi, lambda)

Hardware 2-qubit:
    iSWAP, sqrtISWAP, XX, YY, ZZ, MolmerSorensen

Mid-circuit:
    measure, reset, if_cbit feedforward

HOR meta-operations are **classical compiler operations**, not quantum
gates. They form a monoid with identity ``hor.id`` and associative
composition. They are identity on ``rho_2`` and only update classical
registers (v0.1.5 §6, v0.2 §3.3):
    - hor_force(p: ForcingCondition)
    - hor_certify(config: CertifyConfig) -> Certificate
    - hor_scar_read() -> classical H^1 diagnostic
    - hor_route() -> BackendChoice

This file fixes v0.1 issues A6-65 (gate set too small), A7-81/82
(missing 2Q and parameterized gates), A8-95 (mid-circuit missing),
A7-73..A7-84 (meta-gates are not gates).
"""

from __future__ import annotations

from .gates import (
    GATES,
    Gate,
    gate_matrix,
    is_clifford,
    apply_gate_to_state,
    T_STATE_EXTENT,
)
from .meta import (
    HORMetaOp,
    HORForce,
    HORCertify,
    HORScarRead,
    HORRoute,
    HORIdentity,
    compose_meta_ops,
)

__all__ = [
    "GATES",
    "Gate",
    "gate_matrix",
    "is_clifford",
    "apply_gate_to_state",
    "T_STATE_EXTENT",
    "HORMetaOp",
    "HORForce",
    "HORCertify",
    "HORScarRead",
    "HORRoute",
    "HORIdentity",
    "compose_meta_ops",
]
