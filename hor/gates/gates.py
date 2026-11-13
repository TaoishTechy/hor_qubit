"""hor.gates.gates — Quantum gate matrices and the v0.1.5 expanded gate set.

All single-qubit gates are returned as ``2x2`` complex numpy arrays.
All two-qubit gates are ``4x4``. Three-qubit gates (Toffoli) are ``8x8``.

Cost tracking (v0.1.5 §6, v0.2 §3.4):
    - ``cost_sim``: classical simulation cost (per-gate, in flops)
    - ``cost_ft``: fault-tolerant cost (T-equivalents)

T-gate cost in classical simulation is the same as Clifford per-gate; in
fault-tolerant hardware, T is 10-100x more expensive due to magic state
distillation. HOR reports both separately (fixes A7-74).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

# --------------------------------------------------------------------------
# Fundamental constants
# --------------------------------------------------------------------------

# Stabilizer extent of |T> (Bravyi-Smith-Smolin 2019)
# xi(|T>) = cos^{-2}(pi/8) = 1.1716...
T_STATE_EXTENT: float = 1.0 / (math.cos(math.pi / 8) ** 2)

# Magic state yield rate (illustrative; depends on distillation protocol)
MAGIC_STATE_YIELD: float = 1.0 / 10.0  # 1 distilled T per 10 raw magic states

# --------------------------------------------------------------------------
# Gate catalog
# --------------------------------------------------------------------------

GateName = Literal[
    "h", "s", "x", "y", "z", "sqrtx", "t",
    "cnot", "cz", "iswap", "sqrtiswap",
    "rx", "ry", "rz", "u3",
    "toffoli", "xx", "yy", "zz", "ms",
    "measure", "reset",
]

# Set of Clifford gates (Gottesman-Knill eligible)
_CLIFFORD_1Q = {"h", "s", "x", "y", "z", "sqrtx"}
_CLIFFORD_2Q = {"cnot", "cz"}
_CLIFFORD_3Q: set[str] = set()


@dataclass(frozen=True)
class Gate:
    """A quantum gate instance.

    Attributes
    ----------
    name : GateName
        One of the names listed above.
    targets : tuple[int, ...]
        Qubit indices the gate acts on.
    params : tuple[float, ...]
        Rotation angles (for parameterized gates).
    """

    name: GateName
    targets: tuple[int, ...]
    params: tuple[float, ...] = ()

    @property
    def n_qubits(self) -> int:
        if self.name in ("cnot", "cz", "iswap", "sqrtiswap", "xx", "yy", "zz", "ms"):
            return 2
        if self.name == "toffoli":
            return 3
        return 1

    @property
    def is_clifford(self) -> bool:
        if self.name in _CLIFFORD_1Q or self.name in _CLIFFORD_2Q:
            return True
        # Parameterized gates can be Clifford at special angles
        if self.name == "rx" and len(self.params) == 1:
            theta = self.params[0] % (2 * math.pi)
            return abs(theta - 0.0) < 1e-12 or abs(abs(theta) - math.pi) < 1e-12
        if self.name == "ry" and len(self.params) == 1:
            theta = self.params[0] % (2 * math.pi)
            return abs(theta - 0.0) < 1e-12 or abs(abs(theta) - math.pi) < 1e-12
        if self.name == "rz" and len(self.params) == 1:
            theta = self.params[0] % (2 * math.pi)
            return theta in {0.0, math.pi / 2, math.pi, 3 * math.pi / 2} or any(
                abs(theta - a) < 1e-12 for a in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)
            )
        return False

    @property
    def cost_sim(self) -> int:
        """Per-gate classical simulation cost (flops)."""
        if self.n_qubits == 1:
            return 8 * 2  # 2x2 matrix on 2-element state
        if self.n_qubits == 2:
            return 8 * 4  # 4x4
        return 8 * 8  # 8x8 (Toffoli)

    @property
    def cost_ft(self) -> int:
        """Fault-tolerant cost in T-equivalents (Bravyi-Smith-Smolin).

        v0.1.5 §6: "T-gates are 10 to 100x more expensive than Clifford
        in fault-tolerant accounting." We use:
            - Clifford: 1 (cheap)
            - T: 10 (1 magic state, ~10x Clifford overhead from distillation)
            - Toffoli: 40 (4 T gates)
            - Parameterized non-Clifford: ~70 (T-count ~7 for arbitrary rotation)
        """
        if self.is_clifford:
            return 1
        if self.name == "t":
            return 10
        if self.name == "toffoli":
            return 40
        return 70


# --------------------------------------------------------------------------
# Matrix construction
# --------------------------------------------------------------------------

_SQRT2_INV = 1.0 / math.sqrt(2.0)


def _h() -> np.ndarray:
    return np.array([[_SQRT2_INV, _SQRT2_INV], [_SQRT2_INV, -_SQRT2_INV]], dtype=complex)


def _s() -> np.ndarray:
    return np.array([[1.0, 0.0], [0.0, 1j]], dtype=complex)


def _x() -> np.ndarray:
    return np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)


def _y() -> np.ndarray:
    return np.array([[0.0, -1j], [1j, 0.0]], dtype=complex)


def _z() -> np.ndarray:
    return np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)


def _sqrtx() -> np.ndarray:
    return 0.5 * np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], dtype=complex)


def _t() -> np.ndarray:
    return np.array([[1.0, 0.0], [0.0, np.exp(1j * math.pi / 4)]], dtype=complex)


def _cnot() -> np.ndarray:
    return np.array(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ],
        dtype=complex,
    )


def _cz() -> np.ndarray:
    return np.diag([1.0, 1.0, 1.0, -1.0]).astype(complex)


def _iswap() -> np.ndarray:
    return np.array(
        [
            [1, 0, 0, 0],
            [0, 0, 1j, 0],
            [0, 1j, 0, 0],
            [0, 0, 0, 1],
        ],
        dtype=complex,
    )


def _sqrtiswap() -> np.ndarray:
    return np.array(
        [
            [1, 0, 0, 0],
            [0, 0.5 * (1 + 1j), 0.5 * (1 - 1j), 0],
            [0, 0.5 * (1 - 1j), 0.5 * (1 + 1j), 0],
            [0, 0, 0, 1],
        ],
        dtype=complex,
    )


def _rx(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)


def _ry(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)


def _rz(theta: float) -> np.ndarray:
    return np.array(
        [[np.exp(-1j * theta / 2), 0], [0, np.exp(1j * theta / 2)]],
        dtype=complex,
    )


def _u3(theta: float, phi: float, lam: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array(
        [
            [c, -np.exp(1j * lam) * s],
            [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c],
        ],
        dtype=complex,
    )


def _toffoli() -> np.ndarray:
    M = np.eye(8, dtype=complex)
    M[6:8, 6:8] = np.array([[0, 1], [1, 0]], dtype=complex)
    return M


def _xx(theta: float) -> np.ndarray:
    r"""``exp(-i theta/2 X\otimes X)``."""
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array(
        [
            [c, 0, 0, -1j * s],
            [0, c, -1j * s, 0],
            [0, -1j * s, c, 0],
            [-1j * s, 0, 0, c],
        ],
        dtype=complex,
    )


def _yy(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array(
        [
            [c, 0, 0, 1j * s],
            [0, c, -1j * s, 0],
            [0, -1j * s, c, 0],
            [1j * s, 0, 0, c],
        ],
        dtype=complex,
    )


def _zz(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.diag(
        [np.exp(-1j * s / 2), np.exp(1j * s / 2), np.exp(1j * s / 2), np.exp(-1j * s / 2)]
    ).astype(complex) * c + np.diag(
        [np.exp(1j * s / 2), np.exp(-1j * s / 2), np.exp(-1j * s / 2), np.exp(1j * s / 2)]
    ).astype(complex) * 0  # placeholder; below is the simpler form
    # Actually, ZZ(theta) = exp(-i theta/2 Z\otimes Z) = diag(e^{-i theta/2}, e^{i theta/2}, e^{i theta/2}, e^{-i theta/2})
    # Redefine cleanly:


def _zz_clean(theta: float) -> np.ndarray:
    r"""``exp(-i theta/2 Z\otimes Z)``."""
    return np.diag(
        [
            np.exp(-1j * theta / 2),
            np.exp(1j * theta / 2),
            np.exp(1j * theta / 2),
            np.exp(-1j * theta / 2),
        ]
    ).astype(complex)


def _ms(theta: float) -> np.ndarray:
    r"""Molmer-Sorensen ``exp(-i theta/2 X\otimes X)`` (same form as XX)."""
    return _xx(theta)


# Replace the broken _zz above
_zz = _zz_clean


def gate_matrix(name: GateName, params: tuple[float, ...] = ()) -> np.ndarray:
    """Return the unitary matrix for the named gate."""
    if name == "h":
        return _h()
    if name == "s":
        return _s()
    if name == "x":
        return _x()
    if name == "y":
        return _y()
    if name == "z":
        return _z()
    if name == "sqrtx":
        return _sqrtx()
    if name == "t":
        return _t()
    if name == "cnot":
        return _cnot()
    if name == "cz":
        return _cz()
    if name == "iswap":
        return _iswap()
    if name == "sqrtiswap":
        return _sqrtiswap()
    if name == "rx":
        if len(params) != 1:
            raise ValueError("rx requires 1 parameter")
        return _rx(params[0])
    if name == "ry":
        if len(params) != 1:
            raise ValueError("ry requires 1 parameter")
        return _ry(params[0])
    if name == "rz":
        if len(params) != 1:
            raise ValueError("rz requires 1 parameter")
        return _rz(params[0])
    if name == "u3":
        if len(params) != 3:
            raise ValueError("u3 requires 3 parameters")
        return _u3(*params)
    if name == "toffoli":
        return _toffoli()
    if name == "xx":
        if len(params) != 1:
            raise ValueError("xx requires 1 parameter")
        return _xx(params[0])
    if name == "yy":
        if len(params) != 1:
            raise ValueError("yy requires 1 parameter")
        return _yy(params[0])
    if name == "zz":
        if len(params) != 1:
            raise ValueError("zz requires 1 parameter")
        return _zz(params[0])
    if name == "ms":
        if len(params) != 1:
            raise ValueError("ms requires 1 parameter")
        return _ms(params[0])
    raise ValueError(f"unknown gate: {name}")


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------


def is_clifford(g: Gate) -> bool:
    """Whether ``g`` is a Clifford gate (R4 stabilizer eligible)."""
    return g.is_clifford


def _embed_one_qubit(U: np.ndarray, n: int, target: int) -> np.ndarray:
    """Embed a 1Q unitary into the ``n``-qubit Hilbert space.

    ``U`` acts on qubit ``target``; identity acts on all others.
    """
    op = U if target == 0 else np.eye(2, dtype=complex)
    full = op
    for i in range(1, n):
        op = U if i == target else np.eye(2, dtype=complex)
        full = np.kron(full, op)
    return full


def _embed_two_qubit(U: np.ndarray, n: int, q0: int, q1: int) -> np.ndarray:
    r"""Embed a 2Q unitary acting on qubits ``q0, q1``.

    Builds the unitary by permuting qubits so that ``q0, q1`` become
    positions ``0, 1``, applying ``U \otimes I``, and permuting back.
    """
    if q0 == q1:
        raise ValueError("two-qubit gate requires distinct qubits")
    if q0 > q1:
        # Apply on the canonical order then swap back
        # Easier: build by repeated SWAPs
        pass
    # Simpler approach: apply via tensor network structure
    # Build the full 2^n x 2^n operator by left/right multiplying swap matrices.
    # For simplicity (and correctness), construct via permutations.
    perm = list(range(n))
    perm[0], perm[q0] = perm[q0], perm[0]
    perm[1], perm[q1] = perm[q1], perm[1] if q1 != 0 else perm[0]
    # We use a more direct approach: build the operator via SWAP conjugation
    # SWAP(i, j) matrix
    def _swap(i: int, j: int) -> np.ndarray:
        if i == j:
            return np.eye(2**n, dtype=complex)
        # Build swap on qubits i, j
        # 2-qubit SWAP
        SW2 = np.array(
            [
                [1, 0, 0, 0],
                [0, 0, 1, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
            ],
            dtype=complex,
        )
        # Embed on qubits i, j
        # Easier: build via repeated swap on adjacent qubits (bubble sort)
        # For small n this is fine.
        if i > j:
            i, j = j, i
        # Bubble qubit i to position 0, j to position 1
        full = np.eye(2**n, dtype=complex)
        # bubble i -> 0
        cur = i
        while cur > 0:
            full = _swap_adjacent(n, cur - 1) @ full
            cur -= 1
        # bubble j -> 1 (account for i's movement)
        cur = j - 1 if j > i else j
        while cur > 1:
            full = _swap_adjacent(n, cur - 1) @ full
            cur -= 1
        return full

    def _swap_adjacent(nq: int, k: int) -> np.ndarray:
        """SWAP between adjacent qubits k and k+1."""
        # Build via tensor product
        block = np.array(
            [
                [1, 0, 0, 0],
                [0, 0, 1, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
            ],
            dtype=complex,
        )
        full = np.eye(1, dtype=complex)
        for i in range(nq - 1):
            full = np.kron(full, block if i == k else np.eye(2, dtype=complex))
        return full

    # Bring q0 to position 0 and q1 to position 1
    swap_in = _swap(q0, q1)
    # Apply U on positions 0, 1
    U_embedded = np.kron(U, np.eye(2 ** (n - 2), dtype=complex))
    # Swap back
    full = swap_in.conj().T @ U_embedded @ swap_in
    return full


def apply_gate_to_state(rho: np.ndarray, g: Gate) -> np.ndarray:
    """Apply gate ``g`` to density matrix ``rho`` of size ``2^n x 2^n``.

    Returns the new density matrix ``U rho U^dagger``.
    """
    n = int(math.log2(rho.shape[0]))
    U_small = gate_matrix(g.name, g.params)
    if g.n_qubits == 1:
        U = _embed_one_qubit(U_small, n, g.targets[0])
    elif g.n_qubits == 2:
        U = _embed_two_qubit(U_small, n, g.targets[0], g.targets[1])
    else:
        # Toffoli: implement via embed-three-qubit (simple for n=3)
        if n == 3 and g.name == "toffoli":
            U = _toffoli()
        else:
            raise NotImplementedError(
                f"3-qubit gate embedding for n={n} not implemented; use decomposition"
            )
    return U @ rho @ U.conj().T


# Convenient module-level dict for the catalog
GATES: dict[str, int] = {
    # name -> n_qubits
    "h": 1, "s": 1, "x": 1, "y": 1, "z": 1, "sqrtx": 1, "t": 1,
    "cnot": 2, "cz": 2, "iswap": 2, "sqrtiswap": 2,
    "rx": 1, "ry": 1, "rz": 1, "u3": 1,
    "toffoli": 3, "xx": 2, "yy": 2, "zz": 2, "ms": 2,
}
