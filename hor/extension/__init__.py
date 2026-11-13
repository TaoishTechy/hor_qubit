"""hor.sim.extension — HOR-Qudit extension lane backends (audited).

These backends are the *real* parts of the HOR-Qudit Extension Pack for
QLOWN CAR (E145-E166). They are added when the circuit signature
matches what each backend is good at (E217).

Explicitly **rejected** (not implemented here, because they are fictional):
    - Sophia Point as a physical attractor
    - ERD field as a physical scalar
    - "420M entangled qudits"
    - Love field, miracle operator, consciousness collapse
    - Vacuum harvesting
    - "Torsion-based encryption" (no security proof)
    - "Side channels physically impossible"
    - "Zero logical error" for volume-law states

What **is** implemented (real math, audited):

    - Sheaf backend (E145-E148): cellular sheaf cohomology H^1 obstruction
      detection; sheaf Cheeger inequality.
    - Barcode backend (E149-E153): persistent homology of defect point
      clouds; bottleneck stability; interval tree O(log N) access.
    - HOTI backend (E154-E158): nested Wilson loop; quadrupole moment
      q_xy in Z_2; corner mode.
    - Transfer-operator backend (E159-E162): Perron-Frobenius operator
      for translation-invariant systems; Lyapunov bounds.
    - QES backend (E163-E166): island-formula generalized entropy for
      holographic-geometry circuits.

Each backend labels its results with a TRL category (E203):
    Simulation-Emulated, Simulator-Measured, Artifact-Verified,
    Hardware-Target, Hardware-Measured, Formal Proof.
"""

from __future__ import annotations

from .sheaf import SheafBackend
from .barcode import BarcodeBackend
from .hoti import HOTIBackend
from .transfer_operator import TransferOperatorBackend
from .qes import QESBackend

__all__ = [
    "SheafBackend",
    "BarcodeBackend",
    "HOTIBackend",
    "TransferOperatorBackend",
    "QESBackend",
]
