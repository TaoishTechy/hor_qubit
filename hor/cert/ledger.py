"""hor.cert.ledger — Hash-chained append-only run ledger (E193).

Every certificate emission writes to an append-only log::

    L_i = H(L_{i-1} || record_i)

Each record contains:
    - log index
    - previous hash (chain link)
    - certificate hash (manifest hash)
    - test results (T1..T5 falsifiability metrics)
    - overhead ratio
    - timestamp

Tampering with any entry breaks every subsequent entry.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

from .crypto import blake3_hash, canonical_json


@dataclass
class LedgerEntry:
    """A single entry in the run ledger."""

    log_index: int
    previous_hash: str
    certificate_hash: str
    timestamp: str
    test_results: dict[str, float] = field(default_factory=dict)
    overhead_ratio: float = 1.0
    backend: str = ""
    f_cert: float = 0.0
    status: str = "uncertified"

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_hash(self) -> str:
        """Compute this entry's hash (chain link to next entry)."""
        return blake3_hash(canonical_json(self.to_dict()).encode("utf-8"))


@dataclass
class RunLedger:
    """Hash-chained append-only ledger (E193).

    The ledger file should have the append-only attribute set
    (``chattr +a`` on Linux). Tampering with any past entry breaks all
    subsequent links.
    """

    path: str | None = None
    entries: list[LedgerEntry] = field(default_factory=list)

    def append(
        self,
        certificate_hash: str,
        backend: str,
        f_cert: float,
        status: str,
        test_results: dict[str, float] | None = None,
        overhead_ratio: float = 1.0,
    ) -> LedgerEntry:
        """Append a new entry; returns the entry."""
        prev_hash = self.entries[-1].compute_hash() if self.entries else blake3_hash(b"")
        entry = LedgerEntry(
            log_index=len(self.entries),
            previous_hash=prev_hash,
            certificate_hash=certificate_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
            test_results=test_results or {},
            overhead_ratio=overhead_ratio,
            backend=backend,
            f_cert=f_cert,
            status=status,
        )
        self.entries.append(entry)
        if self.path is not None:
            self._persist(entry)
        return entry

    def verify(self) -> bool:
        """Verify the chain: each entry's previous_hash must match the
        computed hash of the previous entry.
        """
        for i, entry in enumerate(self.entries):
            if i == 0:
                if entry.previous_hash != blake3_hash(b""):
                    return False
            else:
                if entry.previous_hash != self.entries[i - 1].compute_hash():
                    return False
        return True

    def _persist(self, entry: LedgerEntry) -> None:
        """Append entry to the ledger file."""
        assert self.path is not None
        # Open in append mode; chattr +a should be set externally
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
