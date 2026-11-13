"""hor.api.cli — Command-line interface.

Usage::

    hor run circuit.qasm --shots 8192 --chi 64 --certify
    hor certify circuit.qasm --output cert.json
    hor route circuit.qasm --dry-run
    hor probe                  # hardware probe (stub)
"""

from __future__ import annotations

import argparse
import json
import sys

from .horqubit import HORQubit, CertifyConfig
from .qasm import parse_qasm
from ..core.registers import ForcingCondition


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="hor", description="HOR-Qubit CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Run
    p_run = sub.add_parser("run", help="Run a circuit")
    p_run.add_argument("circuit", help="QASM file path")
    p_run.add_argument("--shots", type=int, default=8192)
    p_run.add_argument("--chi", type=int, default=64)
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--certify", action="store_true")
    p_run.add_argument("--output", "-o", default=None, help="Output JSON file")

    # Certify
    p_cert = sub.add_parser("certify", help="Build a certificate without running")
    p_cert.add_argument("circuit", help="QASM file path")
    p_cert.add_argument("--shots", type=int, default=8192)
    p_cert.add_argument("--output", "-o", default=None)

    # Route
    p_route = sub.add_parser("route", help="Show backend routing decision")
    p_route.add_argument("circuit", help="QASM file path")
    p_route.add_argument("--dry-run", action="store_true")

    # Probe
    sub.add_parser("probe", help="Probe hardware (stub)")

    # Version
    sub.add_parser("version", help="Print version")

    args = parser.parse_args(argv)

    if args.cmd == "version":
        from .. import __version__
        print(__version__)
        return 0

    if args.cmd == "probe":
        print("HOR-Qubit hardware probe (stub)")
        print(f"  Python: {sys.version.split()[0]}")
        import numpy as np
        print(f"  NumPy: {np.__version__}")
        try:
            import blake3
            print(f"  BLAKE3: {blake3.__name__} (optional extra installed)")
        except ImportError:
            print("  BLAKE3: not installed (using SHA-256 stand-in)")
        return 0

    # Other commands need to load a QASM file
    with open(args.circuit, "r", encoding="utf-8") as f:
        qasm_text = f.read()
    program = parse_qasm(qasm_text)

    if args.cmd == "run":
        q = HORQubit(n=program.n_qubits, chi_max=args.chi)
        # Apply gates
        for g in program.gates:
            _apply_gate(q, g)
        # HOR force
        if program.hor_force is not None:
            q.hor_force(program.hor_force)
        # Certify
        if args.certify:
            q.hor_certify(CertifyConfig(shots=args.shots))
        # Run
        result = q.run(shots=args.shots, seed=args.seed)
        out = {
            "counts": result.counts,
            "status": result.status,
            "reason": result.reason,
            "backend": result.backend,
            "truncation_error": result.truncation_error,
        }
        if result.certificate is not None:
            out["certificate"] = result.certificate.to_dict()
        _emit(out, args.output)
        return 0 if result.status != "refused" else 1

    if args.cmd == "certify":
        q = HORQubit(n=program.n_qubits, chi_max=64)
        for g in program.gates:
            _apply_gate(q, g)
        if program.hor_force is not None:
            q.hor_force(program.hor_force)
        q.hor_certify(CertifyConfig(shots=args.shots))
        result = q.run(shots=args.shots)
        out = result.certificate.to_dict() if result.certificate else {"error": "no certificate"}
        _emit(out, args.output)
        return 0

    if args.cmd == "route":
        q = HORQubit(n=program.n_qubits, chi_max=64)
        for g in program.gates:
            _apply_gate(q, g)
        choice = q.hor_route()
        out = {
            "backend": choice.backend,
            "reason": choice.reason,
            "estimated_cost": choice.estimated_cost,
            "estimated_error": choice.estimated_error,
            "chi": choice.chi,
            "alternatives": [
                {
                    "backend": alt.backend,
                    "params": alt.params,
                    "memory_bytes": alt.memory_bytes,
                    "f_cert_estimate": alt.f_cert_estimate,
                    "condition": alt.condition,
                    "caveat": alt.caveat,
                }
                for alt in choice.alternatives
            ],
        }
        _emit(out, None)
        return 0

    return 1


def _apply_gate(q: HORQubit, g) -> None:
    """Apply a parsed gate to a HORQubit instance."""
    name = g.name
    targets = g.targets
    params = g.params
    if name == "h":
        q.h(targets[0])
    elif name == "s":
        q.s(targets[0])
    elif name == "t":
        q.t(targets[0])
    elif name == "x":
        q.x(targets[0])
    elif name == "y":
        q.y(targets[0])
    elif name == "z":
        q.z(targets[0])
    elif name == "sqrtx":
        q.sqrtx(targets[0])
    elif name in ("cnot", "cx"):
        q.cnot(targets[0], targets[1])
    elif name == "cz":
        q.cz(targets[0], targets[1])
    elif name == "iswap":
        q.iswap(targets[0], targets[1])
    elif name == "rx":
        q.rx(params[0], targets[0])
    elif name == "ry":
        q.ry(params[0], targets[0])
    elif name == "rz":
        q.rz(params[0], targets[0])
    elif name == "u3":
        q.u3(*params, targets[0])
    elif name == "toffoli":
        q.toffoli(targets[0], targets[1], targets[2])
    elif name == "measure":
        q.measure(targets[0])
    elif name == "reset":
        q.reset(targets[0])


def _emit(obj: dict, output: str | None) -> None:
    """Emit a JSON object to stdout or a file."""
    text = json.dumps(obj, indent=2, default=str)
    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {output}")
    else:
        print(text)


if __name__ == "__main__":
    sys.exit(main())
