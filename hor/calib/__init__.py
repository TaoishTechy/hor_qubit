"""hor.calib — v0.3 hardware calibration layer.

Adds:
    - Calibration importer (HOR JSON canonical format + Qiskit BackendProperties)
    - Per-qubit leakage tracking (Kraus / accumulator)
    - Readout mitigation with negativity guard

A run is `uncertified` if no calibration is loaded, OR if calibration
is stale (older than ``max_age_hours``), OR if readout negativity mass
exceeds 5% (configurable).
"""

from __future__ import annotations

from .importer import Calibration, CalibrationImporter
from .leakage import LeakageTracker
from .readout import ReadoutMitigator, NegativityGuardError

__all__ = [
    "Calibration",
    "CalibrationImporter",
    "LeakageTracker",
    "ReadoutMitigator",
    "NegativityGuardError",
]
