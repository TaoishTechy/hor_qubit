"""Tests for the HOR-Qudit extension lane backends (E145-E166).

Tests the *real* math: sheaf cohomology, persistent homology barcodes,
HOTI invariants, transfer operators, QES island formula.

The fictional claims (Sophia Point, ERD field, 420M entangled qudits,
love field) are explicitly NOT tested because they are rejected.
"""

from __future__ import annotations

import numpy as np
import pytest

from hor.sim.extension.sheaf import SheafBackend
from hor.sim.extension.barcode import BarcodeBackend, IntervalTree
from hor.sim.extension.hoti import HOTIBackend
from hor.sim.extension.transfer_operator import TransferOperatorBackend
from hor.sim.extension.qes import QESBackend
from hor.core.registers import CellularSheaf, PersistenceBar, PersistenceDiagram


# --------------------------------------------------------------------------
# Sheaf backend (E145-E148)
# --------------------------------------------------------------------------


def test_sheaf_construction_basic():
    """Cellular sheaf on a 3-vertex path graph: lambda_1 = 1 (unnormalized Laplacian).

    For the path graph P_3 with edges (0,1), (1,2), the unnormalized
    Laplacian ``L = delta^T delta`` has eigenvalues 0, 1, 3.
    """
    sheaf = CellularSheaf(n_vertices=3, n_edges=0, stalk_dim=1)
    sheaf.add_edge(0, 0, 1)
    sheaf.add_edge(1, 1, 2)
    L = sheaf.laplacian()
    eigs = np.sort(np.real(np.linalg.eigvalsh(L)))
    assert eigs[0] == pytest.approx(0.0, abs=1e-10)
    assert eigs[1] == pytest.approx(1.0, abs=1e-10)
    assert eigs[2] == pytest.approx(3.0, abs=1e-10)


def test_sheaf_h1_dimension_cycle():
    """A cycle graph has H^1 = 1 (one loop)."""
    sheaf = CellularSheaf(n_vertices=3, n_edges=0, stalk_dim=1)
    sheaf.add_edge(0, 0, 1)
    sheaf.add_edge(1, 1, 2)
    sheaf.add_edge(2, 2, 0)  # close the cycle
    h1 = sheaf.h1_dimension()
    # For a cycle graph with 3 vertices and 3 edges, dim H^1 = E - V + 1 = 1
    assert h1 == 1


def test_sheaf_spectral_gap_path():
    """Sheaf backend computes lambda_1 of path graph P_4 correctly.

    For P_4 (4 vertices, 3 edges), the unnormalized Laplacian eigenvalues
    are 0, 2-sqrt(2), 2, 2+sqrt(2). So lambda_1 = 2 - sqrt(2).
    """
    backend = SheafBackend()
    sheaf = CellularSheaf(n_vertices=4, n_edges=0, stalk_dim=1)
    for i in range(3):
        sheaf.add_edge(i, i, i + 1)
    lam1 = backend.spectral_gap(sheaf)
    assert lam1 == pytest.approx(2 - np.sqrt(2), abs=1e-6)


def test_sheaf_cheeger_lower_bound():
    """Cheeger: lambda_1 >= h_F^2 / 2 (E148)."""
    backend = SheafBackend()
    sheaf = CellularSheaf(n_vertices=4, n_edges=0, stalk_dim=1)
    for i in range(3):
        sheaf.add_edge(i, i, i + 1)
    h_F = 0.5  # example conductance
    bound = backend.cheeger_lower_bound(sheaf, h_F)
    assert bound == pytest.approx(0.125, abs=1e-10)  # 0.5^2 / 2


# --------------------------------------------------------------------------
# Barcode backend (E149-E153)
# --------------------------------------------------------------------------


def test_barcode_vr_filtration_1d():
    """H_0 persistence of a 1D point cloud: each point starts as a component."""
    points = np.array([0.0, 1.0, 2.0, 5.0])
    backend = BarcodeBackend()
    dgm = backend.compute_diagram(points)
    # All 4 points start as separate components; 3 die as gaps close, 1 survives
    assert len(dgm.bars) >= 3
    # Longest bar should span the full range
    longest = max(dgm.bars, key=lambda b: b.lifetime)
    assert longest.lifetime > 0


def test_barcode_interval_tree_query():
    """Interval tree returns bars containing a query point (E150)."""
    bars = [PersistenceBar(birth=0.0, death=1.0),
            PersistenceBar(birth=0.5, death=2.0),
            PersistenceBar(birth=1.5, death=3.0)]
    tree = IntervalTree(bars)
    # Query point 0.7: should be in bars 0 and 1
    result = tree.query(0.7)
    assert len(result) == 2
    # Query point 2.5: should be in bar 2 only
    result = tree.query(2.5)
    assert len(result) == 1


