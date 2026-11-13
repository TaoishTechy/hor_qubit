# Certificate Specification

This document specifies the HOR-Qubit certificate format (`cert-v0.3`).

## Sigma-type, not iff

v0.1 wrote the certification as an iff:

$$
V[G] \models \phi \iff \exists p \in G, p \Vdash \phi \land F_{cert}(G) \ge 0.999 \land \text{BLAKE3}(p \Vdash \phi) \text{ signed}
$$

This is a **type error**: it mixes set-theoretic truth ($V[G] \models \phi$),
a numerical threshold ($F_{cert} \ge 0.999$), and a cryptographic hash
(BLAKE3). v0.1.5 fixes it as a Sigma-type:

```typescript
type Certificate = Σ (forcing_proof: ForcingProof)
                      Σ (f_cert: ℝ, f_ok: f_cert ≥ 0.999)
                      Σ (signature: Signature(manifest))
                      Σ (sig_ok: Verify signature)
                      Manifest
```

Each component is independently verified.

## Fields

| Field | Type | Description |
|---|---|---|
| `forcing_proof` | `ForcingProof` | Chain $p_0 \le p_1 \le \ldots \le p_k$ with $\phi$ preserved |
| `f_cert` | `float` | $F_{state} \cdot F_{process} \cdot (1 - \varepsilon_{trunc}) \cdot (1 - \varepsilon_{shot})$ |
| `f_state` | `float` | Fidelity to ideal statevector, or $1 - \varepsilon_{trunc}$ proxy |
| `f_process` | `float` | 1.0 (v0.2 noiseless) or calibration-based (v0.3) |
| `eps_trunc` | `float` | Cumulative MPS truncation error |
| `eps_shot` | `float` | Shot noise bound from Hoeffding/Bernstein |
| `backend` | `string` | Backend name (R1, R3, R4, R5, R6) |
| `truncation_error` | `float` | Same as `eps_trunc` (kept for backwards compat) |
| `shot_budget` | `ShotBudget` | Per-observable shot allocation |
| `resource_budgets` | `ResourceBudgets` | Entanglement, magic, coherence, etc. |
| `calibration_id` | `string` | `"calib: none"` in v0.2; real id in v0.3 |
| `manifest_hash` | `string` | BLAKE3 of canonical JSON serialization |
| `signature` | `string` | Ed25519 signature over `manifest_hash` |
| `signer` | `string` | Public key id |
| `timestamp` | `string` | ISO 8601 UTC |
| `status` | `enum` | `"certified"`, `"uncertified"`, `"refused"` |
| `reason` | `string \| null` | Failure reason, if any |
| `leakage_max` | `float` | Maximum per-qubit leakage |
| `leakage_per_qubit` | `dict[int, float]` | Per-qubit leakage accumulators |
| `readout_negativity` | `float` | Negativity mass from readout mitigation |
| `readout_mitigation_applied` | `bool` | Whether mitigation was applied |
| `classification` | `dict[str, (value, category)]` | E209 classification matrix |
| `trl` | `enum` | TRL label (Simulation-Emulated, Simulator-Measured, etc.) |
| `energy_ledger` | `dict[str, float]` | Landauer, memory-write, compute |
| `bekenstein_check` | `dict[str, float]` | Information content vs. Bekenstein bound |

## $F_{cert}$ formula

$$
F_{cert} = F_{state} \cdot F_{process} \cdot (1 - \varepsilon_{trunc}) \cdot (1 - \varepsilon_{shot})
$$

| Factor | v0.2 source | v0.3 source |
|---|---|---|
| $F_{state}$ | Fidelity to ideal statevector ($n \le 24$); else $1 - \varepsilon_{trunc}$ proxy | Same |
| $F_{process}$ | 1.0 (noiseless) | $\prod_{gates} (1 - \text{error}_g)$ from calibration |
| $\varepsilon_{trunc}$ | MPS discarded weight | Same |
| $\varepsilon_{shot}$ | Hoeffding/Bernstein bound | Same |

v0.3 adds the leakage penalty:

$$
F_{cert}^{v0.3} = F_{cert}^{v0.2} \cdot (1 - L_{max}) \cdot F_{process}^{cal}
$$

## Threshold

Default: $F_{cert} \ge 0.999$ for `certified`; else `uncertified`.

