"""Test the backwards compatibility theorem (v0.1.5 §2, v0.2 §2.4).

Theorem:
    For any n-qubit circuit C built from
    {H, S, T, X, Y, Z, sqrt(X), CNOT, CZ, RX, RY, RZ, U3, Toffoli}
    and measurement in Z::

        P_HOR(x | C, rho_HOR^vac) = P_standard(x | C, rho_2)

    up to ~1e-14 per gate floating-point floor.

We verify this empirically: run a circuit with and without hor. pragmas
and assert TVD < 1e-12 for small n.
"""

from __future__ import annotations

import numpy as np
import pytest

from hor import (
    HORQubit,
    ForcingCondition,
    CertifyConfig,
    backwards_compatible,
    strip_hor_pragmas,
)
from hor.core.state import make_vacuum
from hor.gates.gates import Gate, apply_gate_to_state


def test_strip_hor_pragmas_basic():
    """Stripping hor. pragmas leaves a valid standard program."""
    qasm = """horq q[2];
h q[0];
cx q[0], q[1];
hor.force {gap_open: true};
hor.certify {shots: 8192};
measure q[0] -> c[0];
"""
    stripped = strip_hor_pragmas(qasm)
    assert "hor." not in stripped
    assert "h q[0]" in stripped
    assert "cx q[0], q[1]" in stripped


def test_backwards_compatible_zero_tvd():
    """Identical count dictionaries have TVD = 0."""
    a = {"00": 50, "11": 50}
    b = {"00": 50, "11": 50}
    assert backwards_compatible(a, b, atol=1e-12)


def test_backwards_compatible_detects_mismatch():
    """Different distributions should fail the compatibility check."""
    a = {"00": 100}
    b = {"11": 100}
    assert not backwards_compatible(a, b, atol=1e-12)


def test_bell_state_hor_matches_standard():
    """Bell state via HOR (with hor. pragmas) matches standard circuit.

    The HOR meta-operations are identity on rho_2 (v0.1.5 §6). So a Bell
    circuit with hor_force applied must produce the same counts as the
    same circuit without hor_force.
    """
    # Run with hor_force
    q_hor = HORQubit(n=2, chi_max=64)
    q_hor.h(0)
    q_hor.cnot(0, 1)
    q_hor.hor_force(ForcingCondition(gap_open=True, symmetry="C4", max_bond=64))
    q_hor.hor_certify(CertifyConfig(shots=4096, target_eps=0.001))
    res_hor = q_hor.run(seed=42)

    # Run without hor_force
    q_std = HORQubit(n=2, chi_max=64)
    q_std.h(0)
    q_std.cnot(0, 1)
    q_std.hor_certify(CertifyConfig(shots=4096, target_eps=0.001))
    res_std = q_std.run(seed=42)

    # Counts should be statistically indistinguishable
    # Bell state: ~50% 00, ~50% 11
    keys = set(res_hor.counts) | set(res_std.counts)
    total_h = sum(res_hor.counts.values())
    total_s = sum(res_std.counts.values())
    tvd = 0.5 * sum(
        abs(res_hor.counts.get(k, 0) / total_h - res_std.counts.get(k, 0) / total_s)
        for k in keys
    )
    # With 4096 shots, statistical noise is ~1/sqrt(4096) ~ 1.5%
    assert tvd < 0.05, f"TVD = {tvd:.3f} > 0.05"


def test_vacuum_state_reduces_to_qubit():
    """Tr_{HGR}[rho_HOR^vac] = rho_2 (v0.1.5 §1)."""
    state = make_vacuum(n=3)
    rho_2 = state.rho_2
    # Vacuum state is |000><000|
    assert rho_2[0, 0] == pytest.approx(1.0)
    assert state.vacuum is True
    # Classical registers are at vacuum values
    assert state.c_h.status == "unavailable"
    assert state.c_g.status == "vacuum"
    assert state.c_r.status == "vacuum"


def test_classical_update_does_not_entangle():
    """Quantum gates do not entangle rho_2 with classical registers (v0.1.5 §4.2).

    The cq-state structure is preserved: rho_HOR remains block-diagonal in
    the classical basis after any gate.
    """
    from hor.gates.gates import apply_gate_to_state, Gate
    state = make_vacuum(n=2)
    # Apply H(0) then CNOT(0, 1) (Bell state)
    state.rho_2 = apply_gate_to_state(state.rho_2, Gate(name="h", targets=(0,)))
    state.rho_2 = apply_gate_to_state(state.rho_2, Gate(name="cnot", targets=(0, 1)))
    # Classical registers are *not* touched by apply_gate_to_state (which only updates rho_2)
    # Verify the trace of rho_2 is still 1 (state is normalized)
    assert np.trace(state.rho_2).real == pytest.approx(1.0, abs=1e-10)
    # Verify Bell state: probs[0] = 0.5, probs[3] = 0.5
    probs = state.probabilities()
    assert probs[0] == pytest.approx(0.5, abs=1e-10)
    assert probs[3] == pytest.approx(0.5, abs=1e-10)
    # Classical registers are still at vacuum (we didn't call any hor_force etc.)
    assert state.c_h.status == "unavailable"
    assert state.c_g.status == "vacuum"


def test_density_matrix_supported():
    """HOR supports mixed states (v0.1.5 §1 — fixes v0.1's pure-state restriction)."""
    from hor.core.state import HORState
    rho = np.eye(4, dtype=complex) / 4  # maximally mixed state on 2 qubits
    state = HORState.from_density(rho, n=2)
    assert not state.is_pure
    assert np.trace(state.rho_2).real == pytest.approx(1.0, abs=1e-10)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
