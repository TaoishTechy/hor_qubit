"""hor.core.registers — Classical H/G/R registers for the cq-state.

Three finite classical registers travel with the quantum state. They are
**classical** in the precise sense of v0.1.5: they are stored as ordinary
Python data (lists, dicts, numpy arrays of classical data), never as
quantum amplitudes, and they update via deterministic classical channels
conditioned on gate type and measurement outcome.

This file fixes v0.1 issues A1-1..A1-12 and A2-13..A2-24 by making the
classical/quantum split explicit and well-typed.

References
----------
- HOR-Qubit v0.1.5, §1 (formal state, dimensions, initialization)
- HOR-Qubit v0.1.5 supplement, §1 (Hollow sheaf math), §2 (Generic forcing),
  §3 (Resonant non-Hermitian math)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np


# --------------------------------------------------------------------------
# Hollow register (Layer H)
# --------------------------------------------------------------------------


@dataclass
class PersistenceBar:
    """A single bar in a persistence diagram: born at ``b``, died at ``d``."""

    birth: float
    death: float

    @property
    def lifetime(self) -> float:
        return self.death - self.birth


@dataclass
class PersistenceDiagram:
    """A degree-``k`` persistence diagram with noise floor for filtering."""

    k: int
    bars: list[PersistenceBar] = field(default_factory=list)
    noise_floor: float = 0.0  # bottleneck distance d_B^noise; estimated by bootstrap

    def long_bars(self, factor: float = 2.0) -> list[PersistenceBar]:
        """Return bars with lifetime > 2 * noise_floor (Cohen-Steiner stability)."""
        return [b for b in self.bars if b.lifetime > factor * self.noise_floor]

    def persistence_entropy(self) -> float:
        """E(Dgm) = -sum p_i log p_i, with p_i = (d_i - b_i) / sum (d_j - b_j).

        Standard TDA-derived complexity measure (E152 in the HOR-Qudit
        extension pack). High entropy = many short bars = noisy; low entropy
        = few long bars = structured.
        """
        if not self.bars:
            return 0.0
        lens = np.array([b.lifetime for b in self.bars])
        total = lens.sum()
        if total <= 0:
            return 0.0
        p = lens / total
        p = p[p > 0]
        return float(-np.sum(p * np.log(p)))


@dataclass
class CellularSheaf:
    """A cellular sheaf on the circuit graph (Hansen-Ghrist construction).

    Site: circuit graph ``G = (V, E)``. Stalk at every vertex and edge is
    ``C^d_stalk`` (default ``d_stalk = 3``). Restriction maps are stored as
    a dict from edge id -> (3x3) complex matrix. The coboundary ``delta``
    and sheaf Laplacian ``L_F = delta* delta`` are derived.

    This implements E145 / E146 / E148 from the HOR-Qudit extension pack.
    """

    n_vertices: int
    n_edges: int
    stalk_dim: int = 3
    # edge index -> (src, dst, restriction_matrix)
    edges: dict[int, tuple[int, int, np.ndarray]] = field(default_factory=dict)

    def add_edge(self, eid: int, src: int, dst: int, restriction: np.ndarray | None = None) -> None:
        if restriction is None:
            restriction = np.eye(self.stalk_dim, dtype=complex)
        if restriction.shape != (self.stalk_dim, self.stalk_dim):
            raise ValueError(
                f"restriction must be ({self.stalk_dim},{self.stalk_dim}); got {restriction.shape}"
            )
        self.edges[eid] = (src, dst, restriction.astype(complex))
        self.n_edges = len(self.edges)

    def coboundary(self) -> np.ndarray:
        """Block incidence matrix ``delta: C^0 -> C^1``.

        For each edge ``e = (u, v)`` with restriction ``rho_e``, the row
        corresponding to ``e`` has ``-rho_e`` at column ``u`` and ``+rho_e``
        at column ``v`` (or vice versa; sign convention is consistent).
        """
        rows = self.n_edges * self.stalk_dim
        cols = self.n_vertices * self.stalk_dim
        delta = np.zeros((rows, cols), dtype=complex)
        for eid, (src, dst, rho) in self.edges.items():
            r0 = eid * self.stalk_dim
            c0_s = src * self.stalk_dim
            c0_d = dst * self.stalk_dim
            delta[r0 : r0 + self.stalk_dim, c0_s : c0_s + self.stalk_dim] = -rho
            delta[r0 : r0 + self.stalk_dim, c0_d : c0_d + self.stalk_dim] = rho
        return delta

    def laplacian(self) -> np.ndarray:
        """Sheaf Hodge Laplacian ``L_F = delta* delta`` (0-cochains).

        Returns a ``n_vertices * stalk_dim`` square Hermitian matrix.
        """
        delta = self.coboundary()
        return delta.conj().T @ delta

    def spectral_gap(self) -> float:
        """Second-smallest eigenvalue ``lambda_1(L_F)``.

        This is the *sheaf coherence gap*. If it falls below the
        measurement noise floor, HOR flags the certificate as unmeasurable
        (v0.1.5 §3). Large ``lambda_1`` is *necessary*, not *sufficient*,
        for topological protection (Cheeger inequality, E148).
        """
        L = self.laplacian()
        if L.shape[0] == 0:
            return 0.0
        eigs = np.linalg.eigvalsh(L)
        eigs = np.sort(np.real(eigs))
        # second smallest (algebraic connectivity); first is ~0 (constant mode)
        return float(eigs[1] if len(eigs) > 1 else 0.0)

    def h1_dimension(self) -> int:
        """``dim H^1(X, F) = dim ker(delta^1) - dim im(delta^0)``.

        For our 0/1-cochain complex on the circuit graph, ``delta^1`` is
        the trivial map to ``C^2 = 0``, so ``ker(delta^1) = C^1``. Hence
        ``dim H^1 = dim C^1 - rank(delta^0)``.

        Physical meaning: ``H^1 != 0`` means there are local syndromes that
        cannot be glued into a global correction — a *logical error
        invisible to standard syndrome measurement* (E146). This is the
        real content of HOR-Qudit's H^1 obstruction check.
        """
        delta = self.coboundary()
        rank_d0 = int(np.linalg.matrix_rank(delta))
        dim_c1 = delta.shape[0]
        return dim_c1 - rank_d0


@dataclass
class HollowRecord:
    """Classical Hollow register.

    Stored data: cellular sheaf, sheaf Laplacian eigenvalues, persistence
    diagrams, scar cohomology Hodge norm, status flag.

    In vacuum: all fields are ``None`` / empty / ``status="unavailable"``.
    Computing the sheaf and persistence is **optional** (off by default in
    v0.2 for speed; enable via ``hor_persistence=True``).
    """

    sheaf: CellularSheaf | None = None
    lambda_1: float | None = None
    h_F: float | None = None  # sheaf conductance (Cheeger)
    persistence: list[PersistenceDiagram] = field(default_factory=list)
    scar_norm_hodge: float | None = None
    status: Literal["unavailable", "computed", "failed"] = "unavailable"
    h1_dim: int | None = None  # dim H^1(X, F) — obstruction check (E146)


# --------------------------------------------------------------------------
# Generic register (Layer G)
# --------------------------------------------------------------------------


@dataclass
class ForcingStep:
    """One step in a forcing proof chain ``p_0 <= p_1 <= ... <= p_k``.

    Each step records the poset element ``p`` reached, the invariant
    ``phi`` that was preserved, and the button/switch classification
    (Hamkins-Loewe; v0.1.5 supplement §2). A *button* once forced stays
    forced under all refinements; a *switch* can be forced either way.
    """

    p: str  # human-readable poset element label
    phi: str  # first-order property preserved
    classification: Literal["button", "switch", "ambiguous"] = "ambiguous"
    dense_sets_met: list[str] = field(default_factory=list)


@dataclass
class ForcingCondition:
    """Typed forcing condition (NOT a free-form string).

    v0.1's ``hor_force("gap_open and C4_preserved")`` was ungrammatical;
    v0.1.5 fixes this with a typed struct (issue A12-138).
    """

    gap_open: bool = True
    min_gap_ghz: float = 0.5
    symmetry: str | None = None  # e.g. "C4", "U1", "Z2"
    max_bond: int = 64
    language: Literal["first_order_finite"] = "first_order_finite"
    button_required: bool = True

    def formula(self) -> str:
        """Render as a first-order formula string for the certificate."""
        clauses = []
        if self.gap_open:
            clauses.append(f"gap > {self.min_gap_ghz}")
        if self.symmetry:
            clauses.append(f"symmetry = {self.symmetry}")
        if self.max_bond:
            clauses.append(f"bond <= {self.max_bond}")
        return " AND ".join(clauses) if clauses else "true"


@dataclass
class GenericRecord:
    """Classical Generic register: forcing proof chain.

    The chain ``p_0 <= p_1 <= ... <= p_k`` is the operational content of
    the Generic layer. It is a finite approximation ``G_approx`` to the
    (set-theoretically non-constructible) generic filter ``G`` (v0.1.5 §4).

    ``G_approx`` meets a *finite, preregistered* list of dense sets
    ``D_1, ..., D_k``. It does not claim to meet all dense sets in ``V``.
    """

    forcing_proof: list[ForcingStep] = field(default_factory=list)
    constraints: ForcingCondition | None = None
    dense_sets_checked: list[str] = field(default_factory=list)
    status: Literal["vacuum", "active", "failed"] = "vacuum"


# --------------------------------------------------------------------------
# Resonant register (Layer R)
# ------------------------------------------------------------------


@dataclass
class ResonantRecord:
    """Classical Resonant register.

    Stores the echo-state reservoir state ``x(t)`` and a thermodynamic /
    energy ledger. **Never** acts on the qubit; only processes measurement
    outcomes and calibration streams (v0.1.5 §5).

    The reservoir update is::

        x(t+1) = (1-alpha) x(t) + alpha tanh(W_in u(t) + W x(t))

    which is classical echo-state dynamics. Stability requires
    ``rho(W) < 1`` and bounded input scaling. The non-Hermitian ``D_Gamma``
    from v0.1 is **only** defined for the phononic testbed (PT-symmetric
    biorthogonal QM, Brody formalism) — never for the qubit.

    Energy ledger (E36 / v0.1.5 supplement §7) tracks:
    - ``landauer_erasure``: ``k_B T ln 2 * Delta_bits`` per classical erasure
    - ``memory_write``: DRAM/NVMe write energy per block
    - ``compute``: CPU/GPU flop energy
    - ``bekenstein_check``: information content vs. Bekenstein bound
    """

    x: np.ndarray = field(default_factory=lambda: np.zeros(128))
    alpha: float = 0.3
    W: np.ndarray | None = None  # reservoir matrix; must have spectral radius < 1
    W_in: np.ndarray | None = None
    gamma: float = 0.0  # damping (testbed only)
    thermal_budget_joules: float = 0.0
    energy_ledger: dict[str, float] = field(default_factory=dict)
    status: Literal["vacuum", "active"] = "vacuum"

    def step(self, u: np.ndarray) -> np.ndarray:
        """Echo-state reservoir update (E5 from the v0.1.5 supplement).

        Stability: requires ``rho(W) < 1`` (checked at compile time).
        """
        if self.W is None or self.W_in is None:
            # Identity reservoir: just leaky integrator
            self.x = (1 - self.alpha) * self.x + self.alpha * np.tanh(u)
        else:
            self.x = (
                (1 - self.alpha) * self.x
                + self.alpha * np.tanh(self.W_in @ u + self.W @ self.x)
            )
        return self.x

    def check_stability(self) -> bool:
        """Verify ``rho(W) < 1`` (echo state property)."""
        if self.W is None:
            return True
        rho = max(abs(np.linalg.eigvals(self.W)))
        return rho < 1.0


# --------------------------------------------------------------------------
# Resource budgets (v0.1.5 §9)
# --------------------------------------------------------------------------


@dataclass
class ResourceBudgets:
    """Per-block resource-theoretic budgets (v0.1.5 §9, B6 enhancements 41-48).

    Each budget is a separate field — no single scalar summarizes HOR.
    Replaces v0.1's ill-defined ``S_usable`` with standard resource
    theories (Veitch et al. magic, Baumgratz-Cramer-Plenio coherence, etc.).
    """

    entanglement_entropy: float = 0.0  # von Neumann, bipartition A:B
    entanglement_of_formation: float = 0.0  # Wootters (n <= 6)
    distillable_entanglement: float = 0.0  # upper bound for mixed
    squashed_entanglement: float = 0.0
    magic_robustness: float = 0.0  # Bravyi-Smith-Smolin
    stabilizer_extent: float = 1.0  # xi(|T>^t) = 1.172^t
    t_count: int = 0
    coherence_l1: float = 0.0  # Baumgratz-Cramer-Plenio l1-norm
    coherence_rel_entropy: float = 0.0
    athermality_free_energy: float = 0.0
    asymmetry_measure: float = 0.0
    non_gaussianity: float = 0.0
    contextuality: float = 0.0
    discord: float = 0.0


# --------------------------------------------------------------------------
# Shot budget (v0.1.5 §7, v0.2 §8)
# --------------------------------------------------------------------------


@dataclass
class ShotBudget:
    """Per-observable shot allocation from the shot planner.

    Method is one of: ``"hoeffding"``, ``"bernstein"``, ``"median_of_means"``,
    ``"neyman"``.
    """

    per_observable: dict[str, int] = field(default_factory=dict)
    total: int = 0
    grouping: list[list[str]] = field(default_factory=list)
    expected_epsilon: float = 0.0
    method: str = "hoeffding"
    target_delta: float = 0.001
