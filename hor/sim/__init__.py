"""hor.sim — Simulation backends and router.

Backends:
    - R1 statevector (dense 2^n)
    - R2 sparse amplitude dictionary
    - R3 MPS / TEBD with bond chi
    - R4 stabilizer (Gottesman-Knill tableau)
    - R5 product state
    - R6 trajectory sampling (quantum jumps for density matrices n > 14)

HOR-Qudit extension lane backends (real math, audited):
    - Sheaf backend (cellular sheaf H^1 obstruction; E145-E148)
    - Barcode backend (persistent homology syndrome; E149-E153)
    - HOTI backend (nested Wilson loop; E154-E158)
    - Transfer-operator backend (Perron-Frobenius; E159-E162)
    - QES backend (island-formula QEC; E163-E166)

The router picks the cheapest backend that meets the user's error budget,
or returns a :class:`StructuredRefusal` with concrete alternatives
(v0.1.5 §7, PAZUZU Rev 1.1 §2).
"""

from __future__ import annotations

from .statevector import StatevectorBackend
from .mps import MPSBackend
from .stabilizer import StabilizerBackend
from .product import ProductBackend
from .router import Router, BackendChoice, StructuredRefusal, route_state, BackendName
from .extension import (
    SheafBackend,
    BarcodeBackend,
    HOTIBackend,
    TransferOperatorBackend,
    QESBackend,
)

__all__ = [
    "StatevectorBackend",
    "MPSBackend",
    "StabilizerBackend",
    "ProductBackend",
    "Router",
    "BackendChoice",
    "StructuredRefusal",
    "route_state",
    "BackendName",
    "SheafBackend",
    "BarcodeBackend",
    "HOTIBackend",
    "TransferOperatorBackend",
    "QESBackend",
]
