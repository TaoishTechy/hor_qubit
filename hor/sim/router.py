"""hor.sim.router — Backend router and structured refusals.

The router evaluates the circuit feature vector ``phi(C)`` (E110),
computes each backend's cost and memory model, and picks the minimum
(E109). Falls back to :class:`StructuredRefusal` with concrete
alternatives when no single backend fits.

Decision tree (v0.2 §7.1):

    1. Clifford only? -> R4 stabilizer
    2. n <= 24 and dense allowed? -> R1 statevector
    3. Sparse (nnz / 2^n < 1/3)? -> R2 sparse (stub)
    4. 1D / area-law and chi budget fits? -> R3 MPS
    5. Otherwise: StructuredRefusal with alternatives
       (R3 MPS / light cone / sampling / cloud)

Cost model (E137, E143):

    Cost_R1 = O(2^n * depth)
    Cost_R3 = O(n * chi^3 * depth)
    Cost_R4 = O(n * depth)         # per Clifford gate

The router also dispatches to the HOR-Qudit extension lane (sheaf,
barcode, HOTI, transfer-operator, QES) when the circuit signature
matches (E217).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from ..core.state import HORState
from ..gates.gates import Gate


BackendName = Literal["R1", "R2", "R3", "R4", "R5", "R6", "R7",
                      "sheaf", "barcode", "hoti", "transfer_op", "qes", "none"]


@dataclass
class Alternative:
    """A concrete alternative offered in a structured refusal."""

    backend: str
    params: dict[str, Any] = field(default_factory=dict)
    memory_bytes: int = 0
    f_cert_estimate: float = 1.0
    condition: str = ""
    caveat: str = ""


@dataclass
class BackendChoice:
    """The router's decision for a single circuit."""

    backend: BackendName
    reason: str
    estimated_cost: float = 0.0
    estimated_error: float = 0.0
    chi: int | None = None
    cutoff: float | None = None
    alternatives: list[Alternative] = field(default_factory=list)

    def __str__(self) -> str:
        return f"BackendChoice(backend={self.backend}, reason={self.reason!r}, chi={self.chi})"


@dataclass
class StructuredRefusal:
    """A refusal that always carries concrete alternatives.

    No refusal is a dead end. v0.1 said "refused"; v0.1.5 / PAZUZU Rev 1.1
    requires every refusal to ship with at least two alternatives, each
    with a cost model and a condition (fixes A9-103, A9-104, A9-105).
    """

    reason: str
    detail: str
    requested_n: int = 0
    requested_bytes: int = 0
    available_bytes: int = 0
    alternatives: list[Alternative] = field(default_factory=list)

    def as_backend_choice(self) -> BackendChoice:
        return BackendChoice(
            backend="none",
            reason=self.reason,
            alternatives=self.alternatives,
        )


# --------------------------------------------------------------------------
# Feature extraction
# --------------------------------------------------------------------------


@dataclass
class CircuitFeatures:
    """Cheap static features computed before any simulation (E110).

    Extracted from the gate list and state shape without running the
    circuit. Used by the router to pick a backend.
    """

    n: int
    n_gates: int
    t_count: int = 0
    clifford_count: int = 0
    parameterized_count: int = 0
    two_qubit_count: int = 0
    depth: int = 0
    is_clifford_only: bool = True
    max_qubit_index: int = 0
    # HOR-Qudit extension features (E217)
    topological: bool = False  # circuit has C4 / toric-code / surface-code structure
    sparse_amplitudes: bool = False  # statevector is sparse


def extract_features(state: HORState, gates: list[Gate]) -> CircuitFeatures:
    """Compute the circuit feature vector."""
    f = CircuitFeatures(
        n=state.n,
        n_gates=len(gates),
        max_qubit_index=max((max(g.targets) for g in gates if g.targets), default=0),
    )
    for g in gates:
        if g.name == "t":
            f.t_count += 1
            f.is_clifford_only = False
        elif g.name == "toffoli":
            f.t_count += 4  # decomposed cost
            f.is_clifford_only = False
        elif g.is_clifford:
            f.clifford_count += 1
        else:
            f.parameterized_count += 1
            f.is_clifford_only = False
        if g.n_qubits == 2:
            f.two_qubit_count += 1
    f.depth = len(gates)
    return f


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------


