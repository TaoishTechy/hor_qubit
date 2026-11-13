# Falsifiability

HOR-Qubit is falsified as useful if any of these tests fail repeatedly.
Each test has a pre-registered metric, baseline, sample size,
significance level, and power (v0.1.5 §12, v0.2 §11.1).

## Pre-registered tests

### T1 — Sheaf gap predicts fidelity loss

**Hypothesis:** Sheaf gap $\lambda_1(\Delta^{\mathcal{F}}_0)$ predicts
fidelity loss better than gate error alone across test circuits.

**Metric:** ROC AUC for predicting fidelity loss.

**Baseline:** Gate error alone.

**Sample:** $N = 200$ circuits, stratified:
- 50 Clifford (random from $\{H, S, CNOT\}$)
- 50 non-Clifford (random from $\{H, S, T, CNOT\}$)
- 50 random (all gates)
- 50 structured (QFT, GHZ, QAOA)

**Significance:** $\alpha = 0.05$.

**Power:** $0.8$ (Hanley-McNeil variance formula).

**Pass criterion:** $\mathrm{AUC}_{\text{sheaf}} > \mathrm{AUC}_{\text{gate}} + 0.05$
with $p < 0.05$.

### T2 — Persistence vs MPS truncation

**Hypothesis:** Max persistence bar lifetime $\ell_{\max}$ correlates
with $\varepsilon_{trunc}$ at fixed $\chi$.

**Metric:** Spearman correlation $\rho$.

**Sample:** $N = 100$ MPS runs, $\chi \in \{16, 32, 64\}$.

**Stratification:** Half topological circuits (GHZ, toric code ground
state); half random brickwork. The pass criterion is the topological
stratum.

**Pass criterion:** Spearman $\rho > 0.5$, $p < 0.01$.

### T3 — Forcing routing vs Qiskit transpiler

**Hypothesis:** HOR forcing compiler reduces mis-routing ≥ 15% relative
to Qiskit `optimization_level=3`.

**Metric:** Mis-routing rate (fraction of circuits where the chosen
backend exceeds user budget).

**Sample:** $N = 150$ circuits.

**Pass criterion:** Mis-routing reduced by ≥ 15% relative.

**Regime dependence:** HOR may be worse for random circuits (no
structure to exploit). T3 reports results per stratum.

### T4 — Scar intensity vs interface error

**Hypothesis:** Scar intensity $Q = \partial_t \|H^1(\mathcal{F}_\partial)\|^2$
correlates with interface error in HOTI boundary circuits.

**Metric:** Pearson $r$.

**Sample:** $N = 80$ HOTI boundary circuits.

**Multiple-comparison correction:** Bonferroni; corrected
$\alpha' = 0.05 / 80 = 0.000625$.

**Pass criterion:** $r > 0.38$ (Bonferroni-corrected threshold).

**Note:** T4 requires HOTI testbed, which is v0.4. v0.2 and v0.3 do
not block on T4.

### T5 — Shot efficiency

**Hypothesis:** Variance-aware (Bernstein + Neyman) planner reduces
shots to reach $\varepsilon = 0.01$ by ≥ 20% vs uniform allocation.

**Metric:** Shots to reach target error.

**Sample:** $N = 10$ random Hamiltonians with 6 Pauli terms each.

**Pass criterion:** ≥ 20% reduction.

### T6 — Memory efficiency (PAZUZU integration)

**Hypothesis:** PAZUZU swap + zRAM extends effective $n$ from 28 (8 GB
RAM) to 30 (16 GB RAM + 16 GB NVMe) with measured per-gate cost,
without breaking HOR's certificate guarantees.

**Tests:**

