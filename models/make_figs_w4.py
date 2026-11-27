#!/usr/bin/env python3
"""Figures for week 4: Hybrid ABR vs hls.js default (model)."""
import os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
import abr_sim as m, abr_custom as c

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURF, INK, MUTED, GRID = "#fcfcfb", "#1f2328", "#6b7280", "#e5e7eb"
plt.rcParams.update({"font.size": 10, "axes.facecolor": SURF, "figure.facecolor": SURF, "axes.edgecolor": GRID,
                     "axes.labelcolor": INK, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .6})
here = os.path.dirname(__file__); D = os.path.join(here, "..", "data", "week3"); O = os.path.join(here, "..", "results", "week4")
os.makedirs(O, exist_ok=True)

def fig_timeline():
    sch, T = c.sched_B(D)
    r0 = c.run(c.HlsDefault(), sch, T); r1 = c.run(c.Hybrid(), sch, T)
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True, gridspec_kw={"height_ratios": [1, 1.3]})
    xs = [s for s, _ in sch] + [T]; ys = [min(r, 6000) for _, r in sch] + [min(sch[-1][1], 6000)]
    ax[0].step(xs, ys, where="post", color=MUTED, lw=1.8); ax[0].set_ylabel("link rate (kbit/s)")
    ax[0].set_title("Model, tc schedule of run B: hls.js default vs Hybrid controller", loc="left", fontsize=11)
    ax[1].step(r0.t, r0.level, where="post", color=BLUE, lw=2.2, label="hls.js default")
    ax[1].step(r1.t, r1.level, where="post", color=ORANGE, lw=1.8, ls="--", label="Hybrid (team)")
    ax[1].set_yticks([0, 1, 2]); ax[1].set_yticklabels(["360p", "540p", "720p"]); ax[1].set_ylim(-.4, 2.4)
    ax[1].set_xlabel("time (s)"); ax[1].legend(frameon=False, loc="lower right", fontsize=9)
    for a in ax:
        for s, _ in sch: a.axvline(s, color=GRID, lw=.6, zorder=0)
    fig.tight_layout(); fig.savefig(f"{O}/fig_hybrid_timeline.png", dpi=160); plt.close(fig)

def fig_bars():
    ev = pd.read_csv(f"{O}/abr_custom_vs_default.csv")
    sc = ["B schedule (deterministic)", "random walk 0.9-6 Mbit/s", "short 3 s dips to 0.7 Mbit/s"]
    lab = ["tc schedule B", "random walk", "3 s dips"]
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    w = .36
    for k, (col, ttl, div) in enumerate([("avg_bitrate_kbps", "mean played bitrate (kbit/s)", 1), ("stall_s", "stall time per run (s)", 1)]):
        for i, (name, color) in enumerate([("hls.js default", BLUE), ("Hybrid (team)", ORANGE)]):
            v = [ev[(ev.scenario == s) & (ev.controller == name)][col].iloc[0] for s in sc]
            x = np.arange(3) + (i - .5) * w
            ax[k].bar(x, v, w - .02, color=color, label=name)
            for xi, vi in zip(x, v): ax[k].text(xi, vi, f"{vi:.0f}" if k == 0 else f"{vi:.2f}", ha="center", va="bottom", fontsize=8)
        ax[k].set_xticks(range(3)); ax[k].set_xticklabels(lab); ax[k].set_title(ttl, loc="left", fontsize=10); ax[k].grid(axis="x", visible=False)
    ax[0].legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout(); fig.savefig(f"{O}/fig_hybrid_bars.png", dpi=160); plt.close(fig)

if __name__ == "__main__":
    fig_timeline(); fig_bars(); print(sorted(os.listdir(O)))
