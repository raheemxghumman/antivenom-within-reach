"""Interactive demo:  streamlit run app.py

Pick a district, a stock budget and the child-equity weight, then compare the exact optimum,
greedy and QAOA on the map. QAOA runs live on the Qiskit Aer simulator (a few seconds).
"""
from __future__ import annotations

import time

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from avr.classical import brute_force, greedy, random_baseline
from avr.instance import make_district
from avr.model import all_bitstrings, plan_report, plan_values
from avr.plots import district_map, top_plans_bar
from avr.quantum import run_qaoa, sample, summarize

st.set_page_config(page_title="Antivenom Within Reach", layout="wide")
st.title("Antivenom Within Reach")
st.caption("Which rural clinics should stock snakebite antivenom? Exact search vs greedy vs QAOA "
           "(Qiskit). The district is synthetic; see docs/data_sources.md.")

with st.sidebar:
    st.header("Scenario")
    preset = st.radio("District", ["Main district (seed 2026)", "Hard case: greedy fails (seed 82)", "Custom seed"])
    seed = {"Main district (seed 2026)": 2026, "Hard case: greedy fails (seed 82)": 82}.get(preset)
    if seed is None:
        seed = int(st.number_input("seed", 0, 10_000, 7))
    k = st.slider("Clinics that can stock antivenom (k)", 1, 6, 3)
    lam = st.slider("Child-equity weight λ (a child's bite counts 1+λ)", 0.0, 4.0, 1.0, 0.5)
    mu = st.slider("Cost of a new solar fridge μ (in weighted bites/yr)", 0.0, 10.0, 0.0, 1.0)
    st.header("Quantum solver")
    mixer = st.radio("QAOA variant", ["XY mixer (constraint-preserving)", "X mixer + budget penalty"])
    reps = st.slider("QAOA depth p", 1, 3, 2)
    go = st.button("Run QAOA", type="primary")


@st.cache_data(show_spinner=False)
def classical(seed, k, lam, mu):
    d = make_district(seed)
    return d, brute_force(d, k, lam, mu), greedy(d, k, lam, mu), random_baseline(d, k, lam, mu)


@st.cache_data(show_spinner=False)
def quantum(seed, k, lam, mu, mixer_key, reps):
    d = make_district(seed)
    pen = float(d.weights(lam).max()) if mixer_key == "x" else 0.0
    r = run_qaoa(d, k, lam, mu, reps=reps, mixer=mixer_key, penalty=pen, restarts=2, maxiter=150)
    return r["probs"], sample(r, shots=2048), r["train_seconds"]


d, bf, gr, rb = classical(seed, k, lam, mu)
n = d.n_clinics
vals = plan_values(d, all_bitstrings(n), lam, mu)
mixer_key = "xy" if mixer.startswith("XY") else "x"

rows = {"Exact optimum (brute force, all plans)": bf["plan"], "Greedy max-coverage": gr["plan"]}
qres = None
if go or st.session_state.get("last") == (seed, k, lam, mu, mixer_key, reps):
    with st.spinner("Training QAOA on the Aer simulator..."):
        t = time.time()
        probs, counts, secs = quantum(seed, k, lam, mu, mixer_key, reps)
    st.session_state["last"] = (seed, k, lam, mu, mixer_key, reps)
    valid = all_bitstrings(n).sum(1) == k
    best_shot = int(np.argmax(np.where(valid & (counts > 0), vals, -np.inf)))
    rows["QAOA (best of 2048 shots)"] = all_bitstrings(n)[best_shot]
    qres = (probs, counts, secs, summarize(probs, vals, k, bf["value"], rb["mean"], n))

choice = st.selectbox("Show plan on map", list(rows))
left, right = st.columns([1.15, 1])
with left:
    fig = district_map(d, rows[choice], title=choice)
    st.pyplot(fig, clear_figure=True)
with right:
    st.subheader("Plans compared")
    table = []
    for name, plan in rows.items():
        rep = plan_report(d, plan)
        table.append({"method": name, "clinics": ", ".join(rep["stocked"]),
                      "bites within 6 h": f"{100 * rep['share_bites_covered']:.1f}%",
                      "child bites within 6 h": f"{100 * rep['share_child_bites_covered']:.1f}%",
                      "new fridges": rep["new_fridges_needed"],
                      "score / optimum": f"{plan_values(d, plan, lam, mu)[0] / bf['value']:.3f}"})
    st.dataframe(table, hide_index=True, width="stretch")
    st.caption(f"Random valid plan scores {rb['mean'] / bf['value']:.3f} of the optimum on average. "
               f"{bf['n_plans']} valid plans out of {2 ** n} bitstrings.")
    if qres:
        probs, counts, secs, s = qres
        c1, c2, c3 = st.columns(3)
        c1.metric("P(optimal plan)", f"{s['p_optimal']:.3f}", f"{s['boost_vs_random']:.1f}x random")
        c2.metric("Valid samples", f"{100 * s['valid_rate']:.0f}%")
        c3.metric("Expected score / optimum", f"{s['approx_ratio_valid']:.3f}")
        st.caption(f"Trained in {secs:.1f}s on 9 qubits, depth p={reps}.")
    else:
        st.info("Press **Run QAOA** in the sidebar to solve the same problem on a quantum circuit.")

if qres:
    st.subheader("What the quantum circuit outputs")
    fig = top_plans_bar(d, qres[0], vals, bf["value"], k, title="Most likely plans after training")
    st.pyplot(fig, clear_figure=True)
plt.close("all")
