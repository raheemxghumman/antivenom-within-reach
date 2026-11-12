"""Self-checks that the quantum model solves exactly the problem the classical solvers score.

    python check_model.py

1. The cost Hamiltonian's energy equals -objective + penalty for all 512 bitstrings.
2. The same Hamiltonian built as a Qiskit SparsePauliOp has the same diagonal.
3. Qiskit's QuadraticProgram (pairwise form) matches the exact objective wherever no village is
   reachable from 3+ clinics, and the gap shows why the exact ZZZ terms are needed.
4. The Aer-simulated QAOA state matches an independent numpy simulation.
5. The XY mixer keeps every amplitude on plans with exactly k clinics.
Also writes docs/model.txt (the pairwise model, printed by Qiskit).
"""
from pathlib import Path

import numpy as np

from avr.instance import make_district
from avr.model import all_bitstrings, build_qp, plan_values
from avr.quantum import (cost_polynomial, exact_probabilities, poly_energies, poly_to_sparse_pauli,
                         qaoa_circuit)

d, k, lam, mu, n = make_district(2026), 3, 1.0, 2.0, 9
bits = all_bitstrings(n)
vals = plan_values(d, bits, lam, mu)
A = float(d.weights(lam).max())

poly = cost_polynomial(d, k, lam, mu, A)
e = poly_energies(poly, n)
err1 = np.abs(e - (-vals + A * (bits.sum(1) - k) ** 2)).max()
print(f"1. Hamiltonian vs brute-force objective, max error: {err1:.1e}")
assert err1 < 1e-8

diag = np.real(poly_to_sparse_pauli(poly, n).to_matrix(sparse=True).diagonal())
err2 = np.abs(diag - e).max()
print(f"2. SparsePauliOp diagonal vs energies, max error:  {err2:.1e}")
assert err2 < 1e-8

qp, truncated = build_qp(d, k, lam, mu)
qpv = np.array([qp.objective.evaluate(b) for b in bits])
valid = bits.sum(1) == k
gap = np.abs(qpv[valid] - vals[valid]).max()
print(f"3. QuadraticProgram (pairwise only) vs exact: {len(truncated)} villages reach 3+ clinics, "
      f"max gap {gap:.2f} -> exact ZZZ terms are needed")
Path("docs").mkdir(exist_ok=True)
Path("docs/model.txt").write_text(qp.prettyprint())

polyn = {key: c / 10 for key, c in cost_polynomial(d, k, lam, mu, A).items()}
qc, params = qaoa_circuit(polyn, n, 1, "x", k)
g, b = 0.4, 0.3
psi = np.full(2 ** n, 2 ** (-n / 2)) * np.exp(-1j * g * poly_energies(polyn, n))
rx = np.array([[np.cos(b), -1j * np.sin(b)], [-1j * np.sin(b), np.cos(b)]])
t = psi.reshape([2] * n)
for q in range(n):
    ax = n - 1 - q
    t = np.moveaxis(np.tensordot(rx, t, axes=([1], [ax])), 0, ax)
err4 = np.abs(np.abs(t.reshape(-1)) ** 2 - exact_probabilities(qc, params)([g, b])).max()
print(f"4. Aer QAOA probabilities vs numpy reference, max error: {err4:.1e}")
assert err4 < 1e-9

qc, params = qaoa_circuit(polyn, n, 2, "xy", k)
mass = exact_probabilities(qc, params)([0.7, 0.2, 0.5, 0.9])[valid].sum()
print(f"5. XY-mixer probability on valid plans: {mass:.12f}")
assert abs(mass - 1) < 1e-9
print("All checks passed.")
