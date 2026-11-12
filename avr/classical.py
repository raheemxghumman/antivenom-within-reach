"""Classical baselines: exact brute force, greedy max-coverage and random valid plans."""
from __future__ import annotations

from itertools import combinations

import numpy as np

from .instance import District
from .model import plan_values


def valid_plans(n: int, k: int) -> np.ndarray:
    plans = np.zeros((0, n), dtype=np.int8)
    rows = []
    for combo in combinations(range(n), k):
        row = np.zeros(n, dtype=np.int8)
        row[list(combo)] = 1
        rows.append(row)
    return np.array(rows) if rows else plans


def brute_force(d: District, k: int, lam: float, mu: float) -> dict:
    plans = valid_plans(d.n_clinics, k)
    vals = plan_values(d, plans, lam, mu)
    best = int(np.argmax(vals))
    return {"plan": plans[best], "value": float(vals[best]), "all_values": vals,
            "n_plans": len(plans), "n_optimal": int(np.isclose(vals, vals[best]).sum())}


def greedy(d: District, k: int, lam: float, mu: float) -> dict:
    """Classic greedy for max coverage: add the clinic with the biggest marginal gain."""
    x = np.zeros(d.n_clinics, dtype=np.int8)
    for _ in range(k):
        best_i, best_v = None, -np.inf
        for i in np.where(x == 0)[0]:
            trial = x.copy()
            trial[i] = 1
            v = plan_values(d, trial, lam, mu)[0]
            if v > best_v + 1e-12:
                best_i, best_v = i, v
        x[best_i] = 1
    return {"plan": x, "value": float(plan_values(d, x, lam, mu)[0])}


def random_baseline(d: District, k: int, lam: float, mu: float) -> dict:
    """Expected value of a plan picked uniformly at random (computed exactly)."""
    vals = plan_values(d, valid_plans(d.n_clinics, k), lam, mu)
    return {"mean": float(vals.mean()), "worst": float(vals.min()), "best": float(vals.max())}
