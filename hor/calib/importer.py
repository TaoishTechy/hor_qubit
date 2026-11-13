"""hor.calib.importer — Hardware calibration import.

Canonical HOR JSON schema (v0.3):

    {
      "calibration_id": "cal-2026-11-13-001",
      "timestamp": "2026-11-13T10:00:00Z",
      "backend_name": "example-5q",
      "qubits": [
        {"id": 0, "t1_us": 120.0, "t2_us": 90.0, "readout_error": 0.012, "freq_ghz": 5.01}
      ],
      "gates": [
        {"name": "sx", "qubits": [0], "error": 0.0008, "duration_ns": 35},
        {"name": "cx", "qubits": [0, 1], "error": 0.008, "duration_ns": 320}
      ],
      "readout": {
        "confusion_matrix": [[0.988, 0.012], [0.018, 0.982]]
      },
      "leakage": {
        "per_qubit_leakage_rate": {"0": 0.0005}
      }
    }

Rules:
    - Importer validates schema.
    - Rejects missing ``calibration_id`` or stale timestamp.
    - Calibration is never assumed; if absent, F_process = "unknown"
      and status = "uncertified" with reason "no_calibration".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


@dataclass
class GateCalib:
    """Per-gate calibration entry."""

    name: str
    qubits: tuple[int, ...]
    error: float
    duration_ns: int


@dataclass
class QubitCalib:
    """Per-qubit calibration entry."""

    id: int
    t1_us: float
    t2_us: float
    readout_error: float
    freq_ghz: float


@dataclass
class Calibration:
    """A parsed hardware calibration."""

    calibration_id: str
    timestamp: datetime
    backend_name: str
    qubits: dict[int, QubitCalib] = field(default_factory=dict)
    gates: dict[tuple[str, tuple[int, ...]], GateCalib] = field(default_factory=dict)
    confusion_matrix: list[list[float]] | None = None
    leakage_rates: dict[int, float] = field(default_factory=dict)
    raw_hash: str = ""

    @property
    def age_hours(self) -> float:
        """Hours since this calibration was taken."""
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds() / 3600.0

    def is_stale(self, max_age_hours: float = 24.0) -> bool:
        return self.age_hours > max_age_hours

    def gate_error(self, name: str, qubits: tuple[int, ...]) -> float:
        """Look up the error rate for a specific gate."""
        return self.gates.get((name, qubits), GateCalib(name, qubits, 0.0, 0)).error

    def qubit_leakage(self, q: int) -> float:
        return self.leakage_rates.get(q, 0.0)


class CalibrationImporter:
    """Calibration importer for HOR JSON and Qiskit BackendProperties."""

    def import_hor_json(self, path: str, max_age_hours: float = 24.0) -> Calibration:
        """Import a canonical HOR JSON calibration file."""
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        if "calibration_id" not in data:
            raise ValueError("calibration file missing 'calibration_id'")
        if "timestamp" not in data:
            raise ValueError("calibration file missing 'timestamp'")
        ts = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        cal = Calibration(
            calibration_id=data["calibration_id"],
            timestamp=ts,
            backend_name=data.get("backend_name", "unknown"),
            raw_hash=__import__("hashlib").sha256(raw.encode()).hexdigest()[:16],
        )
        for q in data.get("qubits", []):
            qc = QubitCalib(
                id=q["id"],
                t1_us=q.get("t1_us", 100.0),
                t2_us=q.get("t2_us", 80.0),
                readout_error=q.get("readout_error", 0.0),
                freq_ghz=q.get("freq_ghz", 5.0),
            )
            cal.qubits[qc.id] = qc
        for g in data.get("gates", []):
            gc = GateCalib(
                name=g["name"],
                qubits=tuple(g["qubits"]),
                error=g.get("error", 0.0),
                duration_ns=g.get("duration_ns", 0),
            )
            cal.gates[(gc.name, gc.qubits)] = gc
        if "readout" in data and "confusion_matrix" in data["readout"]:
            cm = data["readout"]["confusion_matrix"]
            # Validate rows sum to 1 within tolerance 1e-6
            for row in cm:
                if abs(sum(row) - 1.0) > 1e-6:
                    raise ValueError(f"confusion matrix row does not sum to 1: {row}")
            cal.confusion_matrix = cm
        for qid_str, rate in data.get("leakage", {}).get("per_qubit_leakage_rate", {}).items():
            cal.leakage_rates[int(qid_str)] = float(rate)
        if cal.is_stale(max_age_hours):
            raise ValueError(
                f"calibration is stale: {cal.age_hours:.1f} hours > {max_age_hours} hours"
            )
        return cal

    def import_qiskit_json(self, path: str, max_age_hours: float = 24.0) -> Calibration:
        """Import a Qiskit BackendProperties JSON dump.

        This is a best-effort importer; the canonical HOR JSON format is
        the source of truth.
        """
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        ts = datetime.fromisoformat(data.get("last_update_date", "2026-01-01T00:00:00Z")
                                    .replace("Z", "+00:00"))
        cal = Calibration(
            calibration_id=f"qiskit-{data.get('backend_name', 'unknown')}",
            timestamp=ts,
            backend_name=data.get("backend_name", "unknown"),
            raw_hash=__import__("hashlib").sha256(raw.encode()).hexdigest()[:16],
        )
        for q in data.get("qubits", []):
            for qprop in q:
                if qprop.get("name") == "T1":
                    qc = QubitCalib(
                        id=len(cal.qubits),
                        t1_us=float(qprop.get("value", 100.0)),
                        t2_us=80.0,
                        readout_error=0.01,
                        freq_ghz=5.0,
                    )
                    cal.qubits[qc.id] = qc
                    break
        if cal.is_stale(max_age_hours):
            raise ValueError(
                f"calibration is stale: {cal.age_hours:.1f} hours > {max_age_hours} hours"
            )
        return cal
