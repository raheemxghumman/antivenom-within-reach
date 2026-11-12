"""Turn the district into a QuadraticProgram, and score any stocking plan exactly.

Decision: x_i = 1 if candidate clinic i stocks antivenom (one qubit per clinic).
A village v is covered if any stocked clinic is inside its time window.
For a village reachable from clinics a and b:  covered = x_a + x_b - x_a * x_b  (exact).
That pairwise overlap term is what makes the problem quadratic and greedy imperfect.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np
from qiskit_optimization import QuadraticProgram

from .instance import District


def decision_villages(d: District) -> np.ndarray:
    """Villages whose coverage depends on our choice (not already covered by the hospital)."""
    return ~d.hospital_covers & d.reach.any(axis=1)


def coverage_terms(d: District, lam: float, mu: float):
    """Linear and pairwise coefficients of the coverage objective (to maximise)."""
    w = d.weights(lam)
    lin = np.zeros(d.n_clinics)
    quad: dict[tuple[int, int], float] = {}
    truncated = []
    for v in np.where(decision_villages(d))[0]:
        s = np.where(d.reach[v])[0]
        for i in s:
            lin[i] += w[v]
        for i, j in combinations(s, 2):
            quad[(i, j)] = quad.get((i, j), 0.0) - w[v]
        if len(s) >= 3:
            truncated.append(int(v))   # inclusion-exclusion cut at pairs: not exact here
    lin -= mu * d.cold_cost
    return lin, quad, truncated


def build_qp(d: District, k: int, lam: float = 1.0, mu: float = 0.0,
             with_budget: bool = True) -> tuple[QuadraticProgram, list[int]]:
    lin, quad, truncated = coverage_terms(d, lam, mu)
    names = d.clinic_names
    qp = QuadraticProgram("antivenom_within_reach")
    for nm in names:
        qp.binary_var(nm)
    qp.maximize(linear={names[i]: float(lin[i]) for i in range(d.n_clinics)},
                quadratic={(names[i], names[j]): float(c) for (i, j), c in quad.items()})
    if with_budget:
        qp.linear_constraint({nm: 1 for nm in names}, "==", k, "budget")
    return qp, truncated


def all_bitstrings(n: int) -> np.ndarray:
    """Row b is the plan whose qubit j is (b >> j) & 1 (Qiskit's little-endian order)."""
    return ((np.arange(2 ** n)[:, None] >> np.arange(n)) & 1).astype(np.int8)


def plan_values(d: District, plans: np.ndarray, lam: float = 1.0, mu: float = 0.0) -> np.ndarray:
    """Exact objective of each plan (rows of 0/1), using true 'any clinic covers' logic."""
    plans = np.atleast_2d(plans).astype(int)
    covered = (plans @ d.reach.T.astype(int)) > 0
    gain = (covered & ~d.hospital_covers) @ d.weights(lam)
    return gain - mu * (plans @ d.cold_cost)


def plan_report(d: District, plan) -> dict:
    """Human numbers for one plan: bites and child bites reaching antivenom in time."""
    x = np.asarray(plan, dtype=bool)
    covered = d.hospital_covers | d.reach[:, x].any(axis=1)
    e, ce = d.envenomings, d.child_envenomings
    return {
        "stocked": [d.clinic_names[i] for i in np.where(x)[0]],
        "villages_covered": int(covered.sum()),
        "villages_total": int(d.n_villages),
        "bites_covered_per_year": float(e[covered].sum()),
        "bites_total_per_year": float(e.sum()),
        "share_bites_covered": float(e[covered].sum() / e.sum()),
        "child_bites_covered_per_year": float(ce[covered].sum()),
        "share_child_bites_covered": float(ce[covered].sum() / ce.sum()),
        "new_fridges_needed": int(d.cold_cost[x].sum()),
    }
