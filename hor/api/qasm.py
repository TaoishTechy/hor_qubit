"""hor.api.qasm — Minimal QASM parser with HOR pragma support.

Parses a small subset of OpenQASM 2.0 plus the ``hor.`` extension
directives. A parser that ignores ``hor.`` lines yields a valid
standard program (v0.1.5 §14).

Supported:

    horq q[2]; c[2];
    h q[0]; cx q[0], q[1]; rz(0.5) q[0]; t q[0];
    measure q[0] -> c[0];
    hor.force {gap_open: true, symmetry: "C4"};
    hor.certify {shots: 8192};

This is a minimal parser for the HOR-Qubit examples and CLI. For
production QASM, use the ``qiskit.qasm2`` parser.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..core.registers import ForcingCondition
from ..gates.gates import Gate


@dataclass
class QASMProgram:
    """A parsed QASM program."""

    n_qubits: int
    n_clbits: int
    gates: list[Gate]
    hor_force: ForcingCondition | None = None
    hor_certify_shots: int = 1024
    hor_certify_delta: float = 0.001
    raw: str = ""


# Mapping from QASM gate names to internal names
_QASM_GATE_MAP: dict[str, str] = {
    "h": "h", "s": "s", "t": "t", "x": "x", "y": "y", "z": "z",
    "sx": "sqrtx", "cx": "cnot", "cnot": "cnot", "cz": "cz",
    "iswap": "iswap", "rx": "rx", "ry": "ry", "rz": "rz",
    "u3": "u3", "ccx": "toffoli", "toffoli": "toffoli",
}


def parse_qasm(text: str) -> QASMProgram:
    """Parse a QASM program into gates and HOR directives."""
    n_qubits = 0
    n_clbits = 0
    gates: list[Gate] = []
    hor_force_cond: ForcingCondition | None = None
    hor_shots = 1024
    hor_delta = 0.001

    for line in text.splitlines():
        line = line.strip().rstrip(";").strip()
        if not line or line.startswith("//"):
            continue
        # hor.* directives
        if line.startswith("hor."):
            m = re.match(r"hor\.(\w+)\s*(.*)", line)
            if m:
                directive = m.group(1)
                args = m.group(2).strip().lstrip("{").rstrip("}").strip()
                if directive == "force":
                    try:
                        params = _parse_kv(args)
                        hor_force_cond = ForcingCondition(
                            gap_open=params.get("gap_open", True),
                            symmetry=params.get("symmetry"),
                            max_bond=int(params.get("max_bond", 64)),
                        )
                    except Exception:
                        hor_force_cond = ForcingCondition()
                elif directive == "certify":
                    try:
                        params = _parse_kv(args)
                        hor_shots = int(params.get("shots", 1024))
                        hor_delta = float(params.get("target_delta", 0.001))
                    except Exception:
                        pass
            continue
        # QASM headers
        if line.startswith("horq") or line.startswith("OPENQASM") or line.startswith("include"):
            # Extract n_qubits and n_clbits
            m = re.search(r"q\[(\d+)\]", line)
            if m:
                n_qubits = int(m.group(1))
            m = re.search(r"c\[(\d+)\]", line)
            if m:
                n_clbits = int(m.group(1))
            continue
        # Gate line: name [params] q[i], q[j], ...
        # Try to match: gate(params) q[i], q[j] OR gate q[i], q[j]
        m = re.match(r"(\w+)(\([^)]*\))?\s+(.+)", line)
        if m:
            gname = m.group(1).lower()
            params_str = m.group(2)
            targets_str = m.group(3)
            # Parse targets
            target_matches = re.findall(r"q\[(\d+)\]", targets_str)
            targets = tuple(int(t) for t in target_matches)
            if not targets:
                continue
            # Parse params
            params: tuple[float, ...] = ()
            if params_str:
                inner = params_str[1:-1]  # strip parens
                params = tuple(float(p.strip()) for p in inner.split(","))
            # Map name
            internal_name = _QASM_GATE_MAP.get(gname, gname)
            try:
                gates.append(Gate(name=internal_name, targets=targets, params=params))  # type: ignore[arg-type]
            except Exception:
                continue
        elif line.startswith("measure"):
            # measure q[i] -> c[j]
            m = re.search(r"q\[(\d+)\]", line)
            if m:
                gates.append(Gate(name="measure", targets=(int(m.group(1)),)))
    if n_qubits == 0 and gates:
        n_qubits = max(max(g.targets) for g in gates) + 1
    return QASMProgram(
        n_qubits=n_qubits,
        n_clbits=n_clbits,
        gates=gates,
        hor_force=hor_force_cond,
        hor_certify_shots=hor_shots,
        hor_certify_delta=hor_delta,
        raw=text,
    )


def _parse_kv(s: str) -> dict[str, Any]:
    """Parse a key-value string like ``gap_open: true, symmetry: "C4"``."""
    # Try JSON first
    try:
        return json.loads("{" + s + "}")
    except Exception:
        pass
    # Fall back to manual parsing
    result: dict[str, Any] = {}
    for pair in s.split(","):
        if ":" not in pair:
            continue
        k, v = pair.split(":", 1)
        k = k.strip().strip('"').strip("'")
        v = v.strip().strip('"').strip("'")
        if v.lower() in ("true", "false"):
            result[k] = v.lower() == "true"
        else:
            try:
                result[k] = int(v)
            except ValueError:
                try:
                    result[k] = float(v)
                except ValueError:
                    result[k] = v
    return result
