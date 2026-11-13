# Architecture

This document describes the internal architecture of `hor-qubit` v0.3.

## 1. The cq-state core (v0.1.5 type correction)

The HOR-Qubit state is a **classical-quantum (cq) state**:

$$
\rho_{HOR} = \sum_c p_c \, \rho_2^{(c)} \otimes |c\rangle\langle c|_{HGR}
$$

- $\rho_2^{(c)}$ is a $2^n \times 2^n$ quantum density matrix
- $c = (h, g, r)$ is a classical register tuple (Hollow, Generic, Resonant)
- $|c\rangle\langle c|_{HGR}$ is a classical state stored diagonally

The **vacuum** is:
$$
\rho_{HOR}^{vac} = \rho_2 \otimes |0\rangle\langle 0|_{HGR}, \quad \mathrm{Tr}_{HGR}[\rho_{HOR}^{vac}] = \rho_2
$$

This is the type correction that v0.1 lacked. v0.1 wrote a naive tensor
product $|\psi\rangle_2 \otimes |h\rangle \otimes |g\rangle \otimes |r\rangle$ that conflated
classical records with quantum amplitudes; that would have broken the
Born rule whenever the metadata entangled with the qubit.

### Why the split matters

**Quantum evolution** drives only $\rho_2$:
$$
\rho_2 \to U \rho_2 U^\dagger \quad \text{or} \quad \dot{\rho}_2 = -i[H_2, \rho_2] + \sum_k \mathcal{D}[L_k](\rho_2)
$$

**Classical updates** drive only the registers:
$$
c \to f_{\text{classical}}(c, U)
$$

The classical update is a deterministic function (not a quantum
channel), so it **cannot** create entanglement between $\rho_2$ and
$C_{HGR}$. This is enforced by construction.

### Files

- `hor/core/state.py` — `HORState`, `make_vacuum`, evolution laws
- `hor/core/registers.py` — `HollowRecord`, `GenericRecord`, `ResonantRecord`
- `hor/core/compatibility.py` — backwards compatibility theorem

## 2. Gate engine

Full v0.1.5 expanded gate set:

| Category | Gates |
|---|---|
| **Clifford** | $H, S, X, Y, Z, \sqrt{X}, CNOT, CZ$ |
| **Non-Clifford** | $T, \text{Toffoli}$ |
| **Parameterized** | $RX(\theta), RY(\theta), RZ(\theta), U3(\theta, \phi, \lambda)$ |
| **Hardware 2Q** | $iSWAP, \sqrt{iSWAP}, XX, YY, ZZ, \text{Mølmer–Sørensen}$ |
| **Mid-circuit** | `measure`, `reset`, `if_cbit` feedforward |

HOR meta-operations are **classical compiler operations**, not gates.
They form a monoid with identity `hor.id` and associative composition.

### Cost tracking

Each gate carries both `cost_sim` (classical simulation flops) and
`cost_ft` (fault-tolerant T-equivalents). This fixes v0.1 issue A7-74
(T-cost misattribution): in classical simulation T and Clifford have
similar per-gate cost; in fault-tolerant hardware T is 10–100× more
expensive due to magic state distillation.

### Files

- `hor/gates/gates.py` — matrices, `Gate` dataclass, cost properties
- `hor/gates/meta.py` — `HORForce`, `HORCertify`, `HORScarRead`, `HORRoute`

## 3. Backends

| Backend | Module | Use case |
|---|---|---|
| R1 statevector | `hor/sim/statevector.py` | $n \le 30$ dense |
| R2 sparse | (stub) | Few non-zero amplitudes |
| R3 MPS | `hor/sim/mps.py` | Area-law, 1D |
| R4 stabilizer | `hor/sim/stabilizer.py` | Clifford only (Gottesman–Knill) |
| R5 product | `hor/sim/product.py` | No entanglement (420M storage) |
| R6 trajectory | (stub) | Density matrix $n > 14$ |
| R7 cloud | (stub) | Escalation |

### Router

`hor/sim/router.py` evaluates the circuit feature vector $\phi(C)$ and
picks the cheapest feasible backend. If no backend fits, it returns a
`StructuredRefusal` with concrete alternatives (R3 MPS, light-cone
pruning, sampling, cloud) — never a dead-end refusal.

### HOR-Qudit extension lane

`hor/sim/extension/` adds 5 backends from the HOR-Qudit Extension Pack
(real math only, audited):

