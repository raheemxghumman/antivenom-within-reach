# Build plan — Qiskit Fall Fest 2026 (Healthcare)

**Problem.** Snakebite envenoming kills an estimated 81,000–138,000 people a year (WHO), mostly
rural farmers, herders and children in South Asia, sub-Saharan Africa and Latin America.
Antivenom is scarce and must reach a patient within hours. A district can afford to stock
only a few clinics. **Which clinics should stock it?**

**Decision.** `x_i = 1` if candidate clinic *i* stocks antivenom (one qubit per clinic, 9 qubits).
**Objective.** Maximise yearly envenomings that reach antivenom within 6 h, where a child's bite
counts `(1 + λ)` times, minus `μ` per new solar fridge needed.
**Constraint.** Exactly `k` clinics are stocked (stock / staffing budget).

## Phases

1. Scaffold: repo, plan, requirements.
2. Model: synthetic district generator, exact objective, classical baselines
   (brute force over all plans, greedy max-coverage, random valid plan).
3. Quantum: exact cost Hamiltonian (Z, ZZ and ZZZ terms, no extra qubits),
   standard QAOA (X mixer + budget penalty) and constraint-preserving QAOA (XY mixer from a
   Dicke state), CVaR objective.
4. Experiments: depth sweep, penalty sweep, CVaR sweep, supply sweep, child-equity trade-off,
   greedy-failure statistics on 100 districts, a case study where greedy is not optimal.
5. Demo: web app (map, live QAOA, real-QPU panel).
6. Docs: README, report (.docx) with architecture diagram, 3-minute video script.
7. Optional: noisy simulation with an IBM device noise model and one real IBM QPU run.

## Honesty rules

- The district is **synthetic**; parameter ranges are documented in `docs/data_sources.md`.
- No speedup claim: at 9 qubits brute force is instant. The point is a faithful quantum
  formulation and a measured comparison.
- Every number in the report comes from `run_experiments.py` output in `results/`.

## Added during the build

8. Real geography: Sanghar, Sindh (OpenStreetMap BHUs, hospital, settlements).
9. Hardware-friendly ring-XY mixer and a real IBM QPU run (ibm_marrakesh).
