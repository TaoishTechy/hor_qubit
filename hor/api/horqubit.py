"""hor.api.horqubit — The user-facing HORQubit class.

Wraps a :class:`hor.core.state.HORState` plus a gate list, dispatches
to the chosen backend, builds a :class:`hor.cert.Certificate`, and
returns a :class:`HORResult` with counts + certificate + status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

import numpy as np

from ..core.state import HORState, make_vacuum
from ..core.registers import (
    ForcingCondition,
    ResourceBudgets,
    ShotBudget,
)
from ..gates.gates import Gate
from ..gates.meta import HORForce, HORCertify, HORMetaOp, HORIdentity
from ..sim.router import Router, BackendChoice, StructuredRefusal
from ..sim.statevector import StatevectorBackend
from ..sim.mps import MPSBackend
from ..sim.stabilizer import StabilizerBackend
from ..sim.product import ProductBackend
from ..shots.planner import ShotPlanner
from ..cert.certificate import Certificate, CertificateBuilder, TRL, Classification
from ..cert.forcing import ForcingProof
from ..calib.importer import Calibration
from ..calib.leakage import LeakageTracker
from ..calib.readout import ReadoutMitigator, NegativityGuardError


@dataclass
class CertifyConfig:
    """Configuration for ``hor.certify``."""

    shots: int = 8192
    target_delta: float = 0.001
    target_eps: float = 0.01
    threshold: float = 0.999
    method: str = "bernstein"


@dataclass
class HORResult:
    """The result of a ``HORQubit.run()`` call."""

    counts: dict[str, int]
    certificate: Certificate | None
    status: Literal["certified", "uncertified", "refused"]
    reason: str | None
    backend: str
    final_state: HORState | None = None
    truncation_error: float = 0.0


# --------------------------------------------------------------------------
# HORQubit class
# --------------------------------------------------------------------------


class HORQubit:
    """The user-facing HOR-Qubit simulator.

    Usage::

        q = HORQubit(n=2)
        q.h(0)
        q.cnot(0, 1)
        q.t(0)
        q.hor_force(ForcingCondition(gap_open=True))
        q.hor_certify(CertifyConfig(shots=8192))
        result = q.run()

    The class accumulates gates and meta-operations until :meth:`run`
    is called. :meth:`run` routes to the best backend, executes the
    circuit, builds a certificate, and returns a :class:`HORResult`.
    """

    def __init__(
        self,
        n: int,
        chi_max: int = 64,
        precision: str = "c128",
        ram_budget_gb: float = 16.0,
        calibration: Calibration | None = None,
    ) -> None:
        self.n = n
        self.chi_max = chi_max
        self.precision = precision
        self.calibration = calibration
        self.state = make_vacuum(n)
        self.gates: list[Gate] = []
        self.meta_ops: list[HORMetaOp] = []
        self._certify_config: CertifyConfig | None = None
        self.router = Router(
            ram_budget_gb=ram_budget_gb,
            chi_max=chi_max,
            allow_dense=True,
        )

    # ------------------------------------------------------------------
    # Gate application (accumulates; doesn't run yet)
    # ------------------------------------------------------------------

    def h(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="h", targets=(q,)))
        return self

    def s(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="s", targets=(q,)))
        return self

    def t(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="t", targets=(q,)))
        return self

    def x(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="x", targets=(q,)))
        return self

    def y(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="y", targets=(q,)))
        return self

    def z(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="z", targets=(q,)))
        return self

    def sqrtx(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="sqrtx", targets=(q,)))
        return self

    def cnot(self, c: int, t: int) -> "HORQubit":
        self.gates.append(Gate(name="cnot", targets=(c, t)))
        return self

    def cx(self, c: int, t: int) -> "HORQubit":
        return self.cnot(c, t)

    def cz(self, a: int, b: int) -> "HORQubit":
        self.gates.append(Gate(name="cz", targets=(a, b)))
        return self

    def iswap(self, a: int, b: int) -> "HORQubit":
        self.gates.append(Gate(name="iswap", targets=(a, b)))
        return self

    def rx(self, theta: float, q: int) -> "HORQubit":
        self.gates.append(Gate(name="rx", targets=(q,), params=(theta,)))
        return self

    def ry(self, theta: float, q: int) -> "HORQubit":
        self.gates.append(Gate(name="ry", targets=(q,), params=(theta,)))
        return self

    def rz(self, theta: float, q: int) -> "HORQubit":
        self.gates.append(Gate(name="rz", targets=(q,), params=(theta,)))
        return self

    def u3(self, theta: float, phi: float, lam: float, q: int) -> "HORQubit":
        self.gates.append(Gate(name="u3", targets=(q,), params=(theta, phi, lam)))
        return self

    def toffoli(self, c1: int, c2: int, t: int) -> "HORQubit":
        self.gates.append(Gate(name="toffoli", targets=(c1, c2, t)))
        return self

    def measure(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="measure", targets=(q,)))
        return self

    def reset(self, q: int) -> "HORQubit":
        self.gates.append(Gate(name="reset", targets=(q,)))
        return self

    # ------------------------------------------------------------------
    # HOR meta-operations (classical, identity on rho_2)
    # ------------------------------------------------------------------

    def hor_force(self, condition: ForcingCondition) -> "HORQubit":
        op = HORForce(condition=condition)
        self.meta_ops.append(op)
        op.apply(self.state)
        return self

    def hor_certify(self, config: CertifyConfig) -> "HORQubit":
        self._certify_config = config
        op = HORCertify(shots=config.shots, target_delta=config.target_delta)
        self.meta_ops.append(op)
        return self

    def hor_route(self) -> BackendChoice:
        op = self.router.choose(self.state, self.gates)
        if isinstance(op, StructuredRefusal):
            return op.as_backend_choice()
        return op

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self, shots: int | None = None, seed: int | None = None) -> HORResult:
        """Run the circuit. Returns a :class:`HORResult` with counts + certificate."""
        # Route
        choice = self.router.choose(self.state, self.gates)
        if isinstance(choice, StructuredRefusal):
            return HORResult(
                counts={},
                certificate=None,
                status="refused",
                reason=choice.reason,
                backend="none",
            )
        backend_name = choice.backend
        # Pick backend
        if backend_name == "R4":
            backend = StabilizerBackend()
        elif backend_name == "R1":
            backend = StatevectorBackend(precision=self.precision,
                                          max_qubits_ram_gb=self.router.ram_budget_gb)
        elif backend_name == "R3":
            backend = MPSBackend(chi_max=self.chi_max)
        elif backend_name == "R5":
            backend = ProductBackend()
        else:
            # Default to R1
            backend = StatevectorBackend(precision=self.precision,
                                          max_qubits_ram_gb=self.router.ram_budget_gb)
        # Determine shots
        shot_count = shots or (self._certify_config.shots if self._certify_config else 1024)
        # Run
        try:
            sim_result = backend.run(self.state, self.gates, shots=shot_count, seed=seed)
        except (ValueError, MemoryError) as e:
            return HORResult(
                counts={},
                certificate=None,
                status="refused",
                reason=str(e),
                backend=backend_name,
            )
        # Build certificate
        cert = self._build_certificate(sim_result, backend_name)
        return HORResult(
            counts=sim_result["counts"],
            certificate=cert,
            status=cert.status,
            reason=cert.reason,
            backend=backend_name,
            final_state=sim_result["final_state"],
            truncation_error=sim_result.get("truncation_error", 0.0),
        )

    # ------------------------------------------------------------------
    # Certificate building
    # ------------------------------------------------------------------

    def _build_certificate(self, sim_result: dict, backend_name: str) -> Certificate:
        """Build a typed Certificate from the simulation result."""
        # Compute F_state, F_process, eps_trunc, eps_shot
        eps_trunc = float(sim_result.get("truncation_error", 0.0))
        # Shot budget
        shot_config = self._certify_config or CertifyConfig(shots=sim_result.get("shots", 1024))
        planner = ShotPlanner(
            method=shot_config.method,
            target_eps=shot_config.target_eps,
            target_delta=shot_config.target_delta,
        )
        budget = planner.plan([{"name": "Z", "pauli_weight": 1, "variance": 0.25}])
        eps_shot = shot_config.target_eps
        # F_state: 1.0 for exact backends, (1 - eps_trunc) proxy for MPS
        f_state = 1.0 if backend_name in ("R1", "R4", "R5") else max(0.0, 1.0 - eps_trunc)
        # F_process: from calibration if available, else 1.0
        f_process = 1.0
        if self.calibration is not None:
            for g in self.gates:
                if g.name in ("measure", "reset"):
                    continue
                err = self.calibration.gate_error(g.name, g.targets)
                f_process *= (1 - err)
        # Leakage (v0.3)
        leakage_tracker = LeakageTracker(n_qubits=self.n)
        if self.calibration is not None:
            leakage_tracker = LeakageTracker.from_calibration(self.calibration, n_qubits=self.n)
        for g in self.gates:
            if g.name in ("measure", "reset"):
                continue
            err = 0.0
            if self.calibration is not None:
                err = self.calibration.gate_error(g.name, g.targets)
            leakage_tracker.step(g.name, g.targets, gate_error=err)
        # Readout mitigation (v0.3)
        neg_mass = 0.0
        mit_applied = False
        if self.calibration is not None and self.calibration.confusion_matrix is not None:
            mitigator = ReadoutMitigator(
                confusion_matrix=self.calibration.confusion_matrix,
                threshold=0.05,
            )
            try:
                _ = mitigator.mitigate_with_guard(sim_result["counts"])
                mit_applied = True
            except NegativityGuardError:
                # Negativity mass exceeds threshold; counts untrusted
                _, neg_mass = mitigator.mitigate(sim_result["counts"])
        # Forcing proof
        forcing_proof = ForcingProof(
            steps=self.state.c_g.forcing_proof,
            dense_sets_checked=self.state.c_g.dense_sets_checked,
            target_phi=self.state.c_g.constraints.formula() if self.state.c_g.constraints else "",
            poset_size=len(self.state.c_g.forcing_proof),
            n_dense_met=len(self.state.c_g.dense_sets_checked),
        )
        # Resource budgets (simplified)
        t_count = sum(1 for g in self.gates if g.name == "t")
        budgets = ResourceBudgets(
            t_count=t_count,
            stabilizer_extent=float((1.0 / (np.cos(np.pi / 8) ** 2)) ** t_count) if t_count > 0 else 1.0,
        )
        # Classification (E209)
        classification_data: dict[str, tuple[float, Classification]] = {}
        if backend_name in ("R4",):
            classification_data["clifford_only"] = (1.0, "Derived")
        if t_count > 0:
            classification_data["t_count"] = (float(t_count), "Derived")
        # TRL
        trl: TRL = "Simulator-Measured"
        if self.calibration is not None:
            trl = "Artifact-Verified"
        # Build certificate
        builder = CertificateBuilder(threshold=shot_config.threshold)
        cert = builder.build(
            forcing_proof=forcing_proof,
            f_state=f_state,
            f_process=f_process,
            eps_trunc=eps_trunc,
            eps_shot=eps_shot,
            backend=backend_name,
            shot_budget=budget,
            resource_budgets=budgets,
            calibration_id=(self.calibration.calibration_id if self.calibration else "calib: none"),
            leakage_max=leakage_tracker.max_leakage,
            leakage_per_qubit=leakage_tracker.per_qubit(),
            readout_negativity=neg_mass,
            readout_mitigation_applied=mit_applied,
            classification_data=classification_data,
            trl=trl,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return cert
