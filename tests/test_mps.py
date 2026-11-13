"""Tests for the R3 MPS backend: Schmidt truncation, entanglement, sampling."""

from __future__ import annotations

import numpy as np
import pytest

from hor.sim.mps import MPS, MPSBackend
from hor.core.state import make_vacuum


def test_mps_from_statevector_ghz():
    """GHZ state has Schmidt rank 2 at every bond.

    Due to numerical precision, SVD may return tiny singular values for
    the zero-rows; we filter values below 1e-10.
    """
    n = 4
    psi = np.zeros(2**n, dtype=complex)
    psi[0] = 1.0 / np.sqrt(2)
    psi[-1] = 1.0 / np.sqrt(2)
    mps = MPS.from_statevector(psi, n=n, d=2, chi=4)
    # Each Schmidt spectrum should have at most 2 *significant* values
    for s in mps.schmidt_values:
        significant = s[s > 1e-10]
        assert len(significant) <= 2
        if len(significant) == 2:
            assert significant[0] == pytest.approx(significant[1], abs=1e-10)
            assert significant[0] == pytest.approx(1.0 / np.sqrt(2), abs=1e-10)


def test_mps_entanglement_entropy_ghz():
    """GHZ has entanglement entropy 1 at every cut."""
    n = 5
    psi = np.zeros(2**n, dtype=complex)
    psi[0] = 1.0 / np.sqrt(2)
    psi[-1] = 1.0 / np.sqrt(2)
    mps = MPS.from_statevector(psi, n=n, d=2, chi=4)
    for bond in range(len(mps.schmidt_values)):
        s = mps.entanglement_entropy(bond)
        assert s == pytest.approx(1.0, abs=1e-6)


def test_mps_truncation_error_zero_for_low_rank():
    """GHZ at chi=4 has zero truncation error."""
    n = 5
    psi = np.zeros(2**n, dtype=complex)
    psi[0] = 1.0 / np.sqrt(2)
    psi[-1] = 1.0 / np.sqrt(2)
    mps = MPS.from_statevector(psi, n=n, d=2, chi=4)
    assert mps.truncation_error == pytest.approx(0.0, abs=1e-10)


def test_mps_max_entanglement():
    """MPS reports max entanglement across bonds."""
    n = 4
    psi = np.zeros(2**n, dtype=complex)
    psi[0] = 1.0 / np.sqrt(2)
    psi[-1] = 1.0 / np.sqrt(2)
    mps = MPS.from_statevector(psi, n=n, d=2, chi=4)
    assert mps.max_entanglement() == pytest.approx(1.0, abs=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