@dataclass
class Router:
    """Backend router.

    Holds references to each backend and the cost model parameters
    (RAM budget, chi_max, etc.). The :meth:`plan` method returns the
    list of (backend, estimate) tuples; :meth:`choose` returns the best
    feasible backend or a :class:`StructuredRefusal`.
    """

    ram_budget_gb: float = 16.0
    nvme_budget_gb: float = 0.0  # 0 = no swap
    chi_max: int = 64
    cutoff: float = 1e-10
    truncation_budget: float = 1e-3
    allow_dense: bool = True
    # HOR-Qudit extension features
    enable_extension_lane: bool = True

    @property
    def total_memory_bytes(self) -> int:
        return int((self.ram_budget_gb + self.nvme_budget_gb) * (2**30))

    def plan(self, state: HORState, gates: list[Gate]) -> list[tuple[str, dict]]:
        """Return estimates for each candidate backend."""
        feats = extract_features(state, gates)
        estimates: list[tuple[str, dict]] = []
        # R4 stabilizer
        if feats.is_clifford_only:
            mem_r4 = (2 * feats.n * (2 * feats.n + 1)) // 8
            feasible_r4 = mem_r4 <= self.total_memory_bytes
            estimates.append(("R4", {
                "memory": mem_r4,
                "feasible": feasible_r4,
                "error": 0.0,
                "reason": "Clifford-only; exact via Gottesman-Knill",
            }))
        # R1 statevector
        if self.allow_dense:
            mem_r1 = 16 * (4 ** feats.n)  # density matrix c128
            feasible_r1 = mem_r1 <= self.total_memory_bytes
            estimates.append(("R1", {
                "memory": mem_r1,
                "feasible": feasible_r1,
                "error": 0.0,
                "reason": "dense density matrix" if feasible_r1 else "exceeds RAM+swap",
            }))
        # R3 MPS
        if not feats.is_clifford_only or not any(b[0] == "R4" for b in estimates):
            chi_eff = min(self.chi_max, max(2, 2 ** max(1, int(np.log2(feats.two_qubit_count + 1)))))
            mem_r3 = 2 * feats.n * chi_eff * chi_eff * 16
            feasible_r3 = mem_r3 <= self.total_memory_bytes
            estimates.append(("R3", {
                "memory": mem_r3,
                "feasible": feasible_r3,
                "error": self.truncation_budget if feasible_r3 else 1.0,
                "chi": chi_eff,
                "reason": "MPS with truncation" if feasible_r3 else "chi too large",
            }))
        # R5 product
        if feats.two_qubit_count == 0:
            mem_r5 = feats.n * 2 * 8
            estimates.append(("R5", {
                "memory": mem_r5,
                "feasible": True,
                "error": 0.0,
                "reason": "product state (no entanglement)",
            }))
        # HOR-Qudit extension lane
        if self.enable_extension_lane and feats.topological:
            estimates.append(("hoti", {
                "memory": 4 * 1024,  # placeholder
                "feasible": True,
                "error": 0.0,
                "reason": "HOTI-sim backend for topological circuit",
            }))
        return estimates

    def choose(self, state: HORState, gates: list[Gate]) -> BackendChoice | StructuredRefusal:
        """Choose the best feasible backend or return a structured refusal."""
        estimates = self.plan(state, gates)
        feasible = [(name, est) for name, est in estimates if est.get("feasible", False)]
        if not feasible:
            return self._build_refusal(state, gates, estimates)
        # Pick the cheapest feasible backend
        # Priority: R4 (exact Clifford) > R1 (exact dense) > R3 (MPS) > R5 (product)
        priority = {"R4": 0, "R1": 1, "R5": 2, "R3": 3, "R6": 4, "hoti": 5}
        feasible.sort(key=lambda x: priority.get(x[0], 99))
        name, est = feasible[0]
        return BackendChoice(
            backend=name,  # type: ignore[arg-type]
            reason=est.get("reason", ""),
            estimated_cost=est.get("memory", 0),
            estimated_error=est.get("error", 0.0),
            chi=est.get("chi"),
        )

    def _build_refusal(self, state: HORState, gates: list[Gate],
                        estimates: list[tuple[str, dict]]) -> StructuredRefusal:
        """Build a structured refusal with concrete alternatives."""
        feats = extract_features(state, gates)
        # Estimate what each alternative would need
        alternatives: list[Alternative] = []
        # R3 MPS with higher chi
        chi_alt = min(2048, max(self.chi_max, 2 ** int(np.log2(feats.two_qubit_count + 4))))
        mem_r3 = 2 * feats.n * chi_alt * chi_alt * 16
        alternatives.append(Alternative(
            backend="R3",
            params={"chi": chi_alt},
            memory_bytes=mem_r3,
            f_cert_estimate=0.9995 if mem_r3 <= self.total_memory_bytes else 0.97,
            condition="area-law entanglement; verify entropy before committing",
            caveat=f"needs {mem_r3 / 2**30:.1f} GB; only valid for area-law circuits",
        ))
        # Light-cone pruning (for local observables)
        alternatives.append(Alternative(
            backend="light_cone",
            params={"M": min(feats.n, 30)},
            memory_bytes=16 * (2 ** min(feats.n, 30)),
            f_cert_estimate=0.9999,
            condition="observable is M-local",
            caveat="only valid for local observables on M qubits",
        ))
        # Cloud escalation
        alternatives.append(Alternative(
            backend="R7_cloud",
            params={"qubits": feats.n, "provider": "IBM/Google/IonQ"},
            memory_bytes=0,
            f_cert_estimate=0.95,
            condition="hardware fidelity, not simulation",
            caveat="provider queue; hardware fidelity depends on calibration",
        ))
        return StructuredRefusal(
            reason="statevector_too_large",
            detail=f"n={feats.n} qubits need {16 * 4**feats.n / 2**30:.1f} GB density matrix; "
                   f"available {self.total_memory_bytes / 2**30:.1f} GB",
            requested_n=feats.n,
            requested_bytes=16 * (4 ** feats.n),
            available_bytes=self.total_memory_bytes,
            alternatives=alternatives,
        )


