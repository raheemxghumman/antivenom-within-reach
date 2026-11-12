"""Real-geography case study: Sanghar district, Sindh, Pakistan.

    python run_sanghar.py

Facility and settlement locations are real (OpenStreetMap); demand is modelled (see avr/sanghar.py).
Writes results/sanghar_*.json and results/sanghar_*.png.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from avr.classical import brute_force, greedy, random_baseline
from avr.model import all_bitstrings, decision_villages, plan_report, plan_values
from avr.plots import COVER, INK, MISS, MUTED, STOCK, style, top_plans_bar
from avr.quantum import run_qaoa, sample, summarize
from avr.sanghar import make_sanghar

OUT = Path(__file__).parent / "results"
K, LAM, MU = 3, 1.0, 0.0


def named(d, plan):
    return [d.clinic_labels[i] for i in np.where(np.asarray(plan, bool))[0]]


def sanghar_map(d, plan, title, ax):
    plan = np.asarray(plan, bool)
    covered = d.hospital_covers | d.reach[:, plan].any(axis=1)
    ll = d.village_latlon
    s = 20 + 260 * np.sqrt(d.envenomings / d.envenomings.max())
    ax.scatter(ll[~covered, 1], ll[~covered, 0], s=s[~covered], c=MISS, alpha=0.8, edgecolor="white", lw=0.7,
               label="settlement, no antivenom within 1 h")
    ax.scatter(ll[covered, 1], ll[covered, 0], s=s[covered], c=COVER, alpha=0.8, edgecolor="white", lw=0.7,
               label="settlement, antivenom within 1 h")
    for i, (la, lo) in enumerate(d.clinic_latlon):
        on = plan[i]
        ax.scatter(lo, la, marker="s", s=120 if on else 60, c=STOCK if on else "#b8c2cc",
                   edgecolor=INK if on else MUTED, zorder=4)
        if on:
            ax.annotate(d.clinic_labels[i], (lo, la), xytext=(5, 5), textcoords="offset points", fontsize=8,
                        color=INK, fontweight="bold")
    ax.scatter(d.hospital_latlon[1], d.hospital_latlon[0], marker="P", s=240, c="#7b2d8b", edgecolor="white",
               zorder=5, label="Civil Hospital, Sanghar")
    ax.scatter([], [], marker="s", s=80, c=STOCK, edgecolor=INK, label="BHU stocking antivenom")
    ax.scatter([], [], marker="s", s=50, c="#b8c2cc", edgecolor=MUTED, label="candidate BHU")
    ax.set_xlabel("longitude", color=INK)
    ax.set_ylabel("latitude", color=INK)
    ax.set_aspect(1 / np.cos(np.radians(26.05)))
    style(ax)
    ax.set_title(title, color=INK, fontsize=10.5, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=7.5, frameon=False)


def main():
    t0 = time.time()
    d = make_sanghar()
    n = d.n_clinics
    dv = decision_villages(d)
    bits = all_bitstrings(n)
    vals = plan_values(d, bits, LAM, MU)
    bf, gr, rb = brute_force(d, K, LAM, MU), greedy(d, K, LAM, MU), random_baseline(d, K, LAM, MU)
    none = plan_report(d, np.zeros(n, int))
    summary = {
        "district": "Sanghar, Sindh, Pakistan",
        "data": "OpenStreetMap (facility and settlement locations); demand modelled",
        "settlements": d.n_villages, "people_modelled": int(d.village_pop.sum()),
        "expected_envenomings_per_year": float(d.envenomings.sum()),
        "candidate_sites": d.clinic_labels, "window_hours": d.window_h, "budget_k": K,
        "settlements_covered_by_hospital": int(d.hospital_covers.sum()),
        "settlements_decided_by_bhus": int(dv.sum()),
        "max_bhus_reaching_one_settlement": int(d.reach[dv].sum(1).max()),
        "hospital_only": none,
        "optimal": {"value": bf["value"], **plan_report(d, bf["plan"]), "sites": named(d, bf["plan"])},
        "greedy": {"value": gr["value"], **plan_report(d, gr["plan"]), "sites": named(d, gr["plan"])},
        "random_mean_over_optimal": rb["mean"] / bf["value"],
        "supply_sweep": [],
        "qaoa": [],
    }
    for k in range(1, 6):
        b = brute_force(d, k, LAM, MU)
        summary["supply_sweep"].append({"k": k, "share_bites": plan_report(d, b["plan"])["share_bites_covered"],
                                        "sites": named(d, b["plan"])})
    for mixer, p, alpha in [("xy", 1, 1.0), ("xy", 2, 1.0), ("xy", 3, 1.0), ("xy", 2, 0.1)]:
        r = run_qaoa(d, K, LAM, MU, reps=p, mixer=mixer, alpha=alpha, restarts=4, maxiter=250)
        counts = sample(r, shots=4096)
        row = {"mixer": mixer, "reps": p, "alpha": alpha, "train_seconds": r["train_seconds"],
               "hamiltonian_terms": r["n_terms"], "max_term_order": r["max_term_order"],
               "exact": summarize(r["probs"], vals, K, bf["value"], rb["mean"], n),
               "sampled_4096": summarize(counts, vals, K, bf["value"], rb["mean"], n), "theta": r["theta"].tolist()}
        summary["qaoa"].append(row)
        print(f"  Sanghar QAOA {mixer} p={p} a={alpha}: P(opt) {row['exact']['p_optimal']:.3f} "
              f"({row['exact']['boost_vs_random']:.1f}x)  AR {row['exact']['approx_ratio_valid']:.3f}  "
              f"{r['train_seconds']:.0f}s", flush=True)
        if (p, alpha) == (3, 1.0):
            fig = top_plans_bar(d, r["probs"], vals, bf["value"], K,
                                title="Sanghar: QAOA (XY mixer, p=3) most likely plans")
            ax = fig.axes[0]
            idx = np.argsort(-r["probs"])[:12]
            ax.set_xticklabels([" + ".join(d.clinic_labels[j].split(" / ")[0] for j in range(n) if (i >> j) & 1)
                                for i in idx], rotation=60, ha="right", fontsize=7)
            fig.savefig(OUT / "sanghar_qaoa_top_plans.png", dpi=160, bbox_inches="tight")
            plt.close(fig)
    (OUT / "sanghar.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.6))
    sanghar_map(d, np.zeros(n, int), f"Hospital only: {100 * none['share_bites_covered']:.0f}% of bites within 1 h", axes[0])
    sanghar_map(d, bf["plan"], f"Optimal {K} BHUs: {100 * summary['optimal']['share_bites_covered']:.0f}% of bites within 1 h", axes[1])
    fig.suptitle("Sanghar district, Sindh: real BHU and settlement locations (OpenStreetMap), modelled demand",
                 fontsize=10, color=MUTED, y=0.995)
    fig.tight_layout()
    fig.savefig(OUT / "sanghar_map.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
