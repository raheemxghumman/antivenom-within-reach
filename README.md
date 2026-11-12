# Antivenom Within Reach

**Which rural clinics should stock snakebite antivenom?** A quantum optimisation (QAOA, Qiskit)
that chooses the clinics so that the most snakebites — children's weighted higher — reach
antivenom within 6 hours, when a district can only afford to stock a few.

Qiskit Fall Fest 2026 · Healthcare · SDG 3.3 (neglected tropical diseases), SDG 3.8, SDG 10

![Greedy vs optimal plan on the hard-case district](results/hard_greedy_vs_optimal.png)

## The problem

Snakebite envenoming kills an estimated **81,000–138,000 people a year** and disables many more
(WHO). Most victims are rural farmers, herders and children; children suffer more severe effects
because of their smaller body mass. Antivenom works only if it reaches the patient in time, but it
is expensive, scarce and (in liquid form) needs a 2–8 °C cold chain. A district health officer
can stock only a few clinics. Picking the wrong ones leaves whole villages more than 6 hours away.

## Formulation

| | |
|---|---|
| **Decision** | `x_i ∈ {0,1}`: candidate clinic *i* stocks antivenom (9 clinics → **9 qubits**) |
| **Objective** | maximise `Σ_v w_v · covered_v − μ · Σ_i fridge_i · x_i` |
| **Village weight** | `w_v` = expected envenomings per year × `(1 + λ · child share_v)` |
| **Coverage** | `covered_v = 1 − Π_{i ∈ S_v} (1 − x_i)`, where `S_v` = clinics reachable within 6 h |
| **Constraint** | `Σ_i x_i = k` (stock and staff budget); the district hospital is always stocked |

**Why it is quantum-shaped.** A village reachable from two clinics is counted once, not twice:
`x_a + x_b − x_a·x_b`. Those overlap terms make the objective a polynomial in binary variables,
not a sum, which is exactly what makes greedy imperfect. With `x_i = (1 − Z_i)/2`, each village
contributes `w_v (1 − 2^{−|S_v|} Σ_{T ⊆ S_v} Z_T)`: Z, ZZ and **ZZZ** terms. We build this
**exact** cost Hamiltonian (no QUBO truncation, no ancilla qubits) and verified its diagonal against
brute force to 1e-13 (see `avr/quantum.py`).

**Algorithms.**
- *Standard QAOA*: X mixer, budget as a penalty `A(Σx − k)²`.
- *Constraint-preserving QAOA* (Hadfield et al., 2019): start in the equal superposition of all
  plans with exactly *k* clinics (a Dicke state) and mix with XX+YY gates, which never change the
  number of stocked clinics. **Every shot is a valid plan**, so no penalty weight is needed.
- *CVaR-QAOA* (Barkoutsos et al., 2020): optimise the best α-fraction of outcomes.

All circuits are simulated with Qiskit Aer; training uses COBYLA with seeded restarts.

## Results (all from `run_experiments.py`, seeded)

Main synthetic district: 30 villages, 40,655 people, ~94 envenomings a year, 9 candidate clinics, k = 3.

| Plan | Clinics | Bites within 6 h | Child bites within 6 h |
|---|---|---|---|
| Hospital only | — | 49.2% | 49.8% |
| **Exact optimum** (brute force, 84 plans) | C1, C8, C9 | **83.4%** | **83.2%** |
| Greedy | C1, C8, C9 | 83.4% | 83.2% |
| Random valid plan (average) | — | score 0.64 of optimum | |

**QAOA (ideal simulator), main district**

| Variant | Depth p | Valid outputs | P(optimal plan) | vs random valid plan | Expected score / optimum |
|---|---|---|---|---|---|
| X mixer + penalty | 1 / 2 / 3 | 42% / 43% / 29% | 0.006 / 0.008 / 0.002 | below random | 0.66 / 0.67 / 0.69 |
| **XY mixer** (constraint-preserving) | 1 / 2 / 3 | **100%** | 0.024 / 0.067 / **0.071** | **2.0× / 5.6× / 6.0×** | 0.71 / 0.72 / 0.73 |
| XY mixer + CVaR α = 0.1 | 2 | 100% | **0.120** | 10× | 0.64 |

