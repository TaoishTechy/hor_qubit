"""QAOA MaxCut example on a 4-node cycle graph.

QAOA with 2 layers:
    - Cost Hamiltonian: H_C = sum_{(i,j)} Z_i Z_j (MaxCut on cycle C_4)
    - Mixer Hamiltonian: H_M = sum_i X_i
    - Parameters: gamma = [0.3, 0.4], beta = [0.2, 0.1]

Demonstrates:
    - Parameterized gates (RZ, RX)
    - Non-Clifford circuit -> R1 statevector backend
    - Variational algorithm structure
"""

from __future__ import annotations

import math

from hor import HORQubit, CertifyConfig


def main() -> None:
    print("=== QAOA MaxCut on C_4 ===")
    n = 4
    # C_4 edges: (0,1), (1,2), (2,3), (3,0)
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]
    gammas = [0.3, 0.4]
    betas = [0.2, 0.1]
    p = 2  # number of QAOA layers

    q = HORQubit(n=n, chi_max=64)
    # Initial state: |+>^n
    for i in range(n):
        q.h(i)
    # QAOA layers
    for layer in range(p):
        # Cost unitary: exp(-i gamma * H_C) = prod exp(-i gamma/2 Z_i Z_j)
        for (i, j) in edges:
            q.cnot(i, j)
            q.rz(2 * gammas[layer], j)  # Z_j rotation by 2*gamma
            q.cnot(i, j)
        # Mixer unitary: exp(-i beta * H_M) = prod exp(-i beta X_i) = RX(2*beta)
        for i in range(n):
            q.rx(2 * betas[layer], i)
    q.hor_certify(CertifyConfig(shots=2048, target_delta=0.001, target_eps=0.01))
    result = q.run(seed=11)
    print(f"Backend:    {result.backend}")
    print(f"Status:     {result.status}")
    print(f"Reason:     {result.reason}")
    if result.certificate:
        print(f"F_cert:     {result.certificate.f_cert:.6f}")
        print(f"t_count:    {result.certificate.resource_budgets.t_count}")
        print(f"magic_extent: {result.certificate.resource_budgets.stabilizer_extent:.4f}")
    # Top 4 outcomes
    sorted_counts = sorted(result.counts.items(), key=lambda x: -x[1])[:4]
    print(f"\nTop 4 outcomes:")
    for bitstring, count in sorted_counts:
        print(f"  {bitstring}: {count} ({count/sum(result.counts.values()):.3f})")


if __name__ == "__main__":
    main()
