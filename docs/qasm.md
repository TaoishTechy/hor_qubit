# HOR-QASM v0.3

A minimal OpenQASM 2.0 subset plus `hor.` extension directives. A
parser that ignores `hor.` lines yields a valid standard program.

## Syntax

```
horq q[N]; c[M];

// Standard gates
h q[0]; s q[0]; t q[0]; x q[0]; y q[0]; z q[0]; sx q[0];
cx q[0], q[1]; cz q[0], q[1]; iswap q[0], q[1];
rx(0.5) q[0]; ry(0.3) q[1]; rz(0.7) q[0];
u3(0.5, 0.3, 0.7) q[0];
ccx q[0], q[1], q[2];

// Measurement
measure q[0] -> c[0];

// HOR extension directives (ignored by standard parsers)
hor.force {gap_open: true, symmetry: "C4", max_bond: 64};
hor.certify {shots: 8192, target_delta: 0.001};
hor.route {chi_max: 64};
```

## Gates

| Name | QASM | Qubits | Parameters | Clifford? |
|---|---|---|---|---|
| Hadamard | `h` | 1 | — | yes |
| Phase | `s` | 1 | — | yes |
| T | `t` | 1 | — | no |
| Pauli-X | `x` | 1 | — | yes |
| Pauli-Y | `y` | 1 | — | yes |
| Pauli-Z | `z` | 1 | — | yes |
| sqrt(X) | `sx` | 1 | — | yes |
| CNOT | `cx` / `cnot` | 2 | — | yes |
| CZ | `cz` | 2 | — | yes |
| iSWAP | `iswap` | 2 | — | no |
| sqrt(iSWAP) | `sqrtiswap` | 2 | — | no |
| RX | `rx(theta)` | 1 | 1 | at theta=0, pi |
| RY | `ry(theta)` | 1 | 1 | at theta=0, pi |
| RZ | `rz(theta)` | 1 | 1 | at theta=0, pi/2, pi, 3pi/2 |
| U3 | `u3(theta, phi, lam)` | 1 | 3 | no |
| Toffoli | `ccx` / `toffoli` | 3 | — | no |

## HOR directives

### `hor.force`

Apply a forcing condition. The compiler only proceeds if `p \Vdash \phi`
for the required invariant `phi`.

```
hor.force {gap_open: true, min_gap_ghz: 0.5, symmetry: "C4", max_bond: 64};
```

JSON schema:

```json
{
  "gap_open": true,
  "min_gap_ghz": 0.5,
  "symmetry": "C4" | "U1" | "Z2" | null,
  "max_bond": 64,
  "button_required": true
}
```

### `hor.certify`

Request certification with a target shot count and confidence.

```
hor.certify {shots: 8192, target_delta: 0.001, target_eps: 0.001, threshold: 0.999};
```

### `hor.route`

Specify backend routing preferences.

```
hor.route {chi_max: 64, cutoff: 1e-10, allow_dense: true};
```

## Backwards compatibility

Stripping `hor.` lines yields a valid standard program. This is
enforced by `tests/test_compatibility.py`:

```python
from hor.core.compatibility import strip_hor_pragmas

standard_qasm = strip_hor_pragmas(hor_qasm)
# `standard_qasm` is a valid OpenQASM 2.0 program
```

## Parser limitations

The `hor.api.qasm.parse_qasm` parser is a minimal reference
implementation. For production QASM, use `qiskit.qasm2` or `cirq.read_json`.

Supported:
- `horq` / `q` / `c` register declarations
- Gates listed above
- `measure q[i] -> c[j]`
- `hor.*` directives with JSON-like arguments

Not supported:
- `gate` definitions (custom gates)
- `if` statements (classical control)
- `barrier`
- Custom noise declarations