| Test | Workload | Baseline | PAZUZU target |
|---|---|---|---|
| T6a | GHZ-30 | Fails (17 GB) | Succeeds on 16+16 GB, $F_{cert} = 1.0$, p95 < 50 ms |
| T6b | QFT-28 | Succeeds on 8 GB | No regression, p95 < 10 ms |
| T6c | Random brickwork-26 | Succeeds on 8 GB | No regression, p95 < 20 ms |
| T6d | MPS-$10^6$, $\chi=64$ | Fails (131 GB) | Succeeds on 16+1 TB, 10 sweeps < 10 min |

**Statistical requirements:** Each test repeated 5× on the same
machine, p95 gate latency computed across all gates, Wilson CI on
success rate.

### T7 — R6 trajectory sampling correctness

**Hypothesis:** R6 with $N_{traj}$ trajectories matches exact density
matrix within $1/\sqrt{N_{traj}}$ statistical error.

**Test:** $n=14$ density matrix, depolarizing noise $p=0.01$, 10 layers.
Exact: 4.29 GB density matrix. R6 with $N_{traj} \in \{100, 1000, 10000\}$.

**Pass:** $|\langle O \rangle_{R6} - \langle O \rangle_{\text{exact}}| \le 3 \sigma_O / \sqrt{N_{traj}}$ in 95% of observables.

### T8 — 40-qubit structured alternative

**Hypothesis:** For 40-qubit local observables, light-cone pruning
matches full simulation exactly; MPS with $\chi=1024$ matches within
$F_{cert} \ge 0.999$.

### T9 — Interactive 30-qubit latency

**Hypothesis:** Path A (c64, no swap) achieves p95 < 50 ms/gate; Path C
(c128, swap) achieves high-gate p95 < 15 ms but low-gate p95 > 4000 ms.

### T10 — 420M product state

**Hypothesis:** 420M product qubits in c64 fit in 6.7 GB and produce
exact Born samples.

### T11 — Landauer/Bekenstein ledger

**Hypothesis:** The certificate's energy and information ledgers are
accurate. RAPL total matches computed memory write + compute within 20%.
Landauer is $>10^{10}$ smaller than memory write.

### T12 — SPMC stability at 420 qubits

**Hypothesis:** Symmetry-Protected MPS Chunks sustain $F_{cert} \ge 0.999$
for 10 sweeps on a 420-site $\chi=2$ MPS; baseline drops below 0.999
within 2 sweeps.

## What falsifies HOR-Qubit as a framework

If tests T1–T5 all fail repeatedly across multiple circuit corpora and
hardware configurations, HOR-Qubit is a labeling system, not a
framework. **That is the intended test.**

If only some tests fail, HOR-Qubit is regime-limited — useful in some
regimes (e.g., structured Clifford circuits) and not others (e.g.,
random deep volume-law). This is honest and reported per-regime.

## What does NOT falsify HOR-Qubit

- "It doesn't beat the exponential wall." — It doesn't claim to.
- "It doesn't simulate 420M entangled qubits." — It refuses them.
- "The Sophia Point isn't real." — We agree; we rejected it.
- "Side channels aren't eliminated." — We never claimed they were.
- "Hardware fidelity is lower than simulator fidelity." — We track this
  via TRL labels; we don't conflate them.

## Arrival audit

Any $\eta \ge 0.999$ (efficiency metric) is flagged as a measurement
fault until independently confirmed (PAZUZU §2.4, E201).

Independent counter pairs:

| Axis | Counter 1 | Counter 2 |
|---|---|---|
| $\eta_{\text{interactive}}$ | HOR timer | PAZUZU wall clock (`perf`) |
| $\eta_{\text{throughput}}$ | HOR gate counter | `perf stat` cycles |
| $\eta_{\text{ram}}$ | `tracemalloc` | `/proc/self/status` VmHWM |
| $\eta_{\text{swap}}$ | PAZUZU SMART reads/writes | HOR block log |
| $\eta_{\text{power}}$ | RAPL | NVML |
| $\eta_{\text{cost}}$ | HOR certificate log | PAZUZU epoch log |

If any pair disagrees by > 2%, CI fails and opens an audit issue.
