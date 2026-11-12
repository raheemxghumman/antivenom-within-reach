"""Figures for the experiment scripts and the report."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .instance import District  # noqa: E402

INK = "#1f2933"
MUTED = "#8a94a6"
COVER = "#1b9e77"      # covered village
MISS = "#d95f02"       # not covered
STOCK = "#2c5aa0"      # stocked clinic
IDLE = "#b8c2cc"       # candidate clinic, not stocked


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=INK, labelsize=9)
    ax.grid(alpha=0.25, lw=0.6)


def district_map(d: District, plan=None, title="", ax=None):
    """Villages sized by bite burden, green if antivenom is within the time window."""
    plan = np.zeros(d.n_clinics, bool) if plan is None else np.asarray(plan, bool)
    covered = d.hospital_covers | d.reach[:, plan].any(axis=1)
    own = ax is None
    if own:
        fig, ax = plt.subplots(figsize=(6.2, 6.2))
    sizes = 30 + 140 * d.envenomings / d.envenomings.max()
    ax.scatter(*d.village_xy[~covered].T, s=sizes[~covered], c=MISS, alpha=0.85,
               edgecolor="white", lw=0.8, label="village, antivenom > 6 h away", zorder=3)
    ax.scatter(*d.village_xy[covered].T, s=sizes[covered], c=COVER, alpha=0.85,
               edgecolor="white", lw=0.8, label="village, antivenom within 6 h", zorder=3)
    for i, (x, y) in enumerate(d.clinic_xy):
        on = plan[i]
        ax.scatter(x, y, marker="s", s=150 if on else 90, c=STOCK if on else IDLE,
                   edgecolor=INK if on else MUTED, lw=1.2, zorder=4)
        tag = d.clinic_names[i] + ("" if d.clinic_fridge[i] else "*")
        ax.annotate(tag, (x, y), xytext=(6, 6), textcoords="offset points", fontsize=9,
                    color=INK if on else MUTED, fontweight="bold" if on else "normal", zorder=5)
        if on:   # links from the stocked clinic to the villages it brings within reach
            for v in np.where(d.reach[:, i] & ~d.hospital_covers)[0]:
                ax.plot(*np.c_[d.clinic_xy[i], d.village_xy[v]], color=STOCK, alpha=0.25, lw=1, zorder=1)
    ax.scatter(*d.hospital_xy, marker="P", s=260, c="#7b2d8b", edgecolor="white", lw=1, zorder=5,
               label="district hospital (always stocked)")
    ax.scatter([], [], marker="s", s=90, c=STOCK, edgecolor=INK, label="clinic stocking antivenom")
    ax.scatter([], [], marker="s", s=70, c=IDLE, edgecolor=MUTED, label="candidate clinic (* = needs fridge)")
    ax.set_aspect("equal")
    ax.set_xlabel("km", color=INK)
    ax.set_ylabel("km", color=INK)
    style(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2, fontsize=8, frameon=False)
    if title:
        ax.set_title(title, color=INK, fontsize=11, loc="left")
    if own:
        fig.tight_layout()
        return fig
    return ax


def plan_label(d: District, idx: int) -> str:
    on = [d.clinic_names[j] for j in range(d.n_clinics) if (idx >> j) & 1]
    return "+".join(on) if on else "(none)"


def top_plans_bar(d: District, probs, plan_vals_all, opt_value, k, top=12, ax=None, title=""):
    """Probability of the most likely plans; the optimal plan is highlighted."""
    weight = np.array([bin(i).count("1") for i in range(len(probs))])
    idx = np.argsort(-probs)[:top]
    own = ax is None
    if own:
        fig, ax = plt.subplots(figsize=(7.5, 3.6))
    colors = [STOCK if (weight[i] == k and np.isclose(plan_vals_all[i], opt_value)) else
              (IDLE if weight[i] == k else MISS) for i in idx]
    ax.bar(range(len(idx)), probs[idx], color=colors)
    ax.set_xticks(range(len(idx)))
    ax.set_xticklabels([plan_label(d, i) for i in idx], rotation=60, ha="right", fontsize=8)
    ax.set_ylabel("probability", color=INK)
    style(ax)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=STOCK, label="optimal plan"), Patch(color=IDLE, label="valid plan"),
                       Patch(color=MISS, label=f"breaks budget (not {k} clinics)")],
              fontsize=8, frameon=False)
    if title:
        ax.set_title(title, color=INK, fontsize=11, loc="left")
    if own:
        fig.tight_layout()
        return fig
    return ax
