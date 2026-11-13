"""HOR-Qudit extension lane example.

Demonstrates the *real* math backends from the HOR-Qudit extension pack:
    - Sheaf cohomology H^1 obstruction detection (E145-E148)
    - Persistent homology barcode syndrome (E149-E153)
    - HOTI nested Wilson loop (E154-E158)
    - Transfer operator Lyapunov exponents (E159-E162)
    - QES island-formula generalized entropy (E163-E166)

Explicitly rejected (NOT demonstrated, because they are fictional):
    - Sophia Point as physical attractor
    - ERD field as physical scalar
    - 420M entangled qudits
    - Love field, miracle operator, consciousness collapse
"""

from __future__ import annotations

import numpy as np

from hor import (
    SheafBackend,
    BarcodeBackend,
    HOTIBackend,
    TransferOperatorBackend,
    QESBackend,
)
from hor.core.registers import CellularSheaf


def main() -> None:
    print("=== HOR-Qudit extension lane (real math only) ===\n")

    # 1. Sheaf backend
    print("1. Sheaf cohomology (E145-E148)")
    backend = SheafBackend()
    # Build a cycle graph C_4: 4 vertices, 4 edges
    sheaf = CellularSheaf(n_vertices=4, n_edges=0, stalk_dim=1)
    for i in range(4):
        sheaf.add_edge(i, i, (i + 1) % 4)
    diag = backend.diagnose(sheaf)
    print(f"   Spectral gap lambda_1: {diag['lambda_1']:.4f}")
    print(f"   H^1 dimension:         {diag['h1_dim']}")
    print(f"   Should escalate:       {diag['should_escalate']}")
    print(f"   TRL:                   {diag['trl']}\n")

    # 2. Barcode backend
    print("2. Persistent homology barcode (E149-E153)")
    backend = BarcodeBackend()
    # Defect point cloud: 5 points in a line
    defects = np.array([0.0, 0.5, 1.0, 5.0, 10.0])
    diag = backend.diagnose(defects)
    print(f"   N defects:             {diag['n_defects']}")
    print(f"   N bars:                {diag['n_bars']}")
    print(f"   Long bars:             {diag['long_bars']}")
    print(f"   Persistence entropy:   {diag['persistence_entropy']:.4f}")
    print(f"   Tree query complexity: {diag['tree_query_complexity']}\n")

    # 3. HOTI backend
    print("3. HOTI nested Wilson loop (E154-E158)")
    backend = HOTIBackend()
    diag = backend.diagnose(L=8, gamma=0.5, lam=1.0)
    print(f"   Quadrupole q_xy:       {diag['q_xy']}")
    print(f"   Classification:        {diag['classification']}")
    print(f"   Corner modes:          {diag['corner_mode_count']}")
    print(f"   Topological:           {diag['topological']}\n")

    # 4. Transfer operator
    print("4. Transfer operator Lyapunov (E159-E162)")
    backend = TransferOperatorBackend()
    # Jacobian of a 2D map
    J = np.array([[0.5, 0.3], [-0.2, 0.8]])
    diag = backend.diagnose(J)
    print(f"   chi_max (Lyapunov):    {diag['chi_max']:.4f}")
    print(f"   Chaotic:               {diag['chaotic']}")
    print(f"   Stable dim:            {diag['oseledets_dim_stable']}")
    print(f"   Unstable dim:          {diag['oseledets_dim_unstable']}")
    print(f"   Shadowing applies:     {diag['shadowing_applies']}\n")

    # 5. QES backend
    print("5. QES island-formula (E163-E166)")
    backend = QESBackend()
    diag = backend.diagnose(area_boundary=4.0, gn0=1.0, bulk_entropy=0.5,
                             erd_scalar=0.0, t2=1.0)
    print(f"   S_gen:                 {diag['s_gen']:.4f}")
    print(f"   Area term:             {diag['area_term']:.4f}")
    print(f"   Bulk term:             {diag['bulk_term']:.4f}")
    print(f"   G_N effective:         {diag['gn_effective']:.4f}")
    print(f"   Page time:             {diag['page_time']:.4f}")


if __name__ == "__main__":
    main()
