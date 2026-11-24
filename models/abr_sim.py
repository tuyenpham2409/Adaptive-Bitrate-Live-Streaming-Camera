#!/usr/bin/env python3
"""ABR simulation of the hls.js controller used in the streaming camera (week 3).

Model of hls.js v1 (abr-controller.ts / ewma-bandwidth-estimator.ts):
  * two EWMAs of per-segment throughput, half-life 3 s (fast) and 9 s (slow),
    weight = segment download time in seconds, estimate = min(fast, slow)
  * level choice (live): highest level with  factor * estimate >= BANDWIDTH
    factor = 0.95 when not above the last loaded level, 0.7 when switching up
  * if no level fits, fall back to the lowest level
Not modelled: fragment-abandon rules, TTFB estimate, playbackRate catch-up.

Two modes
  validate : replay the *measured* per-segment throughput of a real run through
             the estimator and compare with the est_kbps the browser logged.
  simulate : closed loop. The link follows the tc schedule, the player downloads
             1 s segments, keeps a buffer and picks levels with the model above.

Usage:  python3 abr_sim.py [--data DIR] [--out DIR]
"""
import argparse, math, os
from dataclasses import dataclass
import numpy as np
import pandas as pd

# master.m3u8 BANDWIDTH (kbit/s) and real average bitrate incl. audio (kbit/s)
LEVELS = {"360p": (691, 628), "540p": (1461, 1328), "720p": (2891, 2628)}
ORDER = ["360p", "540p", "720p"]
SEG_OF = {"A": 2.0, "B": 1.0, "C": 1.0}      # segment length per tested config
SYNC_OF = {"A": 3, "B": 3, "C": 2}           # liveSyncDurationCount per tested config
SEG = 1.0                       # segment duration (s)
FAST_HL, SLOW_HL = 3.0, 9.0     # abrEwmaFastLive / abrEwmaSlowLive
DOWN_F, UP_F = 0.95, 0.7        # abrBandWidthFactor / abrBandWidthUpFactor
SYNC = 3                        # liveSyncDurationCount
FREE_KBPS = 20000               # throughput measured with no limit (Wi-Fi)
LINK_EFF = 0.95                 # tc tbf: measured segment rate ~0.95 x limit
TTFB = 0.03                     # request overhead per segment (s)


class EWMA:
    def __init__(self, hl):
        self.a = math.exp(math.log(0.5) / hl); self.e = 0.0; self.w = 0.0
    def sample(self, w, v):
        k = self.a ** w; self.e = v * (1 - k) + k * self.e; self.w += w
    def get(self):
        z = 1 - self.a ** self.w
        return self.e / z if z else self.e


class Estimator:
    def __init__(self, fast=FAST_HL, slow=SLOW_HL):
        self.f, self.s = EWMA(fast), EWMA(slow)
    def sample(self, dur_s, kbit):
        dur_s = max(dur_s, 0.05)
        self.f.sample(dur_s, kbit / dur_s); self.s.sample(dur_s, kbit / dur_s)
    def get(self):
        return min(self.f.get(), self.s.get()) if self.f.w > 0 else 500.0


def choose(est, base, down_f=DOWN_F, up_f=UP_F):
    bi = ORDER.index(base)
    for i in range(len(ORDER) - 1, -1, -1):
        f = up_f if i > bi else down_f
        if f * est >= LEVELS[ORDER[i]][0]:
            return ORDER[i]
    return ORDER[0]


# ----------------------------------------------------------------- validate
def validate(abr, seg=SEG):
    """Replay measured frag_kbps; return log-ratio stats model/browser.
    seg = segment length of that run (A used 2 s, B and C 1 s)."""
    est = Estimator(); out = []; prev = None
    for _, r in abr.iterrows():
        if r.frag_kbps > 0 and r.frag_kbps != prev:
            kbit = LEVELS[r.level][1] * seg
            est.sample(kbit / r.frag_kbps, kbit); prev = r.frag_kbps
        out.append(est.get() if est.f.w > 0 else np.nan)
    m = np.array(out); ok = ~np.isnan(m)
    lr = np.log(m[ok] / abr.est_kbps.values[ok])
    return {"n": int(ok.sum()), "median_abs_pct": 100 * (np.exp(np.median(np.abs(lr))) - 1),
            "p90_abs_pct": 100 * (np.exp(np.quantile(np.abs(lr), .9)) - 1),
            "bias_pct": 100 * (np.exp(lr.mean()) - 1)}, m


# ----------------------------------------------------------------- simulate
def parse_rate(s):
    if s == "none": return FREE_KBPS
    return float(s.replace("mbit", "")) * 1000 if s.endswith("mbit") else float(s.replace("kbit", ""))


def schedule(tc):
    sec = lambda c: sum(int(x) * m for x, m in zip(c.split(":"), (3600, 60, 1)))
    t0 = sec(tc.clock.iloc[0])
    return [(sec(c) - t0, parse_rate(r)) for c, r in zip(tc.clock, tc.rate)]


def capacity(sched, t):
    cap = sched[0][1]
    for ts, r in sched:
        if t >= ts: cap = r
    return cap if cap >= FREE_KBPS else cap * LINK_EFF


@dataclass
class Result:
    t: list; level: list; est: list; buf: list; lat: list
    stalls: int; stall_s: float; switches: int


