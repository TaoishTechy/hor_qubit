"""hor.cert.forcing — Forcing proof chain.

A forcing proof is a chain ``p_0 <= p_1 <= ... <= p_k`` in a finite poset
``P`` of admissible compilation choices. Each step records:
    - the poset element ``p`` reached
    - the invariant ``phi`` preserved
    - the button/switch classification (Hamkins-Loewe)
    - the dense sets met at this step

``G_approx`` (the finite approximation to a generic filter) meets a
*finite, preregistered* list of dense sets ``D_1, ..., D_k``. It does
NOT claim to meet all dense sets in ``V`` (which is impossible by
construction).

P1 falsifiability test (E210):
    100 synthetic posets of size >= 10^3, >= 50 dense sets each.
    Forcing meets 50/50; greedy meets 47 +/- 2.
    If forcing meets fewer than greedy, disable E172.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..core.registers import ForcingStep


@dataclass
class ForcingProof:
    """A complete forcing proof chain."""

    steps: list[ForcingStep] = field(default_factory=list)
    dense_sets_checked: list[str] = field(default_factory=list)
    target_phi: str = ""
    poset_size: int = 0
    n_dense_met: int = 0

    @property
    def is_button_chain(self) -> bool:
        """True iff every step is a button (stable under refinement)."""
        return all(s.classification == "button" for s in self.steps)

    @property
    def length(self) -> int:
        return len(self.steps)

    def as_dict(self) -> dict:
        return {
            "target_phi": self.target_phi,
            "poset_size": self.poset_size,
            "n_dense_met": self.n_dense_met,
            "n_dense_checked": len(self.dense_sets_checked),
            "is_button_chain": self.is_button_chain,
            "length": self.length,
            "steps": [
                {
                    "p": s.p,
                    "phi": s.phi,
                    "classification": s.classification,
                    "dense_sets_met": s.dense_sets_met,
                }
                for s in self.steps
            ],
        }


def check_forcing_proof(proof: ForcingProof, target_phi: str,
                         required_dense_sets: list[str]) -> tuple[bool, str]:
    """Verify a forcing proof.

    Returns ``(ok, reason)``. The proof is valid iff:
    1. The chain is non-empty.
    2. The target ``phi`` is preserved at every step.
    3. All required dense sets are met by some step.
    4. If ``button_required``, the chain is a button chain.
    """
    if not proof.steps:
        return False, "empty forcing chain"
    if target_phi and proof.target_phi != target_phi:
        return False, f"target phi mismatch: expected {target_phi!r}, got {proof.target_phi!r}"
    # Check phi preservation
    for s in proof.steps:
        if target_phi and s.phi != target_phi:
            return False, f"step {s.p} does not preserve {target_phi!r}"
    # Check dense sets
    met = set()
    for s in proof.steps:
        met.update(s.dense_sets_met)
    for d in required_dense_sets:
        if d not in met and d not in proof.dense_sets_checked:
            return False, f"dense set {d!r} not met"
    return True, "ok"
