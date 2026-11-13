"""hor.api — HORQubit class, QASM parser, CLI.

The :class:`HORQubit` class is the user-facing entry point. It builds
a vacuum HOR state, applies gates and HOR meta-operations, and emits
a typed certificate after :meth:`run`.

Python API (v0.1.5 §14)::

    from hor import HORQubit, ForcingCondition, CertifyConfig

    q = HORQubit(n=2, chi_max=64)
    q.h(0)
    q.cnot(0, 1)
    q.rz(0.5, 0)
    q.hor_force(ForcingCondition(gap_open=True, symmetry="C4", max_bond=64))
    cert = q.hor_certify(CertifyConfig(shots=8192, target_delta=0.001))
    result = q.run()
"""

from __future__ import annotations

from .horqubit import HORQubit, HORResult, CertifyConfig
from .cli import main
from .qasm import parse_qasm

__all__ = ["HORQubit", "HORResult", "CertifyConfig", "parse_qasm", "main"]
