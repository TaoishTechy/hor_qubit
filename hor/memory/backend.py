"""hor.memory.backend — PAZUZU / pFACIL memory backend interface.

Memory tiers:
    L0  VRAM      ~0.5 TB/s, 16 GiB
    L1  RAM       ~50-100 GB/s, 64 GiB
    L1.5 zram     ~few GB/s, 25-50% of RAM
    L2  NVMe      ~3-7 GB/s, 2 TB
    L3  remote    network

Estimation formulas (PAZUZU Rev 1.1, QLOWN CAR §1.1):

    Statevector (c128): 16 * 2^n bytes
    Statevector (c64):   8 * 2^n bytes
    Density matrix (c128): 16 * 4^n bytes
    MPS (chi, c128): 2 * n * chi^2 * 16 bytes
    Stabilizer tableau: 2 * n^2 / 8 bytes

The 5-refused regimes from PAZUZU Rev 1.1 are converted to structured
alternatives (Rev 1.2 + Rev 1.3):
    - Density matrix n > 14 -> R6 trajectory sampling
    - Statevector n > 30 -> R3 MPS / light cone / cloud
    - 420M entangled -> refused (Bekenstein bound)
    - 420M product -> R5 product (storage certificate)
    - Interactive 30-qubit -> Path A (c64) / Path B (32 GB) / Path C (swap, batch)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


Backend = Literal["R1", "R2", "R3", "R4", "R5", "R6"]


def estimate_footprint(n: int, backend: Backend, chi: int = 64,
                       precision: str = "c128", d: int = 2) -> int:
    """Estimate memory footprint in bytes.

    Parameters
    ----------
    n : int
        Number of qubits.
    backend : str
        Backend name.
    chi : int
        MPS bond dimension (R3 only).
    precision : str
        ``"c64"`` (8 bytes) or ``"c128"`` (16 bytes).
    d : int
        Local qudit dimension (default 2 for qubits).
    """
    b = 8 if precision == "c64" else 16
    if backend == "R1":
        # Dense density matrix (could be statevector for pure states)
        return b * (d ** (2 * n))
    if backend == "R2":
        # Sparse: depends on nnz; assume 1% nonzeros as a placeholder
        return max(1, int(0.01 * (d**n))) * (b + math.ceil(n * math.log2(d) / 8))
    if backend == "R3":
        return 2 * n * d * chi * chi * b
    if backend == "R4":
        return (2 * n * (2 * n + 1)) // 8
    if backend == "R5":
        return n * d * b
    if backend == "R6":
        # Per-trajectory statevector (sequential)
        return b * (d**n)
    raise ValueError(f"unknown backend: {backend}")


@dataclass
class HORMemoryHandle:
    """A handle to allocated memory, possibly on swap."""

    backend: Backend
    n: int
    precision: str
    chi: int | None
    block_window: int  # number of low qubits kept in RAM
    swap_path: str | None
    footprint_bytes: int
    is_swapped: bool

    @property
    def ram_used_gb(self) -> float:
        if not self.is_swapped:
            return self.footprint_bytes / (2**30)
        # Working set is one block
        block_bytes = (2 ** self.block_window) * (8 if self.precision == "c64" else 16)
        return block_bytes / (2**30)

    @property
    def swap_used_gb(self) -> float:
        if not self.is_swapped:
            return 0.0
        return (self.footprint_bytes - (2 ** self.block_window) * (8 if self.precision == "c64" else 16)) / (2**30)


@dataclass
class HORMemoryBackend:
    """Memory backend adapter.

    If the pFACIL daemon is available, delegates to it. Otherwise, falls
    back to plain numpy arrays in RAM (no swap).

    Configuration (hor_config.toml)::

        [memory]
        ram_budget_gb = 16
        swap_path = "/var/lib/pfacil/swap/log"
        swap_size_gb = 64
        block_window_b = 20
        zram_enabled = true
    """

    ram_budget_gb: float = 16.0
    swap_budget_gb: float = 0.0
    block_window: int = 20
    pfacil_socket: str | None = None

    @property
    def total_budget_bytes(self) -> int:
        return int((self.ram_budget_gb + self.swap_budget_gb) * (2**30))

    def allocate(self, n: int, backend: Backend, chi: int = 64,
                 precision: str = "c128") -> HORMemoryHandle:
        """Allocate memory for an n-qubit state on the given backend."""
        footprint = estimate_footprint(n, backend, chi, precision)
        if footprint <= 0.4 * self.ram_budget_gb * (2**30):
            # Fits comfortably in RAM
            return HORMemoryHandle(
                backend=backend, n=n, precision=precision, chi=chi,
                block_window=n, swap_path=None,
                footprint_bytes=footprint, is_swapped=False,
            )
        if footprint <= self.total_budget_bytes:
            # Needs swap
            b = self._tune_block_window(n, precision)
            return HORMemoryHandle(
                backend=backend, n=n, precision=precision, chi=chi,
                block_window=b, swap_path="/var/lib/pfacil/swap/log",
                footprint_bytes=footprint, is_swapped=True,
            )
        raise MemoryError(
            f"HOR state of {footprint / 2**30:.1f} GB exceeds "
            f"RAM+swap budget ({self.ram_budget_gb:.1f} + {self.swap_budget_gb:.1f} GB). "
            "Router should refuse or escalate to cloud."
        )

    def _tune_block_window(self, n: int, precision: str) -> int:
        """Pick the block window so one block fits in 40% of RAM."""
        b = 8 if precision == "c64" else 16
        target_bytes = 0.4 * self.ram_budget_gb * (2**30)
        # block_bytes = 2^b * b
        # 2^b <= target / b => b <= log2(target/b)
        if b >= target_bytes:
            return n
        b_window = int(math.log2(target_bytes / b))
        return max(16, min(b_window, n))

    def certificate_fields(self, handle: HORMemoryHandle) -> dict:
        """Memory-related fields for the certificate."""
        return {
            "memory_backend": handle.backend,
            "footprint_gb": handle.footprint_bytes / (2**30),
            "is_swapped": handle.is_swapped,
            "block_window_b": handle.block_window,
            "ram_used_gb": handle.ram_used_gb,
            "swap_used_gb": handle.swap_used_gb,
            "p95_gate_latency_ms": 9.0 if handle.is_swapped else 1.0,  # placeholder
        }
