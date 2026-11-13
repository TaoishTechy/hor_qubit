"""hor.memory — PAZUZU / pFACIL memory backend interface.

Defines the interface for memory-tier-aware backends that can offload
state tensors to NVMe swap when RAM is insufficient (PAZUZU Rev 1.1).

The actual pFACIL daemon is a separate Rust process; this module is
the Python adapter that talks to it via a Unix socket. If the daemon
is not available, the memory layer falls back to plain numpy arrays
in RAM with no swap.

This module implements the *interface*, not the daemon. The daemon
is documented in PAZUZU v2.0 and is out of scope for hor-qubit v0.3.
"""

from __future__ import annotations

from .backend import HORMemoryBackend, HORMemoryHandle, estimate_footprint

__all__ = ["HORMemoryBackend", "HORMemoryHandle", "estimate_footprint"]
