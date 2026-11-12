"""Draw docs/architecture.png (run from the repo root: python docs/make_architecture.py)."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

INK, MUTED = "#1f2933", "#5b6675"
FILL = {"data": "#e8f1fb", "model": "#eaf6ef", "quantum": "#efe9f8", "classical": "#fdf0e6", "out": "#f3f4f6"}
EDGE = {"data": "#2c5aa0", "model": "#1b9e77", "quantum": "#6a3d9a", "classical": "#d95f02", "out": "#5b6675"}

boxes = {
    "data": (0.02, 0.62, 0.20, 0.30, "District data", "villages, clinics, hospital\npopulation, child share\nbite incidence, travel time\n(synthetic, sourced ranges)"),
    "model": (0.28, 0.62, 0.20, 0.30, "Optimisation model", "x_i = 1: clinic i stocks\nmax weighted bites < 6 h\nchild weight (1+λ), fridge cost μ\nexactly k clinics"),
    "ham": (0.54, 0.74, 0.20, 0.20, "Exact Hamiltonian", "Z, ZZ, ZZZ terms\n9 qubits, no ancillas"),
    "qaoa": (0.54, 0.44, 0.20, 0.24, "QAOA (Qiskit + Aer)", "X mixer + penalty  |  XY mixer\nfrom Dicke state, CVaR\nCOBYLA, seeded restarts"),
    "classical": (0.28, 0.14, 0.20, 0.30, "Classical baselines", "brute force (all 84 plans)\ngreedy max-coverage\nrandom valid plan"),
    "noise": (0.54, 0.08, 0.20, 0.26, "Noise check", "IBM Heron noise model\n(FakeMarrakesh)\noptional real QPU run"),
    "out": (0.80, 0.30, 0.18, 0.44, "Results & demo", "P(optimal), valid rate,\napprox. ratio, depth sweep\nmaps of each plan\nStreamlit app\nreport + video"),
}
kind = {"data": "data", "model": "model", "ham": "quantum", "qaoa": "quantum", "classical": "classical",
        "noise": "quantum", "out": "out"}

fig, ax = plt.subplots(figsize=(12, 5.6))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")
for key, (x, y, w, h, title, body) in boxes.items():
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006,rounding_size=0.015",
                                fc=FILL[kind[key]], ec=EDGE[kind[key]], lw=1.6))
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=11, fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h - 0.09, body, ha="center", va="top", fontsize=8.6, color=MUTED, linespacing=1.4)


def arrow(a, b, ra=(1, 0.5), rb=(0, 0.5)):
    xa, ya, wa, ha = boxes[a][:4]
    xb, yb, wb, hb = boxes[b][:4]
    ax.add_patch(FancyArrowPatch((xa + wa * ra[0], ya + ha * ra[1]), (xb + wb * rb[0], yb + hb * rb[1]),
                                 arrowstyle="-|>", mutation_scale=14, lw=1.4, color=INK,
                                 connectionstyle="arc3,rad=0"))


arrow("data", "model")
arrow("model", "ham", (1, 0.75), (0, 0.5))
arrow("ham", "qaoa", (0.5, 0), (0.5, 1))
arrow("model", "classical", (0.5, 0), (0.5, 1))
arrow("qaoa", "noise", (0.5, 0), (0.5, 1))
arrow("qaoa", "out", (1, 0.5), (0, 0.62))
arrow("classical", "out", (1, 0.5), (0, 0.2))
arrow("noise", "out", (1, 0.5), (0, 0.05))
ax.text(0.02, 0.03, "Same exact objective scores every method, so quantum and classical plans are compared like for like.",
        fontsize=9, color=MUTED, style="italic")
out = Path(__file__).parent / "architecture.png"
fig.savefig(out, dpi=170, bbox_inches="tight")
print(out)
