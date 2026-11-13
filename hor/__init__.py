r"""hor — HOR-Qubit: Hollow Ontological Resonant Qubit framework.

A HOR-Qubit is a standard ``d=2`` qubit plus three certified classical
metadata layers (Hollow, Generic, Resonant) that travel with it through
compilation, simulation, and readout. When those layers are in vacuum,
the HOR-Qubit *is* a qubit, bit for bit.

Core rule (v0.1.5 type correction)::

    rho_HOR = sum_c p_c rho_2^{(c)} \otimes |c><c|_HGR

The qubit stays quantum; the H/G/R layers stay classical. Stripping
``hor.`` pragmas leaves the exact original standard circuit.

Quick start::

    from hor import HORQubit, ForcingCondition, CertifyConfig

    q = HORQubit(n=2, chi_max=64)
    q.h(0)
    q.cnot(0, 1)
    q.t(0)
    q.hor_force(ForcingCondition(gap_open=True))
    q.hor_certify(CertifyConfig(shots=8192))
    result = q.run()
    print(result.counts)
    print(result.certificate.f_cert, result.certificate.backend)
"""

from __future__ import annotations

__version__ = "0.3.0"

# Re-export the most common API surface
from .core.state import HORState, make_vacuum
from .core.registers import (
    ForcingCondition,
    HollowRecord,
    GenericRecord,
    ResonantRecord,
    ResourceBudgets,
    ShotBudget,
)
from .core.compatibility import backwards_compatible, strip_hor_pragmas
from .gates.gates import Gate, GATES, T_STATE_EXTENT
from .gates.meta import HORMetaOp, HORForce, HORCertify, HORIdentity
from .sim.router import Router, BackendChoice, StructuredRefusal, route_state
from .sim.statevector import StatevectorBackend
from .sim.mps import MPSBackend, MPS
from .sim.stabilizer import StabilizerBackend, StabilizerTableau
from .sim.product import ProductBackend
from .sim.extension import (
    SheafBackend,
    BarcodeBackend,
    HOTIBackend,
    TransferOperatorBackend,
    QESBackend,
)
from .shots.planner import ShotPlanner, hoeffding_shots, bernstein_shots
from .cert.certificate import (
    Certificate,
    CertificateBuilder,
    compute_f_cert,
    bures_angle_composition,
    fuchs_van_de_graaf_bound,
)
from .cert.crypto import blake3_hash, ed25519_sign, SigningKey, canonical_json
from .cert.forcing import ForcingProof, check_forcing_proof
from .cert.ledger import RunLedger, LedgerEntry
from .calib.importer import Calibration, CalibrationImporter
from .calib.leakage import LeakageTracker
from .calib.readout import ReadoutMitigator, NegativityGuardError
from .api.horqubit import HORQubit, HORResult, CertifyConfig
from .api.qasm import parse_qasm, QASMProgram

__all__ = [
    "__version__",
    # Core
    "HORState", "make_vacuum",
    "ForcingCondition", "HollowRecord", "GenericRecord", "ResonantRecord",
    "ResourceBudgets", "ShotBudget",
    "backwards_compatible", "strip_hor_pragmas",
    # Gates
    "Gate", "GATES", "T_STATE_EXTENT",
    "HORMetaOp", "HORForce", "HORCertify", "HORIdentity",
    # Backends
    "Router", "BackendChoice", "StructuredRefusal", "route_state",
    "StatevectorBackend", "MPSBackend", "MPS",
    "StabilizerBackend", "StabilizerTableau", "ProductBackend",
    # Extension lane (HOR-Qudit)
    "SheafBackend", "BarcodeBackend", "HOTIBackend",
    "TransferOperatorBackend", "QESBackend",
    # Shots
    "ShotPlanner", "hoeffding_shots", "bernstein_shots",
    # Certificate
    "Certificate", "CertificateBuilder", "compute_f_cert",
    "bures_angle_composition", "fuchs_van_de_graaf_bound",
    "blake3_hash", "ed25519_sign", "SigningKey", "canonical_json",
    "ForcingProof", "check_forcing_proof",
    "RunLedger", "LedgerEntry",
    # Calibration
    "Calibration", "CalibrationImporter",
    "LeakageTracker", "ReadoutMitigator", "NegativityGuardError",
    # API
    "HORQubit", "HORResult", "CertifyConfig",
    "parse_qasm", "QASMProgram",
]
