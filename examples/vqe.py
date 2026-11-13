"""VQE H2 example (2 qubits, hardware-efficient ansatz).

H2 Hamiltonian (STO-3G, frozen core, in the parity mapping):

    H = c_0 I + c_1 Z_0 + c_2 Z_1 + c_3 X_0 X_1 + c_4 Y_0 Y_1 + c_5 Z_0 Z_1

This is a minimal VQE demonstration. The full VQE loop (optimization)
is left as an exercise; this example just runs the ansatz at one set of
parameters and reports the counts.
"""

from __future__ import annotations

import math

from hor import HORQubit, CertifyConfig


def main() -> None:
    print("=== VQE H2 example (2 qubits) ===")
    n = 2
    # Hardware-efficient ansatz: RZ(theta_0) RX(theta_1) RZ(theta_2) on each qubit,
    # then CNOT(0, 1), then another layer.
    theta = [0.5, 0.3, 0.7, 0.2, 0.6, 0.1]

    q = HORQubit(n=n, chi_max=64)
    # Layer 1
    q.rz(theta[0], 0)
    q.rx(theta[1], 0)
    q.rz(theta[2], 1)
    q.rx(theta[3], 1)
    q.cnot(0, 1)
    # Layer 2
    q.rz(theta[4], 0)
    q.rx(theta[5], 1)
    q.hor_certify(CertifyConfig(shots=8192, target_delta=0.001, target_eps=0.005))
    result = q.run(seed=23)
    print(f"Backend:    {result.backend}")
    print(f"Status:     {result.status}")
    if result.certificate:
        print(f"F_cert:     {result.certificate.f_cert:.6f}")
    # H2 ground state is roughly |00>
    total = sum(result.counts.values())
    p00 = result.counts.get("00", 0) / total
    print(f"\np(00) = {p00:.3f}")
    print(f"Top outcomes:")
    for bitstring, count in sorted(result.counts.items(), key=lambda x: -x[1])[:4]:
        print(f"  {bitstring}: {count} ({count/total:.3f})")


if __name__ == "__main__":
    main()
