# Roadmap

## Status

| Version | Status | Focus |
|---|---|---|
| v0.1 | spec only | Original ill-typed tensor-product formulation |
| v0.1.5 | spec only | Type correction: cq-state, split dynamics |
| **v0.2** | **shipped in this repo** | Reference simulator, R1-R5 routing, certificate |
| **v0.3** | **shipped in this repo** | Calibration import, leakage, readout mitigation |
| v0.4 | planned | Forcing compiler prototype, HOTI testbed, qLDPC accounting |
| v1.0 | planned | Signed manifests, cloud escalation, full falsifiability suite |

## v0.4 — Forcing compiler + HOTI testbed

### Forcing compiler (A* search)

Implement forcing-condition-aware transpilation:

```python
def forcing_compile(circuit, target_phi, poset):
    # A* search over the forcing poset P
    # heuristic: h(p) = c_min * d_min(p, phi) + lambda_gap * (1 - gap(p))
    # admissible iff c_min and d_min are valid lower bounds
    ...
```

Button/switch classification per Hamkins-Loewe. T3 test: ≥15% relative
reduction in mis-routing vs Qiskit `optimization_level=3`.

### HOTI testbed

Implement the BBH Hamiltonian on an $L \times L$ lattice:

$$
H_{BBH}(\mathbf{k}) = [\gamma + \lambda \cos k_x]\Gamma_4 + \lambda \sin k_x \Gamma_3
+ [\gamma + \lambda \cos k_y]\Gamma_2 + \lambda \sin k_y \Gamma_1
$$

T4 test: scar intensity $Q = \partial_t \|H^1\|^2$ correlates with
interface error in HOTI boundary circuits.

### qLDPC accounting

Track surface code, $[[144, 12, 12]]$ gross code, and quantum Tanner
codes:

| Family | $p_{th}$ | $d$ formula | Decoder |
|---|---|---|---|
| Surface | 0.6–0.7% | $2d^2$ | MWPM |
| Gross | 0.7–0.8% | 12 (fixed) | BP+OSD |
| Quantum Tanner | 0.5–0.7% | $\Omega(n)$ | Linear-time |

## v1.0 — Cloud escalation + full falsifiability

### Cloud escalation (R7)

- M/M/1 queue latency model
- Offload decision: $T_{queue} + T_{cloud} < T_{local}$ AND $F_{cloud} > F_{local}$
- Hybrid execution: split circuit, send boundary state
- Cost per certified qubit: $\mathrm{CPCQ} = \mathrm{cost} / (\log D_{cert} \cdot F_{cert})$

### Falsifiability suite

Pre-registered tests with metrics, baselines, sample sizes:

| Test | Hypothesis | Pass criterion |
|---|---|---|
| T1 | Sheaf gap predicts fidelity loss > gate error alone | AUC improvement ≥ 0.05, $p < 0.05$, $N=200$ |
| T2 | Persistence lifetime correlates with MPS truncation | Spearman $\rho > 0.5$, $p < 0.01$, $N=100$ |
| T3 | Forcing routing reduces mis-routing ≥ 15% vs Qiskit | $N=150$ circuits |
| T4 | Scar intensity $Q$ correlates with interface error | Pearson $r > 0.38$ (Bonferroni), $N=80$ |
| T5 | Variance-aware planner reduces shots ≥ 20% | $N=10$ Hamiltonians |
| T6 | Memory layer extends $n$ from 28 → 30 at measured cost | p95 < 50 ms gate latency |

### Signed manifests

PKI with key rotation and revocation list. Signer key id in manifest;
old keys retained for verification.

### Optional lifts (research-grade)

- **Condensed mathematics** (Clausen-Scholze): condensed sets for
  Hollow, solid modules for Resonant. Available for v1.0.
- **HoTT** (Cubical Agda): $\Sigma$-type certificate as a HIT.
  Machine-checkable.

## Honest limits (won't be fixed)

These are physics, not engineering:

- Exponential Hilbert space for generic entangled states
- Bekenstein bound: $I \le 2\pi R E / (\hbar c \ln 2)$ bits
- Landauer bound: $E \ge k_B T \ln 2$ per erased bit
- Quantum speed limits (Mandelstam-Tamm, Margolus-Levitin, Lloyd)
- Decoherence, leakage, and fault-tolerance thresholds
- 420M *entangled* qubits (Hilbert dimension + Bekenstein)
- Side channels (process isolation reduces risk; doesn't eliminate)

## Release schedule (suggested)

| Sprint | Deliverable |
|---|---|
| 1 (done) | Core, gates, R1, API |
| 2 (done) | R4 stabilizer, router skeleton |
| 3 (done) | R3 MPS, truncation accounting |
| 4 (done) | Shot planner, certificate, CI, docs |
| 5 (done) | Calibration importer, canonical schema |
| 6 (done) | Leakage tracking, $F_{cert}$ update |
| 7 (done) | Readout mitigation, negativity guard, PKI rotation |
| 8 (next) | Forcing compiler prototype (A*) |
| 9 | HOTI testbed (BBH Hamiltonian) |
| 10 | qLDPC accounting + cloud escalation |
| 11 | Full falsifiability suite T1–T6 |
| 12 | v1.0 release: signed manifests, reproducibility audits |