- **Penalty sweep** (X mixer, p = 2): penalty 0.3× max weight → only 2% valid outputs;
  3× → 62% valid but the objective is drowned out (P(optimal) 0.008). This is the known weakness
  of penalty encodings that the XY mixer removes.
- **Greedy is not always enough**: on 100 random districts, greedy misses the optimum in **9**,
  by up to **10.6%**. On the hard case (seed 82) greedy covers 80.8% of bites, the optimum 84.9%;
  QAOA (XY, p = 3) gives the optimal plan probability 0.062 (5.2× random) and it appears among the
  sampled plans.
- **Supply sweep** (`results/supply_sweep.png`): bites within 6 h rise from 49.2% (hospital only)
  to 63.3%, 75.8%, 83.4%, 88.6% and 93.4% as 1–5 clinics are stocked. Even on the main district
  greedy misses the optimum at k = 5 (91.9% vs 93.4%).
- **Equity**: in these districts children are spread evenly, so raising the child weight
  (λ from 0 to 4) changes the best plan in only 6 of 100 districts. The fridge cost does change it:
  with μ ≥ 2 the optimum swaps C9 for C6, needing one new fridge instead of two for 0.7 points
  less coverage.
- **Noise** (`run_noisy.py`, IBM Heron noise model FakeMarrakesh, 4096 shots, p = 1):

  | Variant | Transpiled depth | Two-qubit gates | Valid outputs ideal → noisy | P(optimal) ideal → noisy |
  |---|---|---|---|---|
  | X mixer + penalty | 283 | 149 | 42% → 37% | 0.006 → 0.006 |
  | XY mixer | 3,052 | 1,055 | 100% → 35% | 0.024 → 0.003 |

  The constraint-preserving circuit wins in simulation but is too deep for today's hardware.

## Honest limitations

- **Synthetic district.** Numbers are drawn from published ranges (`docs/data_sources.md`), not a
  real place. Real use needs real clinic locations and travel times.
- **No speedup claim.** At 9 qubits brute force takes milliseconds. The value here is a faithful
  quantum formulation, measured against exact answers, that is ready to scale as hardware improves.
- QAOA at p ≤ 3 concentrates probability on good plans (up to 10× random) but does not make the
  optimum the single most likely plan; deeper circuits or warm starts would be needed.
- The constraint-preserving circuit is much deeper than the standard one, so on today's noisy
  hardware it loses its advantage; this is a known trade-off.
- Coverage is binary (within 6 h or not); travel time uncertainty, rainy-season roads and stock
  quantities (vials) are not modelled. Upstream supply (manufacturers, lead times) is out of scope.

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python check_model.py          # verifies the quantum model equals the classical one (seconds)
python run_experiments.py      # all results and figures (~6 min on a laptop CPU)
python run_noisy.py            # noisy-hardware simulation
streamlit run app.py           # interactive map demo
```

Python 3.13 tested. Optional real-hardware run: save an IBM Quantum account with
`QiskitRuntimeService.save_account(...)`, then `python run_noisy.py --hardware`.

## Repository

| Path | What it is |
|---|---|
| `avr/instance.py` | synthetic district generator (seeded) |
| `avr/model.py` | exact objective, plan reports, Qiskit `QuadraticProgram` (pairwise form) |
| `avr/classical.py` | brute force, greedy, random baselines |
| `avr/quantum.py` | exact cost Hamiltonian, QAOA circuits (X / XY mixers), CVaR, sampling |
| `avr/plots.py` | maps and charts |
| `check_model.py` | self-checks: Hamiltonian = objective, Aer = numpy reference, XY keeps budget |
| `run_experiments.py`, `run_noisy.py` | reproduce every number in the report |
| `app.py` | Streamlit demo |
| `results/` | JSON results and figures |
| `docs/` | data sources, architecture diagram, report |

## Credits and references

All code in this repository was written for this hackathon. QAOA follows Farhi et al. (2014); the
XY-mixer / Dicke-state approach follows Hadfield et al., *Algorithms* 12(2) 34 (2019); CVaR-QAOA
follows Barkoutsos et al., *Quantum* 4, 256 (2020). Facility-location coverage objectives are
standard (maximal covering location problem, Church & ReVelle 1974); the Qiskit blog post
"Where should I locate my store?" applies QAOA to a related covering problem. Snakebite figures:
WHO fact sheet on snakebite envenoming; Chippaux (2011); Suraweera et al. (2020).
