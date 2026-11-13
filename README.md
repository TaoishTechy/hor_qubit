# HOR-Qubit

**Hollow Ontological Resonant Qubit** — a standard $d=2$ qubit plus three certified classical metadata layers (Hollow, Generic, Resonant) that travel with it through compilation, simulation, and readout.

> We hollow. We force. We type-check. We calibrate. We remain falsifiable.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](tests/)

---
<img width="1168" height="784" alt="image" src="https://github.com/user-attachments/assets/f92ec647-e514-4afd-95c5-3e1b96e0bae2" />
---

## What HOR-Qubit is

A HOR-Qubit is **not** a new particle. It is a standard $d=2$ qubit plus three certified *classical* metadata layers that travel with it. When those layers are in vacuum, the HOR-Qubit **is** a qubit, bit for bit.

$$
\rho_{HOR} = \sum_{c} p_c \, \rho_2^{(c)} \otimes |c\rangle\langle c|_{HGR}
$$

- $\rho_2^{(c)}$: the physical qubit density matrix ($2^n \times 2^n$), lives in $\mathcal{H}_2 = (\mathbb{C}^2)^{\otimes n}$
- $c = (h, g, r)$: classical registers (Hollow, Generic, Resonant), stored diagonally
- **No entanglement** between $\mathcal{H}_2$ and $C_{HGR}$ is ever created — enforced by construction

Projection recovers the qubit exactly:

$$
\mathrm{Tr}_{HGR}\!\left[\rho_{HOR}^{vac}\right] = \rho_2
$$

This is the **backwards compatibility guarantee**. Stripping `hor.` pragmas from any HOR circuit yields the exact original standard circuit.

## What HOR-Qubit is **not**

- It does **not** beat the exponential Hilbert space wall.
- It does **not** claim universal 99.9% efficiency. Per-block $F_{cert} \geq 0.999$ is a ledger threshold, not a global efficiency claim.
- It does **not** replace the Born rule, the Bloch sphere, or quantum mechanics.
- It does **not** make classical simulation equivalent to hardware.
- It does **not** evade Landauer, Bekenstein, or quantum speed limits — it tracks them.

## Architecture

```
HOR-Qubit = standard qubit
          + Hollow layer    (topological / sheaf / persistence diagnostics)
          + Generic layer   (forcing-based compilation proof chain)
          + Resonant layer  (coherence / reservoir / thermodynamic ledger)
```

Each layer is a **classical register**. The quantum state $\rho_2$ evolves under standard quantum dynamics ($U\rho_2 U^\dagger$ or Lindblad). The classical registers update via deterministic channels conditioned on gate type and measurement outcome — never via quantum superposition.

## Backends

| Backend  | What it does                              | Honest limit                                  |
|----------|-------------------------------------------|-----------------------------------------------|
| **R1**   | Statevector, dense $2^n$                  | 30 qubits in 16 GiB RAM (complex64)           |
| **R2**   | Sparse amplitude dictionary               | Only if state stays sparse                    |
| **R3**   | MPS / TEBD with bond $\chi$               | Area-law only; volume-law saturates $\chi$    |
| **R4**   | Stabilizer (Gottesman–Knill)              | Clifford only; $T$ forces fallback            |
| **R5**   | Product state                             | $S_{usable} = 0$; storage certificate only   |
| **R6**   | Trajectory sampling (quantum jumps)       | Density matrix beyond $n=14$; statistical err |
| **R7**   | Cloud escalation (stub)                   | Provider queue, hardware fidelity             |

The router picks the cheapest backend that meets the user's error budget **or** returns a structured refusal with concrete alternatives.

## Certificate

Every run produces a typed certificate (Σ-type, not an `iff` of mixed types):

```python
@dataclass
class Certificate:
    forcing_proof: ForcingProof      # chain p0 ≤ p1 ≤ ... with φ preserved
    f_cert: float                    # F_state · F_process · (1 - ε_trunc) · (1 - ε_shot)
    manifest_hash: str               # BLAKE3 of canonical JSON
    signature: str                   # Ed25519 over manifest_hash
    backend: BackendChoice
    truncation_error: float
    shot_budget: ShotBudget
    resource_budgets: ResourceBudgets
    calibration_id: str              # "calib: none" or a fresh calibration id
    status: Literal["certified", "uncertified", "refused"]
    reason: str | None
```

$$
F_{cert} = F_{state} \cdot F_{process} \cdot (1 - \varepsilon_{trunc}) \cdot (1 - \varepsilon_{shot})
$$

A block is `certified` iff $F_{cert} \geq 0.999$ (configurable). A signed certificate from a buggy simulator is still wrong — HOR requires **reproducibility** (same code + same calibration id ⇒ same hash).

## Installation

```bash
git clone https://github.com/TaoishTechy/hor-qubit.git
cd hor-qubit
pip install -e .
```

Optional extras:

```bash
pip install -e ".[crypto]"   # blake3, pyspx (Ed25519)
pip install -e ".[viz]"      # matplotlib for plotting
pip install -e ".[dev]"      # pytest, ruff, mypy
```

## Quick start

