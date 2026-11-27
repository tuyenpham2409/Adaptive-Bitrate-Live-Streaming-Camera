#!/usr/bin/env python3
"""Week 4 figures for the multi-viewer model and the tool validations. Run from models/."""
import os
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE, GREEN, INK, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#1baf7a", "#1d1d1f", "#6b6b70", "#e6e6e3", "#fcfcfb"
OUT = "../results/week4"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.facecolor": SURF, "figure.facecolor": SURF})

d = pd.read_csv(f"{OUT}/multi_viewer_sim.csv")
links = sorted(d.link_kbps.unique())
fig, ax = plt.subplots(2, len(links), figsize=(9.6, 5.4), sharex=True)
for j, c in enumerate(links):
    for name, col, ls, mk in (("hls.js default", BLUE, "-", "o"), ("Hybrid (team)", ORANGE, "-", "s")):
        s = d[(d.link_kbps == c) & (d.controller == name)]
        ax[0, j].plot(s.viewers, s.avg_bitrate_kbps, color=col, lw=1.8, marker=mk, ms=4, label=name)
        ax[1, j].plot(s.viewers, s.fairness, color=col, lw=1.8, marker=mk, ms=4)
    n = d.viewers.unique()
    ax[0, j].plot(n, [min(2628, c / k) for k in n], color=MUTED, lw=1, ls="--", label="ideal fair share (max 720p)")
    ax[0, j].set_title("link %.0f Mbit/s" % (c / 1000), color=INK, fontsize=10, loc="left")
    ax[0, j].set_ylim(0, 2900); ax[1, j].set_ylim(0.6, 1.02); ax[1, j].set_xlabel("viewers")
    for r in (0, 1): ax[r, j].grid(color=GRID, lw=0.6); [ax[r, j].spines[s].set_visible(False) for s in ("top", "right")]
ax[0, 0].set_ylabel("mean bitrate per viewer (kbit/s)"); ax[1, 0].set_ylabel("Jain fairness index")
ax[0, 0].legend(frameon=False, fontsize=8, loc="lower left")
fig.suptitle("Shared Wi-Fi uplink: quality and fairness vs number of viewers (model, 0 stalls in every run)", x=0.01, ha="left", fontsize=10.5, color=INK)
fig.tight_layout(rect=(0, 0, 1, 0.95)); fig.savefig(f"{OUT}/fig_multi_viewer_model.png", dpi=170)
print("saved")
