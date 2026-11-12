"""QAOA for the antivenom stocking problem, built from Qiskit circuits and primitives.

Exact cost Hamiltonian (no approximation, no extra qubits)
----------------------------------------------------------
With x_i = (1 - Z_i) / 2, a village reachable from clinic set S is covered with value
    1 - prod_{i in S} (1 - x_i)  =  1 - 2^-|S| * sum_{T subset S} Z_T
so villages reachable from 1, 2 or 3+ clinics give Z, ZZ or ZZZ terms. Each term becomes
one multi-qubit Z rotation in the circuit. (A pure QUBO would have to drop the 3-body
terms; we keep them, so QAOA optimises exactly the objective the brute force scores.)

Three variants:
  * "x"      : standard QAOA, budget sum(x) == k as a penalty A * (sum(x) - k)^2.
  * "xy"     : constraint-preserving QAOA (Hadfield et al., 2019): start in an equal
               superposition of all plans with exactly k clinics (a Dicke state) and mix with
               XX+YY gates on all pairs, which never change how many clinics are on.
  * "xyring" : hardware-friendly version of "xy": start from one valid plan and mix only
               neighbouring qubits on a ring. Much shallower; still every ideal shot is valid.

Training uses exact probabilities from the Qiskit Aer statevector simulator (deterministic
for a fixed seed). Final results are also sampled with Aer's SamplerV2, as a device would return.
"""
from __future__ import annotations

import time
from itertools import combinations

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit import ParameterVector
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2 as AerSamplerV2
from qiskit.circuit.library import StatePreparation, XXPlusYYGate
from qiskit.quantum_info import SparsePauliOp
from scipy.optimize import minimize

from .instance import District
from .model import all_bitstrings, decision_villages


def _add(poly, key, c):
    key = frozenset(key)
    poly[key] = poly.get(key, 0.0) + c


def cost_polynomial(d: District, k: int, lam: float, mu: float, penalty: float = 0.0):
    """Energy E(z) = sum_T c_T * prod_{i in T} Z_i to MINIMISE (= -objective + penalty)."""
    poly: dict[frozenset, float] = {}
    w = d.weights(lam)
    for v in np.where(decision_villages(d))[0]:
        s = list(np.where(d.reach[v])[0])
        _add(poly, (), -w[v])                       # -w * 1
        scale = w[v] / 2 ** len(s)
        for r in range(len(s) + 1):                 # +w * 2^-|S| * sum_T Z_T
            for t in combinations(s, r):
                _add(poly, t, scale)
    for i, c in enumerate(d.cold_cost):             # +mu * cost_i * x_i
        if c:
            _add(poly, (), mu * c / 2)
            _add(poly, (i,), -mu * c / 2)
    if penalty:                                     # A * (sum x - k)^2
        n = d.n_clinics
        cc = n / 2 - k
        _add(poly, (), penalty * (cc ** 2 + n / 4))
        for i in range(n):
            _add(poly, (i,), -penalty * cc)
        for i, j in combinations(range(n), 2):
            _add(poly, (i, j), penalty / 2)
    return {key: c for key, c in poly.items() if abs(c) > 1e-12}


def poly_energies(poly, n):
    z = 1 - 2 * all_bitstrings(n).astype(float)
    e = np.zeros(2 ** n)
    for key, c in poly.items():
        e += c * (np.prod(z[:, sorted(key)], axis=1) if key else 1.0)
    return e


def poly_to_sparse_pauli(poly, n) -> SparsePauliOp:
    """The same Hamiltonian as a Qiskit operator (used for checks and for Estimator runs)."""
    terms = [("Z" * len(key), sorted(key), c) for key, c in poly.items() if key]
    const = poly.get(frozenset(), 0.0)
    return SparsePauliOp.from_sparse_list(terms + [("", [], const)], num_qubits=n).simplify()


def dicke_state(n: int, k: int) -> np.ndarray:
    weight = all_bitstrings(n).sum(axis=1)
    amp = (weight == k).astype(float)
    return amp / np.linalg.norm(amp)


def _z_rotation(qc, qubits, angle):
    """exp(-i * angle/2 * Z...Z) on the given qubits via a CNOT ladder."""
    qubits = sorted(qubits)
    if len(qubits) == 1:
        qc.rz(angle, qubits[0])
    elif len(qubits) == 2:
        qc.rzz(angle, qubits[0], qubits[1])
    else:
        tgt = qubits[-1]
        for q in qubits[:-1]:
            qc.cx(q, tgt)
        qc.rz(angle, tgt)
        for q in reversed(qubits[:-1]):
            qc.cx(q, tgt)


