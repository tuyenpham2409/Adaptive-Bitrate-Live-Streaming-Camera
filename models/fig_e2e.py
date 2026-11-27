#!/usr/bin/env python3
"""Figure: end-to-end test of the real web page (hls.js, headless Chrome) with default vs Hybrid ABR."""
import os
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
BLUE, ORANGE, MUTED, GRID, INK, SURF = "#2a78d6", "#eb6834", "#6b7280", "#e5e7eb", "#1f2328", "#fcfcfb"
plt.rcParams.update({"font.size": 10, "axes.facecolor": SURF, "figure.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK,
                     "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": .6})
here = os.path.dirname(__file__); D = os.path.join(here, "..", "data", "week4"); O = os.path.join(here, "..", "results", "week4")
os.makedirs(O, exist_ok=True)
L = {"360p": 0, "540p": 1, "720p": 2}
a = {n: pd.read_csv(f"{D}/e2e_{n}.csv") for n in ("default", "custom")}
steps = [(0, 100000), (20, 5000), (40, 2500), (60, 1200), (80, 700), (100, 1200), (120, 2500), (140, 5000), (160, 100000)]
fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True, gridspec_kw={"height_ratios": [1.3, 1, 1]})
ax[0].step([s for s, _ in steps] + [180], [min(r, 6000) for _, r in steps] + [6000], where="post", color=MUTED, lw=1.8, label="link rate (kbit/s, 'none' drawn as 6000)")
ax[0].legend(frameon=False, fontsize=8.5, loc="upper right"); ax[0].set_ylabel("kbit/s")
ax[0].set_title("End-to-end test: real web page, hls.js default vs Hybrid controller (headless Chrome, 20 s steps)", loc="left", fontsize=10.5)
for n, c, ls in (("default", BLUE, "-"), ("custom", ORANGE, "--")):
    d = a[n]; lab = "hls.js default" if n == "default" else "Hybrid (team)"
    ax[1].step(d.t_s, d.level.map(L), where="post", color=c, lw=2.0, ls=ls, label=lab)
    ax[2].plot(d.t_s, d.buffer_s, color=c, lw=1.5, ls=ls, label=lab)
ax[1].set_yticks([0, 1, 2]); ax[1].set_yticklabels(["360p", "540p", "720p"]); ax[1].set_ylim(-.4, 2.4); ax[1].legend(frameon=False, fontsize=8.5, loc="lower right")
ax[2].set_ylabel("buffer (s)"); ax[2].set_xlabel("time (s)"); ax[2].set_ylim(0, 4)
for x in ax:
    for s, _ in steps: x.axvline(s, color=GRID, lw=.6, zorder=0)
fig.tight_layout(); fig.savefig(f"{O}/fig_e2e_default_vs_custom.png", dpi=160)
for n in a:
    d = a[n][a[n].t_s >= 5]; print(n, "stalls", d.stalls.iloc[-1], "switches", d.switches.iloc[-1], "min buffer", d.buffer_s.min(), "median latency", d.latency_s.median(), "dropped", d.dropped.iloc[-1])
