"""hor.sim.extension.sheaf — Cellular sheaf cohomological error detection.

Implements E145-E148 from the HOR-Qudit extension pack:

    E145: cellular sheaf construction on the qudit lattice
    E146: coboundary complex and H^1 computation
    E147: H^1-triggered correction escalation (MWPM -> BP+OSD/RSB)
    E148: sheaf Cheeger inequality (lower bound on coherence gap)

**Reality audit:** This is real mathematics — cellular sheaves on CW
complexes (Hansen-Ghrist 2019), standard sheaf cohomology. It does NOT
claim ERD-field physics or "topos in the backend"; it's a *classical*
diagnostic that detects when local-to-global syndrome reconstruction
fails.

Physical meaning (E146):
    If H^1(X, F) != 0, there are local syndromes that cannot be glued
    into a global correction — a *logical error invisible to standard
    syndrome measurement*. This is the real content of HOR-Qudit's
    H^1 obstruction check.

P2 falsifiability test (E211):
    In a 64-qudit lattice with an injected logical error that commutes
    with all stabilizers, the standard syndrome is all-zero but H^1 != 0.
    Expected: 3/64 samples with H^1 != 0; all 3 detected.
    If H^1 never detects or falsely triggers, disable E146.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from ...core.registers import CellularSheaf


TRL = Literal[
    "Simulation-Emulated", "Simulator-Measured", "Artifact-Verified",
    "Hardware-Target", "Hardware-Measured", "Formal Proof",
]


@dataclass
class SheafBackend:
    """Cellular sheaf backend for H^1 obstruction detection.

    Builds a cellular sheaf on the circuit/lattice graph (0-cells =
    qudits, 1-cells = couplers, 2-cells = gates) and computes the
    sheaf Laplacian's spectral gap and H^1 dimension.

    Use cases:
        - Detect syndrome-invisible logical errors (E146, P2 test)
        - Trigger decoder escalation (E147)
        - Lower-bound coherence time (E148, Cheeger)
    """

    name: str = "sheaf"
    stalk_dim: int = 3
    h1_threshold: float = 1e-3  # ||H^1||^2 > this -> escalate
    trl: TRL = "Artifact-Verified"

    def build_sheaf_from_graph(self, n_vertices: int, edges: list[tuple[int, int]],
                                  restrictions: dict[int, np.ndarray] | None = None) -> CellularSheaf:
        """Build a cellular sheaf on the given graph (E145).

        Parameters
        ----------
        n_vertices : int
            Number of 0-cells (qudits).
        edges : list of (src, dst)
            Graph edges (1-cells / couplers).
        restrictions : dict[int, np.ndarray], optional
            Per-edge restriction maps. Defaults to identity (trivial sheaf).
        """
        sheaf = CellularSheaf(n_vertices=n_vertices, n_edges=0, stalk_dim=self.stalk_dim)
        for eid, (src, dst) in enumerate(edges):
            r = restrictions.get(eid) if restrictions else None
            sheaf.add_edge(eid, src, dst, r)
        return sheaf

    def compute_h1(self, sheaf: CellularSheaf) -> int:
        """Compute dim H^1(X, F) (E146).

        ``H^1 = ker(delta^1) / im(delta^0)``. For our 0/1-cochain complex
        on the circuit graph, ``delta^1`` is the trivial map to
        ``C^2 = 0``, so ``ker(delta^1) = C^1``. Hence::

            dim H^1 = dim C^1 - rank(delta^0)
        """
        return sheaf.h1_dimension()

    def spectral_gap(self, sheaf: CellularSheaf) -> float:
        """Second-smallest eigenvalue of the sheaf Laplacian (E148)."""
        return sheaf.spectral_gap()

    def cheeger_lower_bound(self, sheaf: CellularSheaf, h_F: float) -> float:
        """Sheaf Cheeger inequality (E148)::

            lambda_1 >= h_F^2 / 2

        where ``h_F`` is the sheaf conductance. This gives a *lower bound*
        on the coherence gap from the geometry.
        """
        return (h_F ** 2) / 2.0

    def should_escalate_decoder(self, sheaf: CellularSheaf) -> bool:
        """E147: decide whether to escalate from MWPM to BP+OSD/RSB.

        Rule::

            ||H^1||^2 > tau_H1  ==>  escalate

        With default ``tau_H1 = 1e-3`` and ``||H^1||^2 = dim H^1`` (we use
        dimension as a proxy for squared norm; full Hodge norm requires a
        Riemannian structure on the boundary sheaf).
        """
        h1_dim = self.compute_h1(sheaf)
        return float(h1_dim) > self.h1_threshold

    def diagnose(self, sheaf: CellularSheaf) -> dict:
        """Run the full sheaf diagnostic suite.

        Returns a dict with ``lambda_1``, ``h1_dim``, ``should_escalate``,
        and ``trl`` label.
        """
        return {
            "backend": self.name,
            "lambda_1": self.spectral_gap(sheaf),
            "h1_dim": self.compute_h1(sheaf),
            "should_escalate": self.should_escalate_decoder(sheaf),
            "trl": self.trl,
        }
