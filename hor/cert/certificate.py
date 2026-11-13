"""hor.cert.certificate — Certificate builder and F_cert computation.

F_cert formula (v0.2 §9.1)::

    F_cert = F_state * F_process * (1 - eps_trunc) * (1 - eps_shot)

Where:
    F_state   : fidelity to ideal statevector (n <= 24) or 1 - eps_trunc proxy
    F_process : 1.0 (v0.2 noiseless) or calibration-based (v0.3)
    eps_trunc : MPS truncation error (cumulative discarded weight)
    eps_shot  : shot noise bound from Hoeffding/Bernstein

Threshold: F_cert >= 0.999 (configurable; default from v0.1.5 §10).

Bures-angle composition (E205, certified fidelity ledger)::

    theta_i = arccos(sqrt(F_i))
    theta_total = sum_i theta_i
    F_cert = cos^2(min(theta_total, pi/2))

This is the rigorous lower bound on total fidelity from per-step losses.

Fuchs-van de Graaf (E206):
    1 - sqrt(F) <= T(rho, sigma) <= sqrt(1 - F)

For any observable O with ||O||_inf = 1:
    |<O>_rho - <O>_sigma| <= 2 sqrt(1 - F_cert)

This is the operational error bar on every reported observable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from ..core.registers import ResourceBudgets, ShotBudget
from .crypto import blake3_hash, canonical_json, ed25519_sign, SigningKey
from .forcing import ForcingProof


TRL = Literal[
    "Simulation-Emulated", "Simulator-Measured", "Artifact-Verified",
    "Hardware-Target", "Hardware-Measured", "Formal Proof",
]


Classification = Literal["Derived", "Topologically Forced", "Design Choice", "Empirical Fit"]


@dataclass
class Certificate:
    """A HOR certificate (Sigma-type, not an iff).

    Fields are independently verified. A signed certificate from a buggy
    simulator is still wrong — HOR requires reproducibility (same code +
    same calibration id => same hash).
    """

    # Required: forcing proof
    forcing_proof: ForcingProof
    # Required: F_cert and components
    f_cert: float
    f_state: float = 1.0
    f_process: float = 1.0
    eps_trunc: float = 0.0
    eps_shot: float = 0.0
    # Required: backend choice
    backend: str = "R1"
    truncation_error: float = 0.0
    shot_budget: ShotBudget = field(default_factory=ShotBudget)
    resource_budgets: ResourceBudgets = field(default_factory=ResourceBudgets)
    # Required: calibration id ("calib: none" in v0.2)
    calibration_id: str = "calib: none"
    # Required: manifest hash and signature
    manifest_hash: str = ""
    signature: str = ""
    signer: str = ""
    timestamp: str = ""
    # Required: status
    status: Literal["certified", "uncertified", "refused"] = "uncertified"
    reason: str | None = None
    # v0.3 calibration fields
    leakage_max: float = 0.0
    leakage_per_qubit: dict[int, float] = field(default_factory=dict)
    readout_negativity: float = 0.0
    readout_mitigation_applied: bool = False
    # HOR-Qudit extension fields (E209 classification matrix, E203 TRL)
    classification: dict[str, tuple[float, Classification]] = field(default_factory=dict)
    trl: TRL = "Simulator-Measured"
    # Energy / information ledger (v0.1.5 §11, PAZUZU Rev 1.1 §5)
    energy_ledger: dict[str, float] = field(default_factory=dict)
    bekenstein_check: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "forcing_proof": self.forcing_proof.as_dict(),
            "f_cert": self.f_cert,
            "f_state": self.f_state,
            "f_process": self.f_process,
            "eps_trunc": self.eps_trunc,
            "eps_shot": self.eps_shot,
            "backend": self.backend,
            "truncation_error": self.truncation_error,
            "shot_budget": {
                "per_observable": self.shot_budget.per_observable,
                "total": self.shot_budget.total,
                "expected_epsilon": self.shot_budget.expected_epsilon,
                "method": self.shot_budget.method,
            },
            "resource_budgets": {
                "entanglement_entropy": self.resource_budgets.entanglement_entropy,
                "magic_robustness": self.resource_budgets.magic_robustness,
                "stabilizer_extent": self.resource_budgets.stabilizer_extent,
                "t_count": self.resource_budgets.t_count,
                "coherence_l1": self.resource_budgets.coherence_l1,
            },
            "calibration_id": self.calibration_id,
            "manifest_hash": self.manifest_hash,
            "signature": self.signature,
            "signer": self.signer,
            "timestamp": self.timestamp,
            "status": self.status,
            "reason": self.reason,
            "leakage_max": self.leakage_max,
            "leakage_per_qubit": {str(k): v for k, v in self.leakage_per_qubit.items()},
            "readout_negativity": self.readout_negativity,
            "readout_mitigation_applied": self.readout_mitigation_applied,
            "classification": {k: {"value": v[0], "category": v[1]}
                                for k, v in self.classification.items()},
            "trl": self.trl,
            "energy_ledger": self.energy_ledger,
            "bekenstein_check": self.bekenstein_check,
        }


# --------------------------------------------------------------------------
# F_cert computation
# --------------------------------------------------------------------------


def compute_f_cert(
    f_state: float,
    f_process: float,
    eps_trunc: float,
    eps_shot: float,
) -> float:
    """``F_cert = F_state * F_process * (1 - eps_trunc) * (1 - eps_shot)``.

    All four factors are independently bounded. The product is a
    *rigorous lower bound* on the true fidelity (E205).
    """
    return f_state * f_process * (1 - eps_trunc) * (1 - eps_shot)


def bures_angle_composition(per_step_fidelities: list[float]) -> float:
    """E205: Bures-angle composition of per-step fidelities.

    ``theta_i = arccos(sqrt(F_i))``; ``theta_total = sum_i theta_i``;
    ``F_cert = cos^2(min(theta_total, pi/2))``.

    This is the rigorous composition rule for fidelity losses. For small
    losses it reduces to the product formula; for large losses it
    saturates at 0.
    """
    if not per_step_fidelities:
        return 1.0
    theta_total = sum(math.acos(math.sqrt(max(min(f, 1.0), 0.0))) for f in per_step_fidelities)
    return math.cos(min(theta_total, math.pi / 2)) ** 2


def fuchs_van_de_graaf_bound(f_cert: float) -> tuple[float, float]:
    """E206: ``1 - sqrt(F) <= T <= sqrt(1 - F)``.

    Returns ``(T_lower, T_upper)`` bounds on trace distance. For an
    observable ``O`` with ``||O||_inf = 1``::

        |<O> - <O>_true| <= 2 * T_upper = 2 * sqrt(1 - F_cert)
    """
    f = max(min(f_cert, 1.0), 0.0)
    return (1 - math.sqrt(f), math.sqrt(1 - f))


# --------------------------------------------------------------------------
# Classification matrix (E209)
# --------------------------------------------------------------------------


def classification(value: float, category: Classification,
                   name: str = "unnamed") -> tuple[float, Classification]:
    """Tag a parameter with its classification (E209).

    Categories:
        - Derived: follows necessarily from established math/physics
        - Topologically Forced: follows from a topological invariant
        - Design Choice: chosen for engineering convenience
        - Empirical Fit: matches simulation data, no derivation

    Downstream consumers may require "Derived" only.
    """
    return (value, category)


# --------------------------------------------------------------------------
# Certificate builder
# --------------------------------------------------------------------------


@dataclass
class CertificateBuilder:
    """Builds signed certificates from simulation results.

    Steps:
        1. Collect ``f_state``, ``f_process``, ``eps_trunc``, ``eps_shot``
        2. Compute ``F_cert = compute_f_cert(...)``
        3. Build forcing proof (from ``state.c_g.forcing_proof``)
        4. Serialize to canonical JSON
        5. BLAKE3-hash the canonical bytes
        6. Ed25519-sign the hash
        7. Emit :class:`Certificate`
    """

    threshold: float = 0.999
    signing_key: SigningKey | None = None

    def build(
        self,
        forcing_proof: ForcingProof,
        f_state: float,
        f_process: float,
        eps_trunc: float,
        eps_shot: float,
        backend: str,
        shot_budget: ShotBudget,
        resource_budgets: ResourceBudgets,
        calibration_id: str = "calib: none",
        leakage_max: float = 0.0,
        leakage_per_qubit: dict[int, float] | None = None,
        readout_negativity: float = 0.0,
        readout_mitigation_applied: bool = False,
        classification_data: dict[str, tuple[float, Classification]] | None = None,
        trl: TRL = "Simulator-Measured",
        energy_ledger: dict[str, float] | None = None,
        bekenstein_check: dict[str, float] | None = None,
        truncation_error: float | None = None,
        timestamp: str = "",
    ) -> Certificate:
        """Build a signed certificate."""
        f_cert = compute_f_cert(f_state, f_process, eps_trunc, eps_shot)
        status: Literal["certified", "uncertified"] = (
            "certified" if f_cert >= self.threshold else "uncertified"
        )
        reason = None if status == "certified" else f"f_cert = {f_cert:.6f} < {self.threshold}"
        # Build the certificate (without hash/signature first)
        cert = Certificate(
            forcing_proof=forcing_proof,
            f_cert=f_cert,
            f_state=f_state,
            f_process=f_process,
            eps_trunc=eps_trunc,
            eps_shot=eps_shot,
            backend=backend,
            truncation_error=truncation_error if truncation_error is not None else eps_trunc,
            shot_budget=shot_budget,
            resource_budgets=resource_budgets,
            calibration_id=calibration_id,
            leakage_max=leakage_max,
            leakage_per_qubit=leakage_per_qubit or {},
            readout_negativity=readout_negativity,
            readout_mitigation_applied=readout_mitigation_applied,
            classification=classification_data or {},
            trl=trl,
            energy_ledger=energy_ledger or {},
            bekenstein_check=bekenstein_check or {},
            status=status,
            reason=reason,
            timestamp=timestamp,
        )
        # Compute manifest hash
        manifest_bytes = canonical_json(cert.to_dict()).encode("utf-8")
        cert.manifest_hash = blake3_hash(manifest_bytes)
        # Sign
        if self.signing_key is not None:
            cert.signature = ed25519_sign(manifest_bytes, self.signing_key)
            cert.signer = self.signing_key.key_id
        return cert