def simulate(sched, t_end, down_f=DOWN_F, up_f=UP_F, fast=FAST_HL, slow=SLOW_HL,
             sync=SYNC, dt=0.05, start_level="720p"):
    """Closed loop. Media time axis: live edge E(t) = t + sync*SEG, segment k covers
    [k, k+1) and is published when E(t) >= k+1. The player starts `sync` segments
    behind the edge (2 segments buffered), downloads sequentially at the link rate,
    plays at 1x and stalls when the buffer is empty."""
    est = Estimator(fast, slow)
    level = start_level; sw = 0; stalls = 0; stall_s = 0.0
    play = 0.0; have = float(sync - 1); seg = sync - 1      # next segment index to fetch
    stalled = False; inflight = None; rows = []
    t = 0.0
    while t < t_end:
        edge = t + sync * SEG
        # playback
        if have - play > (0.5 if stalled else 1e-9):
            play += dt; stalled = False
        else:
            if not stalled: stalls += 1; stalled = True
            stall_s += dt
        # download
        if inflight is None and edge >= seg + 1:
            inflight = {"left": LEVELS[level][1] * SEG, "ttfb": TTFB, "t0": t, "lvl": level}
        if inflight is not None:
            if inflight["ttfb"] > 0:
                inflight["ttfb"] -= dt
            else:
                inflight["left"] -= capacity(sched, t) * dt
            if inflight["left"] <= 0:
                kbit = LEVELS[inflight["lvl"]][1] * SEG
                est.sample(t - inflight["t0"] + dt - TTFB, kbit)
                have += SEG; seg += 1
                new = choose(est.get(), inflight["lvl"], down_f, up_f)
                if new != level: sw += 1
                level = new; inflight = None
        rows.append((t, level, est.get(), have - play, edge - play))
        t += dt
    a = list(zip(*rows))
    return Result(list(a[0]), list(a[1]), list(a[2]), list(a[3]), list(a[4]), stalls, stall_s, sw)


# ----------------------------------------------------------------- metrics
def first_switch(times, levels, t_from, target):
    for t, l in zip(times, levels):
        if t >= t_from and l == target: return t - t_from
    return float("nan")


def metrics_real(abr, tc):
    sched = schedule(tc)
    sec = lambda c: sum(int(x) * m for x, m in zip(c.split(":"), (3600, 60, 1)))
    t0 = sec(abr.clock.iloc[0]); tt = [sec(c) - t0 for c in abr.clock]
    tc0 = sec(tc.clock.iloc[0]) - t0
    sch = [(s + tc0, r) for s, r in sched]
    return tt, abr.level.tolist(), sch


def step_times(sch, rate):
    return [ts for ts, r in sch if abs(r - rate) < 1]


def summarise(name, times, levels, buf, lat, stalls, sch):
    s25 = step_times(sch, 2500)[0]; s12 = step_times(sch, 1200)[0]
    up540 = step_times(sch, 2500)[1]; up720 = step_times(sch, 5000)[1]
    return {"config": name,
            "down_to_540_s": first_switch(times, levels, s25, "540p"),
            "down_to_360_s": first_switch(times, levels, s12, "360p"),
            "up_to_540_s": first_switch(times, levels, up540, "540p"),
            "up_to_720_s": first_switch(times, levels, up720, "720p"),
            "stalls": stalls, "min_buffer_s": float(np.nanmin(buf)),
            "median_latency_s": float(np.nanmedian(lat))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "..", "data", "week3"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "results", "week3"))
    args = ap.parse_args(); os.makedirs(args.out, exist_ok=True)

    print("== validate estimator against logged est_kbps ==")
    stats = {}
    for n in "ABC":
        abr = pd.read_csv(f"{args.data}/abr_log_{n}.csv")
        st, _ = validate(abr, SEG_OF[n]); stats[n] = st
        print(f"config {n}: n={st['n']} median |err|={st['median_abs_pct']:.1f}% "
              f"p90={st['p90_abs_pct']:.1f}% bias={st['bias_pct']:+.1f}%")
    pd.DataFrame(stats).T.to_csv(f"{args.out}/abr_sim_validation.csv")

    print("== closed loop vs measurement ==")
    rows = []
    sims = {}
    for n in "BC":
        abr = pd.read_csv(f"{args.data}/abr_log_{n}.csv"); tc = pd.read_csv(f"{args.data}/tc_{n}.csv")
        tt, lv, sch = metrics_real(abr, tc)
        stalls_real = int(abr.stalls.iloc[-1])
        rows.append(summarise(f"{n} measured", tt, lv, abr.buffer_s.values, abr.latency_s.values, stalls_real, sch))
        # simulation starts at the same instant as the log; the tc schedule is shifted accordingly
        sim = simulate([(s, r) for s, r in sch], tt[-1], sync=SYNC_OF[n])
        sims[n] = (sim, sch)
        rows.append(summarise(f"{n} simulated", sim.t, sim.level, sim.buf, sim.lat, sim.stalls, sch))
    df = pd.DataFrame(rows); print(df.round(2).to_string(index=False))
    df.to_csv(f"{args.out}/abr_sim_vs_measured.csv", index=False)
    return stats, sims, df


if __name__ == "__main__":
    main()