| Backend | Equations | Purpose |
|---|---|---|
| Sheaf | E145–E148 | Cellular sheaf $H^1$ obstruction detection |
| Barcode | E149–E153 | Persistent homology syndrome, $O(\log N)$ access |
| HOTI | E154–E158 | Nested Wilson loop, quadrupole $q_{xy} \in \mathbb{Z}_2$ |
| Transfer operator | E159–E162 | Perron–Frobenius, Lyapunov exponents |
| QES | E163–E166 | Island-formula generalized entropy |

**Explicitly rejected** (fictional, not implemented):
Sophia Point as physical attractor, ERD field as physical scalar,
"420M entangled qudits", love field, miracle operator, consciousness
collapse, vacuum harvesting.

## 4. Certificate (Sigma-type, not iff)

v0.1 wrote the certification equation as an *iff* mixing set theory, a
number, and a hash — a type error. v0.1.5 fixes this as a Sigma-type:

```typescript
type Certificate = {
  forcing_proof: ForcingProof,      // chain p_0 ≤ p_1 ≤ ... with φ preserved
  f_cert: number,                   // F_state · F_process · (1 - eps_trunc) · (1 - eps_shot)
  manifest_hash: string,            // BLAKE3 of canonical serialization
  signature: string,                // Ed25519 over manifest_hash
  backend: BackendChoice,
  truncation_error: number,
  shot_budget: ShotBudget,
  resource_budgets: ResourceBudgets,
  calibration_id: string,           // "calib: none" in v0.2
  status: "certified" | "uncertified" | "refused",
  reason: string | null,
  // v0.3 calibration fields
  leakage_max: number,
  readout_negativity: number,
  // HOR-Qudit extension fields (E209, E203)
  classification: dict[str, (value, category)],
  trl: TRL,
}
```

$F_{cert}$ formula:

$$
F_{cert} = F_{state} \cdot F_{process} \cdot (1 - \varepsilon_{trunc}) \cdot (1 - \varepsilon_{shot})
$$

Threshold: $F_{cert} \geq 0.999$ (configurable).

### Cryptographic primitives

- **BLAKE3** (E191): ~GB/s tree hashing
- **Ed25519** (E194): lattice-based signatures
- **Merkle tree** (E192): $O(\log N)$ proof per chunk
- **Hash-chained ledger** (E193): tamper-evident run log

### Bures-angle composition (E205)

For per-step fidelities $F_i$:
$$
\theta_i = \arccos(\sqrt{F_i}), \quad \theta_{total} = \sum_i \theta_i, \quad F_{cert} = \cos^2(\min(\theta_{total}, \pi/2))
$$

This is a rigorous lower bound on the total fidelity. For small losses
it reduces to the product formula; for large losses it saturates at 0.

### Files

- `hor/cert/certificate.py` — `Certificate`, `CertificateBuilder`, `compute_f_cert`
- `hor/cert/crypto.py` — BLAKE3, Ed25519, Merkle, AEAD stubs
- `hor/cert/forcing.py` — `ForcingProof`, verification
- `hor/cert/ledger.py` — `RunLedger`, hash-chained entries

## 5. Shot planner

`hor/shots/planner.py` implements:
- **Hoeffding** bound: $N \ge (b-a)^2 \ln(2/\delta) / (2\varepsilon^2)$
- **Bernstein** bound (variance-aware)
- **Median-of-means**: robust to heavy tails
- **Neyman allocation**: $N_j \propto \sqrt{\mathrm{Var}_j}$
- **Classical shadows** (Huang-Kueng-Preskill): shadow norm $3^w$ for weight-$w$ Paulis

## 6. Calibration (v0.3)

- `hor/calib/importer.py` — HOR JSON canonical format + Qiskit importer
- `hor/calib/leakage.py` — per-qubit leakage accumulator
- `hor/calib/readout.py` — iterative Bayesian unfolding + negativity guard

The negativity guard fires when the mitigated quasi-probability
distribution has more than 5% (configurable) mass on negative values,
indicating that the confusion matrix is stale or poorly conditioned.

## 7. Memory layer (PAZUZU integration interface)

`hor/memory/backend.py` defines the interface for memory-tier-aware
backends. The actual pFACIL daemon (PAZUZU v2.0) is a separate Rust
process; this module is the Python adapter. If the daemon is not
available, the memory layer falls back to plain numpy arrays in RAM.

## 8. API and CLI

`hor/api/horqubit.py` — `HORQubit` class
`hor/api/qasm.py` — minimal QASM parser with `hor.` pragma support
`hor/api/cli.py` — `hor run`, `hor certify`, `hor route`, `hor probe`