This is a **per-block ledger threshold**, configurable, not a universal
efficiency claim. For target failure $\delta = 0.001$ and per-block
error budget, HOR requires $F_{cert} \ge 1 - \delta$.

## Cryptographic integrity

- **BLAKE3** (E191): ~GB/s tree hashing, 128-bit collision security
- **Ed25519** (E194): lattice-based signatures, NIST FIPS 204
- **Merkle tree** (E192): $O(\log N)$ proof per chunk
- **Hash-chained ledger** (E193): tamper-evident append-only run log

A signed certificate from a buggy simulator is still wrong. HOR
requires **reproducibility**: same code + same calibration id must
reproduce the same hash.

## Bures-angle composition (E205)

For per-step fidelities $F_i$:

$$
\theta_i = \arccos(\sqrt{F_i}), \quad \theta_{total} = \sum_i \theta_i, \quad F_{cert} = \cos^2(\min(\theta_{total}, \pi/2))
$$

This is a rigorous lower bound on the total fidelity from per-step
losses (Fubini-Study metric).

## Fuchs-van de Graaf (E206)

For trace distance $T$ and fidelity $F$:

$$
1 - \sqrt{F} \le T(\rho, \sigma) \le \sqrt{1 - F}
$$

For any observable $O$ with $\|O\|_\infty = 1$:

$$
|\langle O \rangle_\rho - \langle O \rangle_\sigma| \le 2 T(\rho, \sigma) \le 2 \sqrt{1 - F}
$$

This gives every reported observable an error bar $\pm 2\sqrt{1 - F_{cert}}$.

## Classification matrix (E209)

Every parameter in the certificate is classified:

| Category | Definition | Example |
|---|---|---|
| **Derived** | Follows necessarily from established math/physics | $q_{xy} \in \mathbb{Z}_2$ for $C_4$-symmetric HOTI |
| **Topologically Forced** | Follows from a topological invariant's quantization | $q_{xy} = 1/2$ in topological phase |
| **Design Choice** | Chosen for engineering convenience; could be otherwise | $Q_{corner} = \phi^{-2}$ from specific tiling |
| **Empirical Fit** | Matches simulation data; no derivation | $p_L = 8.2 \times 10^{-13}$ from Monte Carlo |

Downstream consumers may require "Derived" only.

## TRL labels (E203)

Every performance metric is labeled with its verification level:

| Label | Meaning | TRL |
|---|---|---|
| Simulation-Emulated | Classical simulation of quantum behavior | 1–3 |
| Simulator-Measured | Measurement on classical simulator | 3–4 |
| Artifact-Verified | Classical pre-processing | 4 |
| Hardware-Target | Projected hardware performance | 4–5 |
| Hardware-Measured | Actual measurement on physical device | 5+ |
| Formal Proof | Lean 4 / Cubical Agda verified | 4–5 |

## Example JSON

```json
{
  "forcing_proof": {
    "target_phi": "gap > 0.5 AND symmetry = C4 AND bond <= 64",
    "poset_size": 2,
    "n_dense_met": 2,
    "is_button_chain": true,
    "length": 2,
    "steps": [
      {"p": "force_0", "phi": "gap > 0.5 ...", "classification": "button",
       "dense_sets_met": ["D_gap_>_0.5_..."]},
      {"p": "force_1", "phi": "gap > 0.5 ...", "classification": "button",
       "dense_sets_met": ["D_symmetry_=_C4"]}
    ]
  },
  "f_cert": 0.999,
  "f_state": 1.0,
  "f_process": 1.0,
  "eps_trunc": 0.0,
  "eps_shot": 0.001,
  "backend": "R4",
  "truncation_error": 0.0,
  "shot_budget": {"total": 8192, "method": "bernstein", "expected_epsilon": 0.001},
  "resource_budgets": {"t_count": 0, "stabilizer_extent": 1.0},
  "calibration_id": "calib: none",
  "manifest_hash": "310ee6a36ab121969580bad908e9abcf...",
  "signature": "...",
  "signer": "",
  "timestamp": "2026-11-14T...",
  "status": "certified",
  "reason": null,
  "leakage_max": 0.0,
  "leakage_per_qubit": {},
  "readout_negativity": 0.0,
  "readout_mitigation_applied": false,
  "classification": {"clifford_only": {"value": 1.0, "category": "Derived"}},
  "trl": "Simulator-Measured",
  "energy_ledger": {},
  "bekenstein_check": {}
}
```
