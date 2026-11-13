"""hor.core.compatibility — Backwards compatibility theorem.

Theorem (v0.1.5 §2, v0.2 §2.4)::

    For any n-qubit circuit C built from
        {H, S, T, X, Y, Z, sqrt(X), CNOT, CZ, iSWAP, RX, RY, RZ, U3, Toffoli}
    and measurement in Z::

        P_HOR(x | C, rho_HOR^vac) = P_standard(x | C, rho_2)

    up to the classical simulation floating-point floor ~1e-14 per gate.

This module enforces the theorem *empirically*: strip ``hor.`` pragmas
from a circuit, run both the HOR simulator and a reference statevector
simulator, and assert that the total variation distance is below
``1e-12`` for ``n <= 12``.
"""

from __future__ import annotations

import re
from typing import Any


def strip_hor_pragmas(qasm: str) -> str:
    """Strip all ``hor.`` lines from a QASM program.

    A parser that ignores ``hor.`` lines gets a valid standard program
    (v0.1 §2, v0.1.5 §14, v0.2 §10.2). This is the operational content
    of the backwards-compatibility rule.
    """
    lines = qasm.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        # Drop hor.* directives and pure-comment lines
        if stripped.startswith("hor.") or stripped.startswith("// hor."):
            continue
        kept.append(line)
    return "\n".join(kept)


def backwards_compatible(
    hor_counts: dict[str, int],
    standard_counts: dict[str, int],
    atol: float = 1e-12,
) -> bool:
    """Check that two count dictionaries agree to within ``atol`` TVD.

    Both dictionaries are normalized to probabilities first. The absolute
    tolerance is on the total variation distance.
    """
    keys = set(hor_counts) | set(standard_counts)
    if not keys:
        return True
    total_h = sum(hor_counts.values()) or 1
    total_s = sum(standard_counts.values()) or 1
    tvd = 0.0
    for k in keys:
        p = hor_counts.get(k, 0) / total_h
        q = standard_counts.get(k, 0) / total_s
        tvd += abs(p - q)
    tvd *= 0.5
    return tvd < atol


def assert_compatible(
    hor_result: Any,
    standard_result: Any,
    atol: float = 1e-12,
) -> None:
    """Assert backwards compatibility; raise AssertionError on failure."""
    if not hasattr(hor_result, "counts") or not hasattr(standard_result, "counts"):
        raise TypeError("results must have a .counts attribute")
    if not backwards_compatible(hor_result.counts, standard_result.counts, atol=atol):
        # Compute TVD for the error message
        keys = set(hor_result.counts) | set(standard_result.counts)
        total_h = sum(hor_result.counts.values()) or 1
        total_s = sum(standard_result.counts.values()) or 1
        tvd = 0.5 * sum(
            abs(hor_result.counts.get(k, 0) / total_h - standard_result.counts.get(k, 0) / total_s)
            for k in keys
        )
        raise AssertionError(
            f"backwards compatibility broken: TVD = {tvd:.3e} > atol = {atol:.3e}"
        )


# A regex for parsing hor.* directives from a QASM line
HOR_PRAGMA_RE = re.compile(r"^\s*hor\.(\w+)\s*(.*)$")