def qaoa_circuit(poly, n, reps, mixer="x", k=None):
    gam = ParameterVector("gamma", reps)
    bet = ParameterVector("beta", reps)
    qc = QuantumCircuit(n, name=f"QAOA-{mixer}-p{reps}")
    if mixer == "x":
        qc.h(range(n))
    elif mixer == "xy":
        qc.append(StatePreparation(dicke_state(n, k)), range(n))
    else:                                       # "xyring": hardware-friendly, one valid start plan
        for q in range(0, n, max(1, n // k))[:k]:
            qc.x(q)
    terms = sorted(((sorted(key), c) for key, c in poly.items() if key), key=lambda t: (len(t[0]), t[0]))
    if mixer == "xyring":                       # nearest neighbours on a ring, two layers (even, odd)
        pairs = [(i, i + 1) for i in range(0, n - 1, 2)] + [(i, (i + 1) % n) for i in range(1, n, 2)]
    else:
        pairs = list(combinations(range(n), 2))
    for layer in range(reps):
        for qs, c in terms:                     # cost layer exp(-i gamma H_C)
            _z_rotation(qc, qs, 2 * gam[layer] * c)
        if mixer == "x":                        # mixer layer
            for i in range(n):
                qc.rx(2 * bet[layer], i)
        else:
            for i, j in pairs:
                qc.append(XXPlusYYGate(2 * bet[layer]), [i, j])
    return qc, list(gam) + list(bet)


def exact_probabilities(qc: QuantumCircuit, params):
    """Return theta -> exact output probabilities, simulated with Qiskit Aer (statevector).
    The circuit is transpiled once; each call only binds new angles."""
    sim = AerSimulator(method="statevector")
    tqc = qc.copy()
    tqc.save_probabilities()
    tqc = transpile(tqc, sim, optimization_level=0)

    def probs(theta):
        binds = {p: [float(v)] for p, v in zip(params, theta)}
        return np.asarray(sim.run(tqc, parameter_binds=[binds]).result().data(0)["probabilities"])

    return probs


def _objective(p, en, order, alpha):
    if alpha >= 1.0:
        return float(p @ en)
    ps, es = p[order], en[order]               # CVaR: mean of the best alpha share
    prev = np.concatenate([[0.0], np.cumsum(ps)[:-1]])
    take = np.clip(alpha - prev, 0.0, ps)
    return float((take * es).sum() / alpha)


def run_qaoa(d: District, k: int, lam: float = 1.0, mu: float = 0.0, reps: int = 2,
             mixer: str = "x", penalty: float = 0.0, alpha: float = 1.0, restarts: int = 4,
             maxiter: int = 300, seed: int = 7, callback=None) -> dict:
    """Train QAOA and return its output distribution over all 2^n plans.
    callback(restart, n_evals, value), if given, is called after every cost evaluation."""
    t0 = time.time()
    n = d.n_clinics
    if mixer == "x" and penalty <= 0:
        raise ValueError("The X mixer needs a budget penalty > 0")
    poly = cost_polynomial(d, k, lam, mu, penalty if mixer == "x" else 0.0)
    scale = max(abs(c) for key, c in poly.items() if key)
    polyn = {key: c / scale for key, c in poly.items()}
    en = poly_energies(polyn, n)
    order = np.argsort(en)
    qc, params = qaoa_circuit(polyn, n, reps, mixer, k)
    probs = exact_probabilities(qc, params)

    history = []
    current = {"restart": 0}

    def cost(theta):
        val = _objective(probs(theta), en, order, alpha)
        history.append(val)
        if callback is not None:
            callback(current["restart"], len(history), val)
        return val

    rng = np.random.default_rng(seed)
    best = None
    for r in range(restarts):
        current["restart"] = r
        if r == 0:   # linear-ramp start, a common good initial point for QAOA
            x0 = np.concatenate([np.linspace(0.1, 0.9, reps) * np.pi / 2,
                                 np.linspace(0.9, 0.1, reps) * np.pi / 4])
        else:
            x0 = np.concatenate([rng.uniform(0, np.pi, reps), rng.uniform(0, np.pi / 2, reps)])
        res = minimize(cost, x0, method="COBYLA", options={"maxiter": maxiter, "rhobeg": 0.3})
        if best is None or res.fun < best.fun:
            best = res
    return {"probs": probs(best.x), "theta": best.x, "circuit": qc, "poly": poly,
            "history": history, "train_seconds": time.time() - t0, "n_qubits": n,
            "reps": reps, "mixer": mixer, "penalty": penalty, "alpha": alpha,
            "n_cost_evals": len(history), "n_terms": sum(1 for key in poly if key),
            "max_term_order": max(len(key) for key in poly)}


def sample(result: dict, shots: int = 4096, seed: int = 11) -> np.ndarray:
    """Sample the trained circuit with the Aer SamplerV2 primitive; counts per plan index."""
    qc = result["circuit"].assign_parameters(result["theta"])
    qc.measure_all()
    qc = transpile(qc, AerSimulator(), optimization_level=0)
    sampler = AerSamplerV2(seed=seed)
    counts = sampler.run([qc], shots=shots).result()[0].data.meas.get_counts()
    out = np.zeros(2 ** result["n_qubits"])
    for bits, c in counts.items():
        out[int(bits, 2)] = c
    return out


def summarize(dist: np.ndarray, plan_vals_all: np.ndarray, k: int, opt_value: float,
              rand_mean: float, n: int) -> dict:
    """Metrics for an output distribution (probabilities or counts) over all 2^n plans."""
    p = dist / dist.sum()
    valid = all_bitstrings(n).sum(axis=1) == k
    p_valid = float(p[valid].sum())
    is_opt = valid & np.isclose(plan_vals_all, opt_value)
    p_opt = float(p[is_opt].sum())
    exp_valid = float((p[valid] * plan_vals_all[valid]).sum() / p_valid) if p_valid > 0 else 0.0
    top = int(np.argmax(np.where(valid, p, -1)))
    return {
        "valid_rate": p_valid,
        "p_optimal": p_opt,
        "random_p_optimal": float(is_opt.sum() / valid.sum()),
        "boost_vs_random": p_opt / float(is_opt.sum() / valid.sum()),
        "approx_ratio_valid": exp_valid / opt_value,
        "gain_over_random": (exp_valid - rand_mean) / (opt_value - rand_mean),
        "most_likely_valid_plan": top,
        "most_likely_is_optimal": bool(is_opt[top]),
        "p_optimal_in_100_shots": float(1 - (1 - p_opt) ** 100),
    }
