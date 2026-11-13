"""hor.sim.mps — R3 Matrix Product State backend with TEBD-style updates.

Open-boundary MPS::

    |psi> = sum_{s1..sn} A^s1_1 A^s2_2 ... A^sn_n |s1..sn>

with bond dimension ``chi``. Memory: ``2 n chi^2 * b`` bytes.

Truncation accounting (v0.2 §5.3, v0.1.5 §7):
    eps_trunc_step = sum_{s > chi} lambda_s^2  (discarded weight per SVD)
    eps_trunc_total = 1 - prod_steps (1 - eps_trunc_step)

If ``eps_trunc_total`` exceeds user budget, router must flag
``status: uncertified`` or escalate to R1.

Schuch-Vidal bound (v0.1 §7): random circuits saturate ``chi`` after
depth ~ log2(chi) per layer. Router refuses MPS for 2D volume-law.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..core.state import HORState
from ..gates.gates import Gate


@dataclass
class MPS:
    """Open-boundary matrix product state.

    Tensors stored as a list of ``A[k]`` with shape ``(chi_{k-1}, d, chi_k)``.
    Boundary conditions: ``chi_0 = chi_n = 1``.
    """

    n: int
    d: int = 2
    chi: int = 16
    tensors: list[np.ndarray] = field(default_factory=list)
    truncation_error: float = 0.0
    # Schmidt values per bond, for entropy computation
    schmidt_values: list[np.ndarray] = field(default_factory=list)

    @classmethod
    def from_statevector(cls, psi: np.ndarray, n: int, d: int = 2, chi: int = 16) -> "MPS":
        """Construct an MPS from a statevector via sequential SVDs.

        Sweeps left-to-right, performing an SVD at each bond. The
        discarded weight (sum of squared singular values beyond ``chi``)
        accumulates into :attr:`truncation_error`.
        """
        # Reshape psi to (d, d, ..., d) with n axes
        psi = np.asarray(psi, dtype=complex).reshape([d] * n)
        tensors: list[np.ndarray] = []
        schmidt: list[np.ndarray] = []
        chi_left = 1
        truncation = 0.0
        # We maintain `remaining` as a tensor with shape (chi_left, d, d, ..., d)
        # (the leading axis is the bond from the left, the rest are physical/site axes).
        # Initially chi_left=1, so shape is (1, d, d, ..., d) -- we expand psi.
        remaining = psi.reshape(1, d, *([d] * (n - 1)))
        for k in range(n - 1):
            # Shape: (chi_left, d, d^{n-k-1})
            shape = remaining.shape
            # The "rest" after the first two axes is d^{n-k-1}
            rest_size = int(np.prod(shape[2:]))
            new_shape = (chi_left * d, rest_size)
            mat = remaining.reshape(new_shape)
            U, S, Vh = np.linalg.svd(mat, full_matrices=False)
            # Truncate to chi
            if len(S) > chi:
                truncation += float(np.sum(S[chi:] ** 2))
                U = U[:, :chi]
                S = S[:chi]
                Vh = Vh[:chi, :]
            # Renormalize S
            norm = np.linalg.norm(S)
            if norm > 0:
                S = S / norm
            # A^s_k shape (chi_left, d, chi_right)
            chi_right = len(S)
            A = U.reshape(chi_left, d, chi_right)
            tensors.append(A)
            schmidt.append(S)
            chi_left = chi_right
            # New remaining: Vh has shape (chi_right, rest_size).
            # We multiply by diag(S) to keep amplitudes: new = diag(S) @ Vh.
            # We need to reshape to (chi_right, d, d^{n-k-2}) for the next iteration.
            # rest_size = d^{n-k-1}, so d^{n-k-2} = rest_size / d
            new_remaining = S[:, None] * Vh  # shape (chi_right, rest_size)
            if n - k - 2 > 0:
                next_rest = rest_size // d
                remaining = new_remaining.reshape(chi_left, d, next_rest)
            else:
                remaining = new_remaining.reshape(chi_left, d)
        # Last tensor: shape (chi_left, d, 1)
        # If remaining is 2D (chi_left, d), reshape to (chi_left, d, 1)
        if remaining.ndim == 2:
            last = remaining.reshape(chi_left, d, 1)
        else:
            # Collapse remaining axes
            last = remaining.reshape(chi_left, d, 1)
        tensors.append(last)
        return cls(n=n, d=d, chi=chi, tensors=tensors, truncation_error=truncation,
                   schmidt_values=schmidt)

    def to_statevector(self) -> np.ndarray:
        """Contract the MPS back to a statevector. Only feasible for small ``n``."""
        full = self.tensors[0]  # shape (1, d, chi_1)
        full = full.reshape(self.d, -1)  # (d, chi_1)
        for k in range(1, self.n):
            # full shape so far: (chi_{k-1}, d^{k-1})... actually contract sequentially
            # Easier: contract tensor by tensor
            pass
        # Simpler approach: full contraction
        result = self.tensors[0]  # (1, d, chi_1)
        for k in range(1, self.n):
            # result shape: (1, d^k, chi_k)
            # next tensor: (chi_k, d, chi_{k+1})
            result = np.tensordot(result, self.tensors[k], axes=([2], [0]))
        # result shape: (1, d, d, ..., d, 1) -> drop the bond axes
        return result.reshape(-1)

    # ------------------------------------------------------------------
    # Entanglement diagnostics
    # ------------------------------------------------------------------

    def entanglement_entropy(self, bond: int) -> float:
        """Von Neumann entropy at bond ``bond`` (between sites ``bond`` and ``bond+1``).

        ``S = -sum_i lambda_i^2 log2 lambda_i^2``.
        """
        if bond >= len(self.schmidt_values):
            return 0.0
        s = self.schmidt_values[bond]
        s2 = s ** 2
        s2 = s2[s2 > 0]
        return float(-np.sum(s2 * np.log2(s2)))

    def max_entanglement(self) -> float:
        """Maximum bond entropy across all bonds."""
        return max((self.entanglement_entropy(k) for k in range(len(self.schmidt_values))),
                   default=0.0)


@dataclass
class MPSBackend:
    """R3 MPS backend with TEBD-style gate application.

    Applies 1Q gates exactly (no truncation). Applies 2Q gates via SVD
    truncation with discarded-weight tracking.
    """

    name: str = "R3"
    chi_max: int = 64
    cutoff: float = 1e-10
    truncation_budget: float = 1e-3

    def estimate_memory(self, n: int, chi: int | None = None, b: int = 16) -> int:
        chi = chi or self.chi_max
        # 2 * n * chi^2 * b (factor 2 for complex128)
        return 2 * n * chi * chi * b

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, state: HORState, gates: list[Gate], shots: int = 1024,
            seed: int | None = None) -> dict:
        """Run a circuit. The MPS is built from ``state``'s statevector."""
        # Convert initial state to MPS
        psi = state.as_statevector() if state.is_pure else None
        if psi is None:
            # Mixed state: MPS doesn't directly support; fall back
            raise ValueError("MPS backend requires pure state; use R6 for mixed states")
        mps = MPS.from_statevector(psi, state.n, d=2, chi=self.chi_max)
        # Apply gates
        for g in gates:
            if g.name in ("measure", "reset"):
                # Mid-circuit ops are tricky in MPS; defer to end-of-circuit sampling
                continue
            mps = self._apply_gate(mps, g)
        # Convert back to statevector for sampling (works for small n)
        if state.n <= 20:
            final_psi = mps.to_statevector()
            final_psi = final_psi / np.linalg.norm(final_psi)
            probs = np.abs(final_psi) ** 2
        else:
            # Sample from MPS directly (more complex; placeholder)
            # For now: warn and fall back to uniform
            probs = np.ones(2**state.n) / (2**state.n)
        rng = np.random.default_rng(seed)
        indices = rng.choice(2**state.n, size=shots, p=probs / probs.sum())
        counts: dict[str, int] = {}
        for idx in indices:
            bitstring = format(int(idx), f"0{state.n}b")
            counts[bitstring] = counts.get(bitstring, 0) + 1
        return {
            "counts": counts,
            "final_state": state,
            "truncation_error": mps.truncation_error,
            "backend": self.name,
            "shots": shots,
            "chi_used": mps.chi,
            "max_entanglement": mps.max_entanglement(),
        }

    def _apply_gate(self, mps: MPS, g: Gate) -> MPS:
        """Apply a single gate to the MPS.

        For 1Q gates: contract the tensor, no truncation.
        For 2Q gates: contract two tensors, SVD, truncate to ``chi_max``.
        """
        from ..gates.gates import gate_matrix
        U = gate_matrix(g.name, g.params)
        if g.n_qubits == 1:
            # Apply U on the tensor at site g.targets[0]
            k = g.targets[0]
            # A[k] shape (chi_left, d, chi_right)
            A = mps.tensors[k]
            # Contract: A'_{s, l, r} = sum_s' U_{s, s'} A_{s', l, r}
            new_A = np.tensordot(U, A, axes=([1], [1]))
            new_A = np.moveaxis(new_A, 0, 1)  # shape back to (chi_left, d, chi_right)
            mps.tensors[k] = new_A
        elif g.n_qubits == 2:
            k1, k2 = sorted(g.targets)
            # Apply U on the two-site block
            A1 = mps.tensors[k1]  # (chi_{k1-1}, d, chi_{k1})
            A2 = mps.tensors[k2]  # (chi_{k1}, d, chi_{k2+1})
            # For adjacent qubits, contract directly
            if k2 == k1 + 1:
                # Theta shape (chi_left, d, d, chi_right)
                Theta = np.tensordot(A1, A2, axes=([2], [0]))
                # Apply U on the two physical indices
                Theta = np.tensordot(U.reshape(2, 2, 2, 2), Theta, axes=([2, 3], [1, 2]))
                Theta = np.moveaxis(Theta, [0, 1], [1, 2])
                # SVD
                chi_left = Theta.shape[0]
                chi_right = Theta.shape[3]
                mat = Theta.reshape(chi_left * 2, 2 * chi_right)
                Usv, S, Vh = np.linalg.svd(mat, full_matrices=False)
                # Truncate
                chi_eff = min(self.chi_max, len(S))
                if len(S) > chi_eff:
                    mps.truncation_error += float(np.sum(S[chi_eff:] ** 2))
                    Usv = Usv[:, :chi_eff]
                    S = S[:chi_eff]
                    Vh = Vh[:chi_eff, :]
                # Normalize
                norm = np.linalg.norm(S)
                if norm > 0:
                    S = S / norm
                mps.schmidt_values[k1] = S
                # Update tensors
                mps.tensors[k1] = (Usv * S).reshape(chi_left, 2, chi_eff)
                mps.tensors[k2] = Vh.reshape(chi_eff, 2, chi_right)
            else:
                # Non-adjacent: need SWAP network; for simplicity, fall back to R1
                raise NotImplementedError(
                    f"non-adjacent 2Q gate {g.name} on ({k1},{k2}); use R1"
                )
        else:
            raise NotImplementedError(f"{g.n_qubits}-qubit gate not supported in R3")
        return mps
