"""How the trained QAOA circuits behave on noisy hardware.

    python run_noisy.py              # Aer simulation with an IBM Heron noise model (FakeMarrakesh)
    python run_noisy.py --hardware   # also send ONE job to a real IBM QPU (needs a saved account)

Trains on the ideal simulator, then runs the fixed circuit with 4096 shots under noise.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeMarrakesh

from avr.classical import brute_force, random_baseline
from avr.instance import make_district
from avr.model import all_bitstrings, plan_values
from avr.quantum import run_qaoa, summarize

OUT = Path(__file__).parent / "results"
K, LAM, MU = 3, 1.0, 0.0


def counts_vector(counts, n):
    out = np.zeros(2 ** n)
    for bits, c in counts.items():
        out[int(bits, 2)] = c
    return out


def main(hardware=False):
    d = make_district(2026)
    n = d.n_clinics
    vals = plan_values(d, all_bitstrings(n), LAM, MU)
    bf, rb = brute_force(d, K, LAM, MU), random_baseline(d, K, LAM, MU)
    fake = FakeMarrakesh()
    noisy = AerSimulator.from_backend(fake)
    rows = []
    for mixer, pen in [("x", float(d.weights(LAM).max())), ("xy", 0.0)]:
        r = run_qaoa(d, K, LAM, MU, reps=1, mixer=mixer, penalty=pen, restarts=4, maxiter=250)
        qc = r["circuit"].assign_parameters(r["theta"])
        qc.measure_all()
        isa = generate_preset_pass_manager(optimization_level=3, backend=fake, seed_transpiler=1).run(qc)
        ops = isa.count_ops()
        counts = noisy.run(isa, shots=4096, seed_simulator=5).result().get_counts()
        cv = counts_vector(counts, n)
        row = {"mixer": mixer, "reps": 1, "backend_noise_model": fake.name,
               "transpiled_depth": isa.depth(), "two_qubit_gates": int(ops.get("cz", 0) + ops.get("ecr", 0)),
               "ideal": summarize(r["probs"], vals, K, bf["value"], rb["mean"], n),
               "noisy_4096_shots": summarize(cv, vals, K, bf["value"], rb["mean"], n)}
        if hardware:
            from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
            svc = QiskitRuntimeService()
            backend = svc.least_busy(operational=True, simulator=False)
            isa_hw = generate_preset_pass_manager(optimization_level=3, backend=backend, seed_transpiler=1).run(qc)
            job = SamplerV2(mode=backend).run([isa_hw], shots=4096)
            print(f"  sent {mixer} circuit to {backend.name}: job {job.job_id()}", flush=True)
            hv = counts_vector(job.result()[0].data.meas.get_counts(), n)
            row["hardware"] = {"backend": backend.name, "job_id": job.job_id(),
                               "transpiled_depth": isa_hw.depth(),
                               **summarize(hv, vals, K, bf["value"], rb["mean"], n)}
        rows.append(row)
        print(mixer, json.dumps({k: v for k, v in row.items() if k != "ideal"}, default=float)[:600], flush=True)
    name = "hardware_run" if hardware else "noisy_sim"
    (OUT / f"{name}.json").write_text(json.dumps(rows, indent=2, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--hardware", action="store_true")
    main(ap.parse_args().hardware)
