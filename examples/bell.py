"""Bell state example.

Demonstrates:
    - HORQubit API
    - hor_force meta-operation
    - hor_certify meta-operation
    - Certificate with F_cert >= 0.999
    - Backend routing (R4 stabilizer for Clifford)
"""

from __future__ import annotations

from hor import HORQubit, ForcingCondition, CertifyConfig


def main() -> None:
    print("=== Bell state example ===")
    q = HORQubit(n=2, chi_max=64)
    q.h(0)
    q.cnot(0, 1)
    # Apply a forcing condition (classical, identity on rho_2)
    q.hor_force(ForcingCondition(gap_open=True, symmetry="C4", max_bond=64))
    # Request certification with 4096 shots, target_eps = 0.001
    q.hor_certify(CertifyConfig(shots=4096, target_delta=0.001, target_eps=0.001))
    # Run
    result = q.run(seed=42)
    print(f"Counts:     {result.counts}")
    print(f"Backend:    {result.backend}")
    print(f"Status:     {result.status}")
    print(f"Reason:     {result.reason}")
    if result.certificate:
        print(f"F_cert:     {result.certificate.f_cert:.6f}")
        print(f"F_state:    {result.certificate.f_state:.6f}")
        print(f"F_process:  {result.certificate.f_process:.6f}")
        print(f"eps_trunc:  {result.certificate.eps_trunc:.6f}")
        print(f"eps_shot:   {result.certificate.eps_shot:.6f}")
        print(f"Manifest:   {result.certificate.manifest_hash[:32]}...")
        print(f"Signer:     {result.certificate.signer}")
        print(f"TRL:        {result.certificate.trl}")
    # Expected: ~50% 00, ~50% 11
    total = sum(result.counts.values())
    p00 = result.counts.get("00", 0) / total
    p11 = result.counts.get("11", 0) / total
    print(f"\nExpected Bell: p(00) ~ 0.5, p(11) ~ 0.5")
    print(f"Got:           p(00) = {p00:.3f}, p(11) = {p11:.3f}")


if __name__ == "__main__":
    main()
