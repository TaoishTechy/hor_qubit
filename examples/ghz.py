"""GHZ state example.

GHZ-N: ``H_0`` then ``CNOT(0, k)`` for ``k = 1..N-1``.

Demonstrates:
    - Multi-qubit entanglement
    - Stabilizer simulation (R4) for Clifford-only circuits
    - Backwards compatibility: stripping hor. pragmas leaves a valid
      standard program
"""

from __future__ import annotations

from hor import HORQubit, CertifyConfig


def main() -> None:
    print("=== GHZ-4 state example ===")
    n = 4
    q = HORQubit(n=n, chi_max=64)
    q.h(0)
    for k in range(1, n):
        q.cnot(0, k)
    q.hor_certify(CertifyConfig(shots=2048, target_delta=0.001, target_eps=0.001))
    result = q.run(seed=7)
    print(f"Counts:     {result.counts}")
    print(f"Backend:    {result.backend}")
    print(f"Status:     {result.status}")
    if result.certificate:
        print(f"F_cert:     {result.certificate.f_cert:.6f}")
    # Expected: ~50% 0000, ~50% 1111
    total = sum(result.counts.values())
    p0000 = result.counts.get("0" * n, 0) / total
    p1111 = result.counts.get("1" * n, 0) / total
    print(f"\nExpected GHZ-{n}: p({'0'*n}) ~ 0.5, p({'1'*n}) ~ 0.5")
    print(f"Got:             p({'0'*n}) = {p0000:.3f}, p({'1'*n}) = {p1111:.3f}")


if __name__ == "__main__":
    main()
