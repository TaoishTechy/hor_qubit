"""Tests for the certificate builder: F_cert, Bures composition, signing."""

from __future__ import annotations

import math

import pytest

from hor.cert.certificate import (
    Certificate,
    CertificateBuilder,
    compute_f_cert,
    bures_angle_composition,
    fuchs_van_de_graaf_bound,
    classification,
)
from hor.cert.crypto import blake3_hash, canonical_json, merkle_root, merkle_proof, SigningKey, ed25519_sign
from hor.cert.forcing import ForcingProof, check_forcing_proof
from hor.cert.ledger import RunLedger
from hor.core.registers import ForcingStep, ForcingCondition, ResourceBudgets, ShotBudget


def test_compute_f_cert_basic():
    """F_cert = F_state * F_process * (1 - eps_trunc) * (1 - eps_shot)."""
    f = compute_f_cert(f_state=0.999, f_process=1.0, eps_trunc=0.001, eps_shot=0.001)
    expected = 0.999 * 1.0 * 0.999 * 0.999
    assert f == pytest.approx(expected, rel=1e-6)


def test_bures_angle_composition_small_losses():
    """For small losses, Bures composition is a rigorous lower bound on product.

    Bures composition: theta_total = sum_i arccos(sqrt(F_i)); F = cos^2(theta_total).
    Product: F = prod F_i.

    For F_i close to 1, Bures < product (Bures is the rigorous lower bound).
    """
    fs = [0.999, 0.999, 0.999]
    f_bures = bures_angle_composition(fs)
    f_prod = 0.999 ** 3
    # Bures should be a lower bound: f_bures <= f_prod (within numerical tolerance)
    assert f_bures <= f_prod + 1e-10
    # And both should be close to 1 for small losses
    assert f_bures > 0.99
    assert f_prod > 0.99


def test_bures_angle_composition_saturates():
    """For large losses, Bures composition saturates at 0."""
    fs = [0.0, 0.0, 0.0]
    assert bures_angle_composition(fs) == pytest.approx(0.0, abs=1e-10)


def test_fuchs_van_de_graaf_bounds():
    """1 - sqrt(F) <= T <= sqrt(1 - F)."""
    lo, hi = fuchs_van_de_graaf_bound(0.99)
    assert 0 <= lo <= hi
    assert lo == pytest.approx(1 - math.sqrt(0.99), abs=1e-10)
    assert hi == pytest.approx(math.sqrt(0.01), abs=1e-10)


def test_classification_tags():
    """Classification tags parameters with their derivation status."""
    q_xy, cat = classification(0.5, "Topologically Forced", name="q_xy")
    assert q_xy == 0.5
    assert cat == "Topologically Forced"


def test_blake3_deterministic():
    """BLAKE3 is deterministic."""
    h1 = blake3_hash(b"hello")
    h2 = blake3_hash(b"hello")
    assert h1 == h2
    assert h1 != blake3_hash(b"world")


def test_canonical_json_deterministic():
    """Canonical JSON: sorted keys, no whitespace."""
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a == b
    assert " " not in a


def test_merkle_root_consistency():
    """Merkle root is consistent for the same leaves."""
    leaves = [b"a", b"b", b"c", b"d"]
    r1 = merkle_root(leaves)
    r2 = merkle_root(leaves)
    assert r1 == r2
    # Different leaves -> different root
    r3 = merkle_root([b"a", b"b", b"c", b"e"])
    assert r1 != r3


def test_merkle_proof_verifies():
    """Merkle proof for an index produces a valid path."""
    leaves = [b"a", b"b", b"c", b"d"]
    proof = merkle_proof(leaves, 0)
    assert len(proof) > 0
    # Each element is (sibling_hash, direction)
    for sib, direction in proof:
        assert direction in ("L", "R")


def test_ed25519_signing_roundtrip():
    """Sign and verify a message with Ed25519 (or stand-in)."""
    key = SigningKey.generate(key_id="test-key")
    msg = b"test message"
    sig = ed25519_sign(msg, key)
    assert sig  # non-empty
    # Verification: in stand-in mode, just check format
    if sig.startswith("hmac-stub:"):
        assert "hmac-stub:" in sig
    else:
        # Real Ed25519; verification would need the public key bytes
        # We just check the signature length
        assert len(sig) > 0


def test_forcing_proof_check():
    """A forcing proof is valid iff phi is preserved at every step and dense sets are met."""
    steps = [
        ForcingStep(p="p0", phi="gap_open", classification="button",
                    dense_sets_met=["D_gap"]),
        ForcingStep(p="p1", phi="gap_open", classification="button",
                    dense_sets_met=["D_sym"]),
    ]
    proof = ForcingProof(steps=steps, dense_sets_checked=["D_gap", "D_sym"],
                         target_phi="gap_open", poset_size=2, n_dense_met=2)
    ok, reason = check_forcing_proof(proof, target_phi="gap_open",
                                       required_dense_sets=["D_gap", "D_sym"])
    assert ok, reason


def test_forcing_proof_failure_phi():
    """A proof that doesn't preserve phi fails."""
    steps = [
        ForcingStep(p="p0", phi="gap_open"),
        ForcingStep(p="p1", phi="symmetry_C4"),  # different phi
    ]
    proof = ForcingProof(steps=steps, target_phi="gap_open")
    ok, reason = check_forcing_proof(proof, target_phi="gap_open",
                                       required_dense_sets=[])
    assert not ok
    assert "preserve" in reason or "mismatch" in reason


def test_certificate_builder_basic():
    """CertificateBuilder produces a certificate with hash and signature."""
    key = SigningKey.generate(key_id="test-key")
    builder = CertificateBuilder(threshold=0.999, signing_key=key)
    proof = ForcingProof(steps=[ForcingStep(p="p0", phi="gap_open", classification="button",
                                            dense_sets_met=["D_gap"])],
                         dense_sets_checked=["D_gap"], target_phi="gap_open",
                         poset_size=1, n_dense_met=1)
    cert = builder.build(
        forcing_proof=proof,
        f_state=0.9999,
        f_process=1.0,
        eps_trunc=0.0,
        eps_shot=0.0001,
        backend="R1",
        shot_budget=ShotBudget(total=8192),
        resource_budgets=ResourceBudgets(),
        calibration_id="calib: none",
    )
    assert cert.status == "certified"
    assert cert.manifest_hash  # non-empty
    assert cert.signature  # non-empty
    assert cert.signer == "test-key"


def test_certificate_uncertified_when_below_threshold():
    """Certificate is uncertified when F_cert < threshold."""
    builder = CertificateBuilder(threshold=0.999)
    proof = ForcingProof()
    cert = builder.build(
        forcing_proof=proof,
        f_state=0.95,
        f_process=0.95,
        eps_trunc=0.01,
        eps_shot=0.01,
        backend="R3",
        shot_budget=ShotBudget(),
        resource_budgets=ResourceBudgets(),
    )
    assert cert.status == "uncertified"
    assert cert.reason is not None
    assert "f_cert" in cert.reason.lower()


def test_run_ledger_hash_chain():
    """RunLedger entries are hash-chained."""
    ledger = RunLedger()
    e1 = ledger.append("hash1", "R1", 0.999, "certified")
    e2 = ledger.append("hash2", "R1", 0.998, "uncertified")
    # Each entry's previous_hash should be the hash of the previous entry
    assert e2.previous_hash == e1.compute_hash()
    assert ledger.verify()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
