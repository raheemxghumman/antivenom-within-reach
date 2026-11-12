"""Run the trained QAOA circuits on a real IBM quantum computer.

    python run_hardware.py            # needs an IBM Quantum account saved with
                                      # QiskitRuntimeService.save_account(...)
    python run_hardware.py --dry-run  # only train + transpile + noisy simulation, no QPU
    python run_hardware.py --replot   # redraw the figure from the saved hardware results

Two circuits (main benchmark district, 9 qubits) are trained on the ideal simulator,
transpiled for the least-busy IBM QPU and sent in ONE job (two PUBs, 4096 shots each):
  * standard QAOA (X mixer + budget penalty), p = 1
  * hardware-friendly constraint-preserving QAOA (ring XY mixer), p = 1
The same circuits are also run on an Aer simulation of that device's noise model, so
ideal / simulated-noise / real-hardware can be compared side by side.
Results: results/hardware_run.json and results/hardware_vs_sim.png. The job ID is saved so it
can be checked on the IBM Quantum Platform (Workloads page).
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator

from avr.classical import brute_force, random_baseline
from avr.instance import make_district
from avr.model import all_bitstrings, plan_values
from avr.plots import INK, MISS, MUTED, STOCK, style
from avr.quantum import run_qaoa, summarize

OUT = Path(__file__).parent / "results"
K, LAM, MU, SHOTS = 3, 1.0, 0.0, 4096


def vec(counts, n):
    v = np.zeros(2 ** n)
    for b, c in counts.items():
        v[int(b, 2)] = c
    return v


def main(dry_run=False):
    d = make_district(2026)
    n = d.n_clinics
    vals = plan_values(d, all_bitstrings(n), LAM, MU)
    bf, rb = brute_force(d, K, LAM, MU), random_baseline(d, K, LAM, MU)
    variants = [("x", float(d.weights(LAM).max()), 1), ("xyring", 0.0, 1)]
    trained = []
    for mixer, pen, reps in variants:
        r = run_qaoa(d, K, LAM, MU, reps=reps, mixer=mixer, penalty=pen, restarts=4, maxiter=250)
        qc = r["circuit"].assign_parameters(r["theta"])
        qc.measure_all()
        trained.append((mixer, r, qc))
        print(f"trained {mixer}: ideal P(opt) {summarize(r['probs'], vals, K, bf['value'], rb['mean'], n)['p_optimal']:.3f}")

    if dry_run:
        from qiskit_ibm_runtime.fake_provider import FakeMarrakesh
        backend = FakeMarrakesh()
    else:
        from qiskit_ibm_runtime import QiskitRuntimeService
        service = QiskitRuntimeService()
        backend = service.least_busy(operational=True, simulator=False)
    pm = generate_preset_pass_manager(optimization_level=3, backend=backend, seed_transpiler=7)
    isas = [pm.run(qc) for _, _, qc in trained]
    for (mixer, _, _), isa in zip(trained, isas):
        ops = isa.count_ops()
        print(f"{mixer}: transpiled depth {isa.depth()}, two-qubit gates {ops.get('cz', 0) + ops.get('ecr', 0)}")

    noisy_sim = AerSimulator.from_backend(backend)
    noisy_counts = [noisy_sim.run(isa, shots=SHOTS, seed_simulator=3).result().get_counts() for isa in isas]

    hw = None
    if not dry_run:
        from qiskit_ibm_runtime import SamplerV2
        sampler = SamplerV2(mode=backend)
        job = sampler.run(isas, shots=SHOTS)
        sent = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print(f"JOB SENT to {backend.name}: {job.job_id()} at {sent}", flush=True)
        t0 = time.time()
        result = job.result()
        hw = {"backend": backend.name, "job_id": job.job_id(), "sent_utc": sent,
              "wall_seconds": round(time.time() - t0, 1),
              "counts": [res.data.meas.get_counts() for res in result]}
        try:
            hw["usage_quantum_seconds"] = job.usage()
        except Exception:  # noqa: BLE001
            pass

    rows = []
    for i, (mixer, r, _) in enumerate(trained):
        ops = isas[i].count_ops()
        row = {"mixer": mixer, "reps": r["reps"], "theta": r["theta"].tolist(),
               "transpiled_depth": isas[i].depth(), "two_qubit_gates": int(ops.get("cz", 0) + ops.get("ecr", 0)),
               "ideal": summarize(r["probs"], vals, K, bf["value"], rb["mean"], n),
               "noisy_simulation": summarize(vec(noisy_counts[i], n), vals, K, bf["value"], rb["mean"], n)}
        if hw:
            row["real_hardware"] = summarize(vec(hw["counts"][i], n), vals, K, bf["value"], rb["mean"], n)
        rows.append(row)
    out = {"district": "main benchmark (seed 2026)", "k": K, "shots": SHOTS,
           "backend": backend.name, "hardware": {k: v for k, v in (hw or {}).items() if k != "counts"},
           "circuits": rows}
    name = "hardware_run" if hw else "hardware_dry_run"
    (OUT / f"{name}.json").write_text(json.dumps(out, indent=2, default=float))
    if hw:
        (OUT / "hardware_counts.json").write_text(json.dumps(hw["counts"]))

    plot(OUT / f"{name}.json", rb["mean"] / bf["value"])
    print(json.dumps({r["mixer"]: {k: r[k]["valid_rate"] for k in r if isinstance(r[k], dict)} for r in rows}))


def plot(json_path: Path, random_ratio: float | None = None):
    """Ideal vs noise-model vs real-QPU comparison figure, drawn from the saved results."""
    out = json.loads(json_path.read_text())
    rows, backend = out["circuits"], out["backend"]
    hw = "real_hardware" in rows[0]
    if random_ratio is None:
        d = make_district(2026)
        random_ratio = random_baseline(d, K, LAM, MU)["mean"] / brute_force(d, K, LAM, MU)["value"]
    labels = ["ideal simulator", f"noise model of {backend}"] + ([f"real QPU: {backend}"] if hw else [])
    keys = ["ideal", "noisy_simulation"] + (["real_hardware"] if hw else [])
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))
    colors = [STOCK, MUTED, MISS]
    names = [f"standard QAOA, p={r['reps']}\n(X mixer + penalty)" if r["mixer"] == "x" else
             f"constraint-preserving, p={r['reps']}\n(ring XY mixer)" for r in rows]
    for ax, metric, title in [(axes[0], "valid_rate", "share of shots that are valid plans"),
                              (axes[1], "approx_ratio_valid", "expected score of valid plans / optimum")]:
        x = np.arange(len(rows))
        w = 0.8 / len(keys)
        for j, key in enumerate(keys):
            vals = [row[key][metric] for row in rows]
            bars = ax.bar(x + (j - (len(keys) - 1) / 2) * w, vals, w, color=colors[j], label=labels[j])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5, color=INK)
        ax.set_xticks(x)
        ax.set_xticklabels(names)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        style(ax)
    axes[0].set_ylim(0, 1.12)
    axes[1].axhline(random_ratio, color=INK, ls=":", lw=1, label="random valid plan")
    axes[1].set_ylim(0.5, 0.82)
    handles, labs = axes[1].get_legend_handles_labels()
    fig.legend(handles, labs, loc="upper center", ncol=4, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(json_path.with_name("hardware_vs_sim.png" if hw else "hardware_dry_run.png"), dpi=160)
    plt.close(fig)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--replot", action="store_true", help="redraw the figure from results/hardware_run.json")
    a = ap.parse_args()
    if a.replot:
        plot(OUT / "hardware_run.json")
    else:
        main(a.dry_run)