```python
from hor import HORQubit, ForcingCondition, CertifyConfig

q = HORQubit(n=2, chi_max=64)
q.h(0)
q.cnot(0, 1)
q.rz(0.5, 0)

q.hor_force(ForcingCondition(gap_open=True, symmetry="C4", max_bond=64))
cert = q.hor_certify(CertifyConfig(shots=8192, target_delta=0.001))

result = q.run()
print(result.counts)
print(result.certificate.f_cert, result.certificate.backend)
print(result.status, result.reason)
```

CLI:

```bash
hor run circuit.qasm --shots 8192 --chi 64 --certify
hor certify circuit.qasm --output cert.json
hor route circuit.qasm --dry-run
```

## Backwards compatibility theorem

For any $n$-qubit circuit $C$ built from $\{H, S, T, X, Y, Z, \sqrt{X}, CNOT, CZ, iSWAP, RX, RY, RZ, U3, Toffoli\}$ and measurement in $Z$:

$$
P_{HOR}(x \mid C, \rho_{HOR}^{vac}) = P_{standard}(x \mid C, \rho_2)
$$

up to the classical simulation floating-point floor $\sim 10^{-14}$ per gate.

This is enforced empirically in CI: `tests/test_compatibility.py` runs a corpus of random circuits with and without `hor.` pragmas and asserts TVD $< 10^{-12}$.

## Falsifiability

HOR-Qubit is falsified as useful if any of these tests fail repeatedly:

| Test | Hypothesis                                                       |
|------|------------------------------------------------------------------|
| T1   | Sheaf gap $\lambda_1$ predicts fidelity loss > gate error alone  |
| T2   | Persistence lifetime correlates with MPS truncation error        |
| T3   | Forcing routing reduces mis-routing ≥15% vs Qiskit transpiler    |
| T4   | Scar intensity $Q$ correlates with interface error in HOTI      |
| T5   | Variance-aware shot planner gives ≥20% reduction vs uniform      |
| T6   | Memory layer extends effective $n$ from 28 → 30 at measured cost |

Each test has a pre-registered metric, baseline, sample size, significance level, and power. See `tests/falsifiability/`.

## Project structure

```
hor-qubit/
├── hor/
│   ├── core/         # cq-state, classical registers, compatibility theorem
│   ├── gates/        # full v0.1.5 gate set + HOR meta-operations
│   ├── sim/          # R1 statevector, R2 sparse, R3 MPS, R4 stabilizer, R5 product, R6 trajectory
│   ├── cert/         # Certificate builder, F_cert, forcing proof, BLAKE3/Ed25519
│   ├── shots/        # Hoeffding / Bernstein / median-of-means / Neyman planner
│   ├── calib/        # v0.3: calibration import, leakage, readout mitigation
│   ├── memory/       # PAZUZU swap integration interface (pFACIL adapter)
│   └── api/          # HORQubit class, QASM parser, CLI
├── tests/
├── examples/
├── docs/
└── pyproject.toml
```

## Versions

| Version | Status        | Focus                                              |
|---------|---------------|----------------------------------------------------|
| v0.1    | Spec only     | Original ill-typed tensor-product formulation      |
| v0.1.5  | Spec only     | **Type correction**: cq-state, split dynamics      |
| v0.2    | ✅ This repo  | Reference simulator, R1–R4 routing, certificate    |
| v0.3    | ✅ This repo  | Calibration import, leakage, readout mitigation    |
| v0.4    | Planned       | Forcing compiler, HOTI testbed, qLDPC accounting   |
| v1.0    | Planned       | Signed manifests, cloud escalation, full falsifiability |

## Honest limits

HOR does **not** fix:
- Exponential Hilbert space for generic entangled states
- Bekenstein bound: $I \leq 2\pi R E / (\hbar c \ln 2)$ bits
- Landauer bound: $E \geq k_B T \ln 2$ per erased bit
- Quantum speed limits (Mandelstam–Tamm, Margolus–Levitin, Lloyd)
- Decoherence, leakage, and fault-tolerance thresholds

HOR **does** fix:
- Silent backend switching (reports representation change + fidelity cost)
- Silent T-cost (tracks T-count, magic state yield, stabilizer extent)
- Silent packing waste (reports $\eta_{pack}$)
- Silent readout drift (flags negativity mass and stale calibration)
- Silent regime errors (certifies Clifford vs MPS vs statevector regime)

## References

- Aaronson–Gottesman CHP tableau algorithm (Phys. Rev. A 70, 052328, 2004)
- Hansen–Ghrist cellular sheaf Laplacian (J. Appl. Comput. Topol., 2019)
- Cohen-Steiner–Edelsbrunner–Harer persistence stability
- Huang–Kueng–Preskill classical shadows (Nat. Phys., 2020)
- Veitch–Ferrie–Gross–Emerson resource theory of magic
- Baumgratz–Cramer–Plenio resource theory of coherence
- Clausen–Scholze condensed mathematics (for v1.0 lift)

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Citation

```bibtex
@software{hor_qubit,
  title  = {HOR-Qubit: Hollow Ontological Resonant Qubit Framework},
  author = {TaoishTechy},
  year   = {2026},
  url    = {https://github.com/TaoishTechy/hor-qubit}
}
```

---

$$
\boxed{\text{We hollow. We force. We type-check. We calibrate. We remain falsifiable.}}
$$