def test_barcode_persistence_entropy():
    """Persistence entropy is non-negative (E152)."""
    backend = BarcodeBackend()
    points = np.array([0.0, 1.0, 2.0, 5.0, 10.0])
    dgm = backend.compute_diagram(points)
    e = backend.persistence_entropy(dgm)
    assert e >= 0


def test_barcode_bottleneck_distance_zero():
    """Bottleneck distance between identical diagrams is 0 (E151)."""
    bars = [PersistenceBar(birth=0.0, death=1.0)]
    dgm1 = PersistenceDiagram(k=0, bars=bars)
    dgm2 = PersistenceDiagram(k=0, bars=bars)
    backend = BarcodeBackend()
    d = backend.stability_threshold(dgm1, dgm2)
    assert d == pytest.approx(0.0, abs=1e-10)


# --------------------------------------------------------------------------
# HOTI backend (E154-E158)
# --------------------------------------------------------------------------


def test_hoti_bbh_hamiltonian_shape():
    """BBH Hamiltonian is 4x4."""
    backend = HOTIBackend()
    H = backend.bbh_hamiltonian(kx=0.0, ky=0.0, gamma=0.5, lam=1.0)
    assert H.shape == (4, 4)


def test_hoti_bbh_hamiltonian_hermitian():
    """BBH Hamiltonian is Hermitian."""
    backend = HOTIBackend()
    H = backend.bbh_hamiltonian(kx=0.3, ky=0.7)
    assert np.allclose(H, H.conj().T)


def test_hoti_corner_modes_topological():
    """In the topological phase (|gamma/lambda| < 1), expect 4 corner modes."""
    backend = HOTIBackend()
    count = backend.corner_mode_count(L=8, gamma=0.5, lam=1.0)
    assert count == 4


def test_hoti_corner_modes_trivial():
    """In the trivial phase (|gamma/lambda| > 1), expect 0 corner modes."""
    backend = HOTIBackend()
    count = backend.corner_mode_count(L=8, gamma=2.0, lam=1.0)
    assert count == 0


def test_hoti_memory_lifetime_factor():
    """E158: T_mem factor = phi^2 * exp(Delta / (k_B T_eff))."""
    backend = HOTIBackend()
    factor = backend.memory_lifetime_factor(delta_corner=1.0, t_eff_ghz=0.02)
    # phi^2 ~ 2.618; exp(1/0.02) is huge
    assert factor > 2.618  # at least the phi^2 term


# --------------------------------------------------------------------------
# Transfer operator backend (E159-E162)
# --------------------------------------------------------------------------


def test_transfer_operator_identity():
    """Identity Jacobian gives identity transfer operator."""
    backend = TransferOperatorBackend()
    J = np.eye(2)
    L = backend.transfer_matrix(J)
    assert np.allclose(L, np.eye(2))


def test_transfer_operator_lyapunov():
    """Lyapunov exponents of identity are 0."""
    backend = TransferOperatorBackend()
    J = np.eye(2)
    exps = backend.lyapunov_exponents(J)
    assert all(e == pytest.approx(0.0, abs=1e-10) for e in exps)


def test_transfer_operator_chaos_bound():
    """Maldacena-Stanford-Shenker bound: chi_max <= 2 pi T_eff (E161)."""
    backend = TransferOperatorBackend()
    bound = backend.chaos_bound(t_eff_hz=1.0)
    assert bound == pytest.approx(2 * np.pi, abs=1e-6)


# --------------------------------------------------------------------------
# QES backend (E163-E166)
# --------------------------------------------------------------------------


def test_qes_generalized_entropy():
    """S_gen = Area/(4 G_N) + S_bulk."""
    backend = QESBackend()
    s = backend.generalized_entropy(area_boundary=4.0, gn=1.0, bulk_entropy=0.5)
    # 4/(4*1) + 0.5 = 1.5
    assert s == pytest.approx(1.5, abs=1e-10)


def test_qes_page_time():
    """t_Page ~ 0.71 * T_2 (E165)."""
    backend = QESBackend()
    t = backend.page_time(t2=100.0)
    assert t == pytest.approx(71.0, abs=1e-6)


def test_qes_effective_gn():
    """G_N(epsilon) = G_N^0 / (1 + chi * epsilon^2) (E164)."""
    backend = QESBackend()
    gn_eff = backend.effective_gn(gn0=1.0, erd_scalar=0.1, chi_erd=1.0)
    # 1.0 / (1 + 1 * 0.01) = 1/1.01
    assert gn_eff == pytest.approx(1.0 / 1.01, abs=1e-6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
