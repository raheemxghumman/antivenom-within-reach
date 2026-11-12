"""Reproduce every number and figure in the report.

    python run_experiments.py           # full run (~10-15 min on a laptop CPU)
    python run_experiments.py --quick   # fewer restarts, for a smoke test

Writes results/*.json and results/*.png. All randomness is seeded.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from avr.classical import brute_force, greedy, random_baseline
from avr.instance import make_district
from avr.model import all_bitstrings, decision_villages, plan_report, plan_values
from avr.plots import COVER, INK, MISS, MUTED, STOCK, district_map, style, top_plans_bar
from avr.quantum import cost_polynomial, run_qaoa, sample, summarize

OUT = Path(__file__).parent / "results"
MAIN_SEED, HARD_SEED = 2026, 82
K, LAM, MU = 3, 1.0, 0.0


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    return o


def save(name, obj):
    (OUT / f"{name}.json").write_text(json.dumps(jsonable(obj), indent=2))


def bits_of(idx, n):
    return np.array([(idx >> j) & 1 for j in range(n)])


def qaoa_case(d, k, lam, mu, reps, mixer, penalty=0.0, alpha=1.0, restarts=4, maxiter=250):
    n = d.n_clinics
    vals = plan_values(d, all_bitstrings(n), lam, mu)
    bf, rb = brute_force(d, k, lam, mu), random_baseline(d, k, lam, mu)
    r = run_qaoa(d, k, lam, mu, reps=reps, mixer=mixer, penalty=penalty, alpha=alpha,
                 restarts=restarts, maxiter=maxiter)
    counts = sample(r, shots=4096)
    exact = summarize(r["probs"], vals, k, bf["value"], rb["mean"], n)
    shots = summarize(counts, vals, k, bf["value"], rb["mean"], n)
    best_shot = int(np.argmax(np.where(all_bitstrings(n).sum(1) == k,
                                       np.where(counts > 0, vals, -np.inf), -np.inf)))
    row = {"mixer": mixer, "reps": reps, "penalty": penalty, "alpha": alpha,
           "train_seconds": r["train_seconds"], "cost_evaluations": r["n_cost_evals"],
           "n_qubits": n, "hamiltonian_terms": r["n_terms"], "max_term_order": r["max_term_order"],
           "circuit_depth": r["circuit"].decompose(reps=2).depth(),
           "exact": exact, "sampled_4096": shots,
           "best_sampled_plan_value": float(vals[best_shot]),
           "best_sampled_is_optimal": bool(np.isclose(vals[best_shot], bf["value"])),
           "theta": r["theta"]}
    return row, r, vals, bf


def main(quick=False):
    OUT.mkdir(exist_ok=True)
    rs, it = (2, 150) if quick else (4, 250)
    t_all = time.time()
    d = make_district(MAIN_SEED)
    n = d.n_clinics
    dv = decision_villages(d)
    mult = d.reach[dv].sum(axis=1)

    # 1. Instance -------------------------------------------------------------
    inst = {"seed": MAIN_SEED, "villages": d.n_villages, "candidate_clinics": n,
            "people": int(d.village_pop.sum()),
            "expected_envenomings_per_year": float(d.envenomings.sum()),
            "villages_covered_by_hospital_alone": int(d.hospital_covers.sum()),
            "villages_decided_by_clinics": int(dv.sum()),
            "villages_out_of_reach_of_any_site": int((~d.hospital_covers & ~d.reach.any(1)).sum()),
            "villages_by_number_of_reachable_clinics": {int(m): int((mult == m).sum()) for m in np.unique(mult)},
            "clinics_without_fridge": [d.clinic_names[i] for i in range(n) if not d.clinic_fridge[i]],
            "window_hours": d.window_h, "budget_k": K, "lambda_child": LAM, "mu_fridge": MU,
            "search_space_all_bitstrings": 2 ** n,
            "search_space_valid_plans": int(brute_force(d, K, LAM, MU)["n_plans"])}
    save("instance", inst)
    print("instance:", inst)

    # 2. Classical baselines on the main district ------------------------------
    bf, gr, rb = brute_force(d, K, LAM, MU), greedy(d, K, LAM, MU), random_baseline(d, K, LAM, MU)
    none = plan_report(d, np.zeros(n, int))
    base = {"no_clinic_stocked": none,
            "optimal": {"value": bf["value"], **plan_report(d, bf["plan"])},
            "greedy": {"value": gr["value"], **plan_report(d, gr["plan"])},
            "random_mean_value": rb["mean"], "random_worst_value": rb["worst"]}
    save("baselines_main", base)
    for name, plan in [("map_no_stock", None), ("map_optimal", bf["plan"])]:
        fig = district_map(d, plan, title="Synthetic district: hospital only" if plan is None else
                           f"Optimal plan, k={K}: " + ", ".join(plan_report(d, plan)["stocked"]))
        fig.savefig(OUT / f"{name}.png", dpi=160, bbox_inches="tight")
        plt.close(fig)

    # 3. Supply sweep (how much each extra stocked clinic buys) ------------------
    sweep = []
    for k in range(0, 7):
        if k == 0:
            rep = none
            row = {"k": 0, "optimal_share": rep["share_bites_covered"], "greedy_share": rep["share_bites_covered"],
                   "random_share": rep["share_bites_covered"], "optimal_child_share": rep["share_child_bites_covered"]}
        else:
            b, g = brute_force(d, k, LAM, MU), greedy(d, k, LAM, MU)
            plans = all_bitstrings(n)[all_bitstrings(n).sum(1) == k]
            rand_share = np.mean([plan_report(d, p)["share_bites_covered"] for p in plans])
            row = {"k": k, "optimal_share": plan_report(d, b["plan"])["share_bites_covered"],
                   "greedy_share": plan_report(d, g["plan"])["share_bites_covered"],
                   "random_share": float(rand_share),
                   "optimal_child_share": plan_report(d, b["plan"])["share_child_bites_covered"],
                   "optimal_plan": plan_report(d, b["plan"])["stocked"]}
        sweep.append(row)
    save("supply_sweep", sweep)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ks = [r["k"] for r in sweep]
    ax.plot(ks, [100 * r["optimal_share"] for r in sweep], "o-", color=STOCK, label="optimal plan")
    ax.plot(ks, [100 * r["greedy_share"] for r in sweep], "s--", color=COVER, label="greedy", ms=5)
    ax.plot(ks, [100 * r["random_share"] for r in sweep], "^:", color=MISS, label="random plan (average)")
    ax.set_xlabel("clinics that can stock antivenom (k)", color=INK)
    ax.set_ylabel("% of yearly bites within 6 h of antivenom", color=INK)
    style(ax)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "supply_sweep.png", dpi=160)
    plt.close(fig)

    # 4. Child-equity and fridge-cost trade-offs (exact) -------------------------
    trade = []
    for lam in [0.0, 0.5, 1.0, 2.0, 4.0]:
        for mu in [0.0, 2.0, 5.0]:
            b = brute_force(d, K, lam, mu)
            rep = plan_report(d, b["plan"])
            trade.append({"lambda_child": lam, "mu_fridge": mu, **rep})
    save("tradeoffs", trade)

    # 5. QAOA on the main district: mixer x depth ---------------------------------
    A = float(d.weights(LAM).max())     # penalty scale: the heaviest village weight
    rows, keep = [], {}
    for mixer, pen in [("x", A), ("xy", 0.0)]:
        for p in [1, 2, 3]:
            row, r, vals, _ = qaoa_case(d, K, LAM, MU, p, mixer, pen, restarts=rs, maxiter=it)
            rows.append(row)
            keep[(mixer, p)] = r
            print(f"  QAOA {mixer} p={p}: valid {row['exact']['valid_rate']:.2f}  "
                  f"P(opt) {row['exact']['p_optimal']:.3f}  AR {row['exact']['approx_ratio_valid']:.3f}  "
                  f"{row['train_seconds']:.0f}s", flush=True)
    save("qaoa_depth", rows)
    vals = plan_values(d, all_bitstrings(n), LAM, MU)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    for ax, key, lab in [(axes[0], "p_optimal", "P(optimal plan)"), (axes[1], "valid_rate", "share of valid plans")]:
        for mixer, col, name in [("x", MISS, "standard QAOA (X mixer + penalty)"),
                                 ("xy", STOCK, "constraint-preserving QAOA (XY mixer)")]:
            ys = [r["exact"][key] for r in rows if r["mixer"] == mixer]
            ax.plot([1, 2, 3], ys, "o-", color=col, label=name)
        if key == "p_optimal":
            ax.axhline(rows[0]["exact"]["random_p_optimal"], color=MUTED, ls=":", label="random valid plan")
        ax.set_xlabel("QAOA depth p", color=INK)
        ax.set_ylabel(lab, color=INK)
        ax.set_xticks([1, 2, 3])
        style(ax)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "qaoa_depth.png", dpi=160)
    plt.close(fig)
    best_key = max(keep, key=lambda kk: summarize(keep[kk]["probs"], vals, K, bf["value"], rb["mean"], n)["p_optimal"])
    fig = top_plans_bar(d, keep[best_key]["probs"], vals, bf["value"], K,
                        title=f"QAOA output ({best_key[0].upper()} mixer, p={best_key[1]}): most likely plans")
    fig.savefig(OUT / "qaoa_top_plans.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    fig = top_plans_bar(d, keep[("x", 2)]["probs"], vals, bf["value"], K,
                        title="Standard QAOA (X mixer + penalty, p=2): most likely bitstrings")
    fig.savefig(OUT / "qaoa_top_plans_xmixer.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    # 6. Penalty-weight sweep for standard QAOA (p=2) -----------------------------
    pen_rows = []
    for f in [0.1, 0.3, 1.0, 3.0]:
        row, *_ = qaoa_case(d, K, LAM, MU, 2, "x", f * A, restarts=rs, maxiter=it)
        row["penalty_over_max_weight"] = f
        pen_rows.append(row)
        print(f"  penalty {f}xA: valid {row['exact']['valid_rate']:.2f} P(opt) {row['exact']['p_optimal']:.3f}", flush=True)
    save("penalty_sweep", pen_rows)

    # 7. CVaR objective for the XY variant (p=2) ----------------------------------
    cvar_rows = []
    for alpha in [1.0, 0.5, 0.25, 0.1]:
        row, *_ = qaoa_case(d, K, LAM, MU, 2, "xy", 0.0, alpha=alpha, restarts=rs, maxiter=it)
        cvar_rows.append(row)
        print(f"  CVaR alpha={alpha}: P(opt) {row['exact']['p_optimal']:.3f} AR {row['exact']['approx_ratio_valid']:.3f}", flush=True)
    save("cvar_sweep", cvar_rows)

    # 8. Is the problem non-trivial? Greedy vs optimal on 100 random districts ----
    stats = []
    for s in range(100):
        dd = make_district(seed=s)
        b, g = brute_force(dd, K, LAM, MU), greedy(dd, K, LAM, MU)
        stats.append({"seed": s, "gap": (b["value"] - g["value"]) / b["value"]})
    gaps = np.array([s["gap"] for s in stats])
    save("greedy_stats", {"districts": 100, "greedy_suboptimal": int((gaps > 1e-9).sum()),
                          "mean_gap": float(gaps.mean()), "max_gap": float(gaps.max()),
                          "failing_seeds": [s["seed"] for s in stats if s["gap"] > 1e-9]})

    # 9. Case study: a district where greedy is NOT optimal --------------------------
    dh = make_district(HARD_SEED)
    bh, gh = brute_force(dh, K, LAM, MU), greedy(dh, K, LAM, MU)
    hard = {"seed": HARD_SEED, "optimal": {"value": bh["value"], **plan_report(dh, bh["plan"])},
            "greedy": {"value": gh["value"], **plan_report(dh, gh["plan"])}, "qaoa": []}
    for p in [2, 3]:
        row, r, hvals, _ = qaoa_case(dh, K, LAM, MU, p, "xy", 0.0, restarts=rs, maxiter=it)
        hard["qaoa"].append(row)
        if p == 3:
            fig = top_plans_bar(dh, r["probs"], hvals, bh["value"], K,
                                title=f"Hard district (seed {HARD_SEED}): QAOA (XY, p=3) most likely plans")
            fig.savefig(OUT / "hard_qaoa_top_plans.png", dpi=160, bbox_inches="tight")
            plt.close(fig)
    save("hard_case", hard)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.4))
    district_map(dh, gh["plan"], ax=axes[0], title=f"Greedy: {', '.join(plan_report(dh, gh['plan'])['stocked'])} "
                 f"({100 * plan_report(dh, gh['plan'])['share_bites_covered']:.0f}% of bites)")
    district_map(dh, bh["plan"], ax=axes[1], title=f"Optimal: {', '.join(plan_report(dh, bh['plan'])['stocked'])} "
                 f"({100 * plan_report(dh, bh['plan'])['share_bites_covered']:.0f}% of bites)")
    fig.tight_layout()
    fig.savefig(OUT / "hard_greedy_vs_optimal.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"done in {time.time() - t_all:.0f}s -> {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    main(ap.parse_args().quick)
