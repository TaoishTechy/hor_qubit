"""Tests for the gate engine: matrices, Clifford classification, costs."""

from __future__ import annotations

import math

import numpy as np
import pytest

from hor.gates.gates import (
    Gate,
    gate_matrix,
    is_clifford,
    GATES,
    T_STATE_EXTENT,
    apply_gate_to_state,
)
from hor.core.state import make_vacuum


def test_h_matrix_unitary():
    """H is unitary."""
    H = gate_matrix("h")
    assert np.allclose(H @ H.conj().T, np.eye(2))


def test_cnot_matrix_unitary():
    """CNOT is unitary."""
    U = gate_matrix("cnot")
    assert np.allclose(U @ U.conj().T, np.eye(4))


def test_t_state_extent():
    """Stabilizer extent of |T> = cos^{-2}(pi/8) ~ 1.1716 (Bravyi et al.)."""
    expected = 1.0 / (math.cos(math.pi / 8) ** 2)
    assert T_STATE_EXTENT == pytest.approx(expected, rel=1e-6)
    assert T_STATE_EXTENT == pytest.approx(1.1716, rel=1e-3)


def test_clifford_classification():
    """Clifford gates are correctly identified."""
    assert is_clifford(Gate(name="h", targets=(0,)))
    assert is_clifford(Gate(name="s", targets=(0,)))
    assert is_clifford(Gate(name="cnot", targets=(0, 1)))
    assert is_clifford(Gate(name="cz", targets=(0, 1)))
    # T is not Clifford
    assert not is_clifford(Gate(name="t", targets=(0,)))
    # RX(pi) is Clifford (X up to phase)
    assert is_clifford(Gate(name="rx", targets=(0,), params=(math.pi,)))
    # RX(0.3) is not Clifford
    assert not is_clifford(Gate(name="rx", targets=(0,), params=(0.3,)))


def test_gate_set_completeness():
    """v0.1.5 expanded gate set is available (fixes A6-65, A7-81/82)."""
    required = {"h", "s", "x", "y", "z", "sqrtx", "t",
                "cnot", "cz", "iswap", "sqrtiswap",
                "rx", "ry", "rz", "u3",
                "toffoli", "xx", "yy", "zz", "ms"}
    assert required.issubset(set(GATES.keys()))


def test_apply_gate_to_state_bell():
    """Apply H(0) then CNOT(0,1) to |00> yields Bell state |00> + |11>."""
    state = make_vacuum(n=2)
    state.rho_2 = apply_gate_to_state(state.rho_2, Gate(name="h", targets=(0,)))
    state.rho_2 = apply_gate_to_state(state.rho_2, Gate(name="cnot", targets=(0, 1)))
    # Probabilities should be 0.5 for |00> and 0.5 for |11>
    probs = state.probabilities()
    assert probs[0] == pytest.approx(0.5, abs=1e-10)
    assert probs[3] == pytest.approx(0.5, abs=1e-10)
    assert probs[1] == pytest.approx(0.0, abs=1e-10)
    assert probs[2] == pytest.approx(0.0, abs=1e-10)


def test_cost_tracking_sim_vs_ft():
    """Cost tracking separates classical sim cost from fault-tolerant cost (A7-74).

    v0.1.5 §6: T is 10-100x more expensive than Clifford in FT accounting.
    In classical simulation, all 1Q gates have similar cost.
    """
    h_gate = Gate(name="h", targets=(0,))
    t_gate = Gate(name="t", targets=(0,))
    toffoli = Gate(name="toffoli", targets=(0, 1, 2))
    # In classical simulation, all single-qubit gates have similar cost
    assert h_gate.cost_sim == t_gate.cost_sim
    # In fault-tolerant hardware, T is much more expensive (10x Clifford)
    assert t_gate.cost_ft > h_gate.cost_ft
    # Toffoli decomposes to 4 T gates = 40 T-equivalents
    assert toffoli.cost_ft == 4 * t_gate.cost_ft


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
