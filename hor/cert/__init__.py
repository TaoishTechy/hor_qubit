"""hor.cert — Certificate builder, F_cert, BLAKE3/Ed25519, classification matrix.

A HOR claim only counts if three things close at once (v0.1 §10):

    V[G] |= phi  <==>  exists p in G, p |= phi
                    AND F_cert(G) >= 0.999
                    AND BLAKE3(p |= phi) signed

v0.1 wrote this as an *iff* mixing set theory, a number, and a hash — a
type error. v0.1.5 fixes it as a Sigma-type (v0.1.5 §10, v0.2 §9):

    Certificate = Sigma (p: P) (phi: Formula)
                      (proof: p |= phi)
                      (f_cert: R)
                      (f_ok: f_cert >= 0.999)
                      (sig: Signature(manifest p phi f_cert))
                      (sig_ok: Verify sig)

Each component is independently verified. The certificate also carries
the classification matrix (E209) and TRL label (E203) from the HOR-Qudit
extension pack.

Cryptographic primitives (E191-E200):
    - BLAKE3 (integrity, ~GB/s)
    - Ed25519 / ML-DSA-65 (signatures)
    - Merkle tree (state commitment, O(log N) proof per chunk)
    - Hash-chained append-only ledger (tamper-evident run log)
"""

from __future__ import annotations

from .certificate import (
    Certificate,
    CertificateBuilder,
    compute_f_cert,
    classification,
    TRL,
    Classification,
)
from .crypto import (
    blake3_hash,
    ed25519_sign,
    ed25519_verify,
    canonical_json,
    merkle_root,
    merkle_proof,
)
from .forcing import ForcingProof, check_forcing_proof
from .ledger import RunLedger, LedgerEntry

__all__ = [
    "Certificate",
    "CertificateBuilder",
    "compute_f_cert",
    "classification",
    "TRL",
    "Classification",
    "blake3_hash",
    "ed25519_sign",
    "ed25519_verify",
    "canonical_json",
    "merkle_root",
    "merkle_proof",
    "ForcingProof",
    "check_forcing_proof",
    "RunLedger",
    "LedgerEntry",
]
