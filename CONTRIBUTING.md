# Contributing

Thanks for your interest in `hor-qubit`! This document describes how to
contribute effectively while preserving the framework's honesty
discipline.

## 1. Read the spec first

Before contributing, read:

- `README.md` — overview
- `docs/architecture.md` — internal structure
- `docs/certificate.md` — the Sigma-type certificate spec
- `docs/backends.md` — backend catalog and router
- `docs/falsifiability.md` — pre-registered tests

The framework's value comes from its **honesty discipline**:
- No fictional physics (Sophia Point, ERD field, love field)
- No claims without falsifiability tests
- No efficiency metric ≥ 0.999 without independent counter
- No silent truncation, silent regime switching, silent T-cost

## 2. Development setup

```bash
git clone https://github.com/TaoishTechy/hor-qubit.git
cd hor-qubit
pip install -e ".[dev]"
pytest
```

Optional extras:

```bash
pip install -e ".[crypto]"   # blake3, cryptography for real Ed25519
pip install -e ".[viz]"      # matplotlib for plotting
```

## 3. Code style

- Python 3.10+
- Type hints required for public API
- `ruff` for linting, `mypy` for type checking
- Line length: 100 chars
- All docstrings with LaTeX escape sequences must use raw strings (`r"""..."""`)

## 4. Test discipline

Every new feature must ship with:

1. **Unit tests** in `tests/`
2. **A falsifiability test** if the feature makes a claim (e.g., "this
   backend is faster than X" — what would refute it?)
3. **A classification tag** if the feature introduces a parameter
   (Derived / Topologically Forced / Design Choice / Empirical Fit)
4. **A TRL label** (Simulation-Emulated / Simulator-Measured /
   Artifact-Verified / Hardware-Target / Hardware-Measured / Formal Proof)

Run tests before pushing:

```bash
pytest -v
ruff check .
mypy hor/
```

## 5. Backwards compatibility

The **compatibility theorem** is load-bearing:

> For any $n$-qubit circuit $C$ built from the v0.1.5 gate set,
> $P_{HOR}(x | C, \rho_{HOR}^{vac}) = P_{standard}(x | C, \rho_2)$
> up to $10^{-14}$ per gate.

Any change that breaks this is a release-blocking bug. The CI runs
`tests/test_compatibility.py` on every PR.

## 6. Certificate reproducibility

The certificate hash must be reproducible: same code + same
calibration id + same seed = same hash. If you change the certificate
schema, bump `schema_version` and document the migration.

## 7. What NOT to contribute

Please do not propose:

- **Fictional physics**: Sophia Point as attractor, ERD field as
  physical scalar, love field, miracle operator, consciousness
  collapse, vacuum harvesting. These are explicitly rejected by the
  reality audit (HOR-Qudit Extension Pack §0).
- **420M entangled qubit claims**. The Bekenstein bound and Hilbert
  dimension make this physically impossible. 420M *product* qubits is
  the honest ceiling (R5, storage certificate).
- **"Zero logical error"** for volume-law states. There's no such
  thing.
- **"Side channels physically impossible"**. Process isolation reduces
  risk; it doesn't eliminate attacks.
- **Efficiency ≥ 99.9% without an arrival audit**. Any $\eta \ge 0.999$
  is flagged as a measurement fault until independently confirmed.

## 8. What TO contribute

- New **backends** (PEPS, MERA, TTN, Pauli propagation, stabilizer
  rank) — each with cost model, falsifiability test, TRL label.
- New **resource-theory budgets** (asymmetry, non-Gaussianity,
  contextuality, discord) — each with proper monotones.
- New **falsifiability tests** — every claim needs a test that would
  refute it.
- New **calibration importers** (Qiskit, Cirq, Braket, custom CSV) —
  each with schema validation and staleness check.
- New **MPS / PEPS algorithms** (DMRG, VUMPS, CTMRG, TRG) — each with
  truncation accounting.
- New **HOR-Qudit extension backends** — but only the *real math*
  parts. Cellular sheaves, persistent homology, HOTI invariants,
  transfer operators, QES island formulas are real and welcome.
- **Documentation** improvements — math derivations, worked examples,
  honest limits sections.

## 9. Pull request checklist

- [ ] Tests pass (`pytest -v`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type checking passes (`mypy hor/`)
- [ ] Backwards compatibility test passes
- [ ] New features have unit tests
- [ ] New claims have falsifiability tests
- [ ] New parameters have classification tags
- [ ] New metrics have TRL labels
- [ ] No fictional physics introduced
- [ ] No $\eta \ge 0.999$ claim without arrival audit
- [ ] Docstrings updated; raw strings used where needed

## 10. Issue reporting

Use GitHub Issues. For bugs, please include:

- Python version, NumPy version, OS
- Minimal reproducer
- Expected vs actual behavior
- Certificate hash (if applicable)

For feature requests, please include:

- The math (equations, references)
- The falsifiability test (what would refute it?)
- The classification tag for any new parameters
- The TRL label

## 11. Citation

If you use `hor-qubit` in academic work:

```bibtex
@software{hor_qubit,
  title  = {HOR-Qubit: Hollow Ontological Resonant Qubit Framework},
  author = {TaoishTechy},
  year   = {2026},
  url    = {https://github.com/TaoishTechy/hor-qubit}
}
```

---

$$\boxed{\text{We hollow. We force. We type-check. We calibrate. We remain falsifiable.}}$$