# --------------------------------------------------------------------------
# Top-level routing function
# --------------------------------------------------------------------------


def route_state(state: HORState, chi_max: int = 64,
                allow_dense: bool = True) -> BackendChoice:
    """Quick routing based only on the state, without knowing the circuit.

    Used by the ``HORRoute`` meta-op (v0.1.5 §6) for early regime
    detection. The full routing decision uses both the state and the
    gate list (via :meth:`Router.choose`).
    """
    n = state.n
    # Memory-driven decision only
    if n <= 16:
        return BackendChoice(
            backend="R1",
            reason=f"n={n} fits comfortably in RAM",
            chi=None,
        )
    if n <= 24:
        return BackendChoice(
            backend="R1",
            reason=f"n={n} fits in RAM if dense allowed",
            chi=None,
        )
    if n <= 100:
        return BackendChoice(
            backend="R3",
            reason=f"n={n} too large for dense; use MPS with chi={chi_max}",
            chi=chi_max,
        )
    # n > 100: structured refusal needed
    return BackendChoice(
        backend="none",
        reason=f"n={n} exceeds dense + standard MPS budgets; consider light cone or cloud",
        alternatives=[
            Alternative(backend="R3", params={"chi": chi_max},
                        memory_bytes=2 * n * chi_max * chi_max * 16,
                        f_cert_estimate=0.999,
                        condition="area-law entanglement",
                        caveat="verify entropy before committing"),
            Alternative(backend="light_cone",
                        params={"M": 30},
                        memory_bytes=16 * (2 ** 30),
                        f_cert_estimate=0.9999,
                        condition="observable is M-local",
                        caveat="only valid for local observables"),
        ],
    )
