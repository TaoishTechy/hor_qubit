# Backends

HOR-Qubit's router picks the cheapest backend that meets the user's
error budget, or returns a `StructuredRefusal` with concrete
alternatives.

## Backend catalog

### R1 — Statevector (dense)

Memory: `b * 4^n` bytes (density matrix, `b=8` c64 or `b=16` c128).

| $n$ | Memory (c128) | Memory (c64) |
|---|---|---|
| 12 | 256 KiB | 128 KiB |
| 16 | 4 GiB | 2 GiB |
| 20 | 1 TiB | 512 GiB |
| 24 | 16 PiB | 8 PiB |

**Limit:** $n \le 16$ on 16 GiB RAM (density matrix), $n \le 30$ on 16 GiB (statevector c64).

**Fidelity:** exact (within $10^{-14}$ floating-point floor).

### R2 — Sparse

Memory: `nnz * (b + ceil(n/8))` bytes.

**Use case:** circuits where the statevector stays sparse (e.g., GHZ,
QFT on a basis state, shallow classical-oracle circuits).

### R3 — MPS / TEBD

Memory: `2 * n * chi^2 * b` bytes.

| $n$ | $\chi$ | Memory (c128) |
|---|---|---|
| 100 | 16 | 200 KiB |
| 1000 | 64 | 26 MB |
| $10^6$ | 64 | 131 GB |
| $10^6$ | 2 | 128 MB (GHZ-exact) |

**Use case:** area-law entangled states, 1D systems, shallow circuits.

**Truncation accounting:** Cumulative discarded weight $\varepsilon_{trunc}$ is
tracked per bond and reported in the certificate.

**Schuch-Vidal bound:** Random circuits saturate $\chi$ after depth
$\sim \log_2 \chi$ per layer. Router refuses MPS for 2D volume-law.

### R4 — Stabilizer (Gottesman-Knill)

Memory: $2n(2n+1)/8$ bytes per tableau.

| $n$ | Memory |
|---|---|
| 100 | 5 KB |
| $10^4$ | 25 MB |
| $10^5$ | 2.5 GB |
| $10^6$ | 250 GB |
| $420\text{M}$ | 88 PB (infeasible — use Pauli frames or graph states) |

**Use case:** Clifford-only circuits ($\{H, S, X, Y, Z, \sqrt{X}, CNOT, CZ\}$).

**Fidelity:** exact.

### R5 — Product state

Memory: $n \cdot d \cdot b$ bytes.

| $n$ | Memory (c64) |
|---|---|
| 100 | 1.6 KB |
| $10^6$ | 16 MB |
| $420\text{M}$ | 6.7 GB |

**Use case:** no entanglement. The "honest 420M" — a *storage
certificate*, not a *computation certificate*. $S_{usable} = 0$.

### R6 — Trajectory sampling (stub)

Memory: `n_traj * b * 2^n` bytes (sequential: one trajectory at a time).

Statistical error: $\varepsilon_{traj} = \sigma / \sqrt{N_{traj}}$.

**Use case:** density matrix simulation for $n > 14$ (where R1 density
matrix is infeasible).

### R7 — Cloud escalation (stub)

Offload to IBM Quantum, Google Sycamore, IonQ, etc. Provider queue
latency model: $T_{queue} = \lambda / (\mu - \lambda)$ (M/M/1).

## HOR-Qudit extension lane

The extension pack (audited; real math only) adds 5 specialized
backends, dispatched by the router when the circuit signature matches.

### Sheaf backend (E145-E148)

Cellular sheaf cohomology $H^1(X, \mathcal{F})$ obstruction detection.

**Use case:** detect syndrome-invisible logical errors; trigger decoder
escalation (MWPM → BP+OSD/RSB).

**Memory:** $O(|X|)$ where $|X|$ is the number of cells.

**Reality audit:** standard algebraic topology (Hansen-Ghrist 2019).
**Not** a physical statement about ERD fields.

### Barcode backend (E149-E153)

Persistent homology of defect point clouds. $O(\log N)$ syndrome
retrieval via interval tree.

**Use case:** automatic syndrome classification without threshold
tuning; rigorous error threshold from bottleneck stability theorem.

**Memory:** $O(N \log N)$ build; $O(N)$ storage.

**Reality audit:** standard TDA (Cohen-Steiner-Edelsbrunner-Harer 2007).

### HOTI backend (E154-E158)

Nested Wilson loop, quadrupole moment $q_{xy} \in \mathbb{Z}_2$ for
$C_4$-symmetric Hamiltonians (BBH model).

**Use case:** topological invariant computation for HOTI circuits.

**Reality audit:** standard HOTI literature (Benalcazar-Bernevig-Hughes
2017). The specific $Q_{corner} = \phi^{-2}$ claim is a *design choice*
of the phi-tiling, not a topological necessity.

### Transfer operator backend (E159-E162)

Perron-Frobenius transfer operator for translation-invariant circuits.

**Use case:** $O(\dim^3 \log T)$ evolution of translation-invariant
systems (vs $O(T \dim^2)$ step-by-step).

**Reality audit:** standard dynamical systems (Oseledets, Anosov-Bowen
shadowing).

### QES backend (E163-E166)

Island-formula generalized entropy $S_{gen}(R)$ for holographic-geometry
circuits.

**Use case:** closed-form entanglement entropy without simulating the
circuit, when the circuit geometry is holographic.

**Reality audit:** standard holographic QEC (Penington 2019; Almheiri
et al. 2019).

## Router decision tree

```
1. Clifford only?                       -> R4 stabilizer
2. n <= 16 (c128) / n <= 17 (c64)?      -> R1 statevector
3. Sparse (nnz / 2^n < 1/3)?            -> R2 sparse
4. 1D / area-law and chi budget fits?   -> R3 MPS
5. No entangling gates?                 -> R5 product
6. Density matrix n > 14?               -> R6 trajectory
7. Topological structure?               -> extension lane (sheaf/HOTI/...)
8. Otherwise: StructuredRefusal with alternatives
```

## Structured refusals

Every refusal carries at least 2 alternatives, each with a cost model
and a condition:

```python
@dataclass
class StructuredRefusal:
    reason: str
    detail: str
    requested_n: int
    requested_bytes: int
    available_bytes: int
    alternatives: list[Alternative]

@dataclass
class Alternative:
    backend: str              # e.g. "R3", "light_cone", "R7_cloud"
    params: dict              # e.g. {"chi": 1024}
    memory_bytes: int
    f_cert_estimate: float
    condition: str            # when this alternative applies
    caveat: str               # limitations
```

No refusal is a dead end. The user always has a path forward.
