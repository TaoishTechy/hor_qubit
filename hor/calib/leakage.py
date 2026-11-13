"""hor.calib.leakage — Per-qubit leakage tracking.

Per-qubit leakage accumulator (v0.3 §2)::

    L_q starts at 0
    After each gate: L_q += leakage_rate_gate * (1 - L_q)
    After each measurement: if hardware reports leakage, overwrite.

For a qubit, leakage is population outside ``{|0>, |1>}`` (typically
the ``|2>`` state for transmons).

Kraus model for incoherent leakage::

    L_0 = sqrt(1 - p_L) * I_2  +  1
    L_1 = sqrt(p_L) * |2><1|

v0.3 tracks incoherent ``p_L`` only. Coherent leakage requires
tomography and is v0.4.

Effect on F_cert (v0.3)::

    F_cert^v0.3 = F_cert^v0.2 * (1 - L_max) * F_process^cal

where ``F_process^cal ~= prod_gates (1 - error_g)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .importer import Calibration


@dataclass
class LeakageTracker:
    """Track per-qubit leakage through a circuit.

    Maintains an accumulator per qubit, updated at each gate. Also
    tracks the maximum leakage across all qubits for the F_cert
    formula.
    """

    n_qubits: int
    leakage_rates: dict[int, float] = field(default_factory=dict)
    accumulators: dict[int, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for q in range(self.n_qubits):
            self.accumulators[q] = 0.0

    @classmethod
    def from_calibration(cls, cal: Calibration, n_qubits: int) -> "LeakageTracker":
        """Build a tracker from a Calibration's leakage rates."""
        return cls(n_qubits=n_qubits, leakage_rates=dict(cal.leakage_rates))

    def step(self, gate_name: str, qubits: tuple[int, ...],
             gate_error: float = 0.0) -> None:
        """Apply one gate's leakage contribution.

        For v0.3, we use a simple model: each gate contributes
        ``leakage_rate_q * (1 - L_q)`` to qubit ``q``'s accumulator,
        where ``leakage_rate_q`` is the per-qubit rate from calibration.
        """
        for q in qubits:
            rate = self.leakage_rates.get(q, 0.0)
            self.accumulators[q] += rate * (1 - self.accumulators[q])
        # Optional: also accumulate gate_error as a leakage proxy
        # (gate errors include leakage contribution; this is conservative)

    def measure(self, qubit: int, measured_leakage: float | None = None) -> None:
        """Update leakage with a measurement.

        If the hardware reports leakage, overwrite the accumulator.
        Otherwise leave unchanged.
        """
        if measured_leakage is not None:
            self.accumulators[qubit] = measured_leakage

    @property
    def max_leakage(self) -> float:
        return max(self.accumulators.values()) if self.accumulators else 0.0

    def per_qubit(self) -> dict[int, float]:
        return dict(self.accumulators)

    def f_cert_penalty(self) -> float:
        """``(1 - L_max)`` factor for the F_cert formula."""
        return 1.0 - self.max_leakage
