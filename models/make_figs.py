#!/usr/bin/env python3
"""Figures for the week-3 report: ABR simulation vs measurement."""
import os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(__file__))
import abr_sim as m

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURF, INK, MUTED, GRID = "#fcfcfb", "#1f2328", "#6b7280", "#e5e7eb"
plt.rcParams.update({"font.size": 10, "axes.facecolor": SURF, "figure.facecolor": SURF,
                     "axes.edgecolor": GRID, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": .6})
here = os.path.dirname(__file__); D = os.path.join(here, "..", "data", "week3"); O = os.path.join(here, "..", "results", "week3")
os.makedirs(O, exist_ok=True)
LV = {"360p": 0, "540p": 1, "720p": 2}

def fig_run(n, fname):
    abr = pd.read_csv(f"{D}/abr_log_{n}.csv"); tc = pd.read_csv(f"{D}/tc_{n}.csv")
    tt, lv, sch = m.metrics_real(abr, tc)
    sim = m.simulate(sch, tt[-1], sync=m.SYNC_OF[n])
    fig, ax = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True, gridspec_kw={"height_ratios": [1.5, 1]})
    st = [(s, r) for s, r in sch] + [(tt[-1], sch[-1][1])]
    xs = [s for s, _ in st]; ys = [min(r, 30000) for _, r in st]
    ax[0].step(xs, ys, where="post", color=MUTED, lw=1.6, label="tc limit (link rate)")
    ax[0].plot(tt, abr.est_kbps, color=BLUE, lw=1.5, label="hls.js estimate (measured)")
    ax[0].plot(sim.t, sim.est, color=ORANGE, lw=1.5, label="Python model estimate")
    for k, c in LV.items():
        ax[0].axhline(m.LEVELS[k][0] / m.UP_F, color=GRID, lw=0.8, ls=":")
    ax[0].set_yscale("log"); ax[0].set_ylim(400, 40000); ax[0].set_ylabel("kbit/s (log)")
    ax[0].legend(frameon=False, loc="upper right", fontsize=8.5, ncol=1)
    ax[0].set_title(f"Run {n}: segment {m.SEG_OF[n]:g} s, live sync {m.SYNC_OF[n]} - measured vs simulated ABR", loc="left", fontsize=11)
    ax[1].step(tt, [LV[l] for l in lv], where="post", color=BLUE, lw=2.2, label="measured rendition")
    ax[1].step(sim.t, [LV[l] for l in sim.level], where="post", color=ORANGE, lw=1.8, ls="--", label="simulated rendition")
    ax[1].set_yticks([0, 1, 2]); ax[1].set_yticklabels(["360p", "540p", "720p"]); ax[1].set_ylim(-.4, 2.4)
    ax[1].set_xlabel("time since start of log (s)"); ax[1].legend(frameon=False, loc="lower right", fontsize=8.5)
    for a in ax:
        for s, r in sch: a.axvline(s, color=GRID, lw=.6, zorder=0)
    fig.tight_layout(); fig.savefig(f"{O}/{fname}", dpi=160); plt.close(fig)

def fig_validate():
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
    for a, n in zip(ax, "ABC"):
        abr = pd.read_csv(f"{D}/abr_log_{n}.csv"); st, mod = m.validate(abr, m.SEG_OF[n])
        ok = ~np.isnan(mod)
        a.scatter(abr.est_kbps[ok], mod[ok], s=6, color=BLUE, alpha=.45, lw=0)
        a.plot([300, 5e4], [300, 5e4], color=MUTED, lw=1, ls="--")
        a.set_xscale("log"); a.set_yscale("log"); a.set_xlim(300, 5e4); a.set_ylim(300, 5e4)
        a.set_title(f"Run {n}: median error {st['median_abs_pct']:.1f}%", fontsize=9.5, loc="left")
        a.set_xlabel("browser estimate (kbit/s)")
    ax[0].set_ylabel("model estimate (kbit/s)")
    fig.tight_layout(); fig.savefig(f"{O}/fig_sim_validation.png", dpi=160); plt.close(fig)

def fig_whatif():
    df = pd.read_csv(f"{O}/abr_whatif.csv")
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    w = .26
    for i, (sl, c) in enumerate([(9, BLUE), (6, ORANGE), (4, AQUA)]):
        d = df[df.slow_halflife == sl].sort_values("up_factor")
        x = np.arange(3) + (i - 1) * (w + .02)
        b = ax.bar(x, d.up_to_720_s, w, color=c, label=f"slow half-life {sl} s")
        for xi, v in zip(x, d.up_to_720_s): ax.text(xi, v + 1.2, f"{v:.0f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(3)); ax.set_xticklabels([f"up factor {u}" for u in sorted(df.up_factor.unique())])
    ax.set_ylabel("delay to 720p after the 5 Mbit/s step (s)"); ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=8.5); ax.set_title("What-if: hls.js up-switch delay (model, run B schedule)", loc="left", fontsize=10.5)
    fig.tight_layout(); fig.savefig(f"{O}/fig_sim_whatif.png", dpi=160); plt.close(fig)

if __name__ == "__main__":
    fig_run("B", "fig_sim_B.png"); fig_run("C", "fig_sim_C.png"); fig_validate(); fig_whatif()
    print(sorted(os.listdir(O)))
