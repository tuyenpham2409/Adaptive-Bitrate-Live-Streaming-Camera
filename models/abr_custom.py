#!/usr/bin/env python3
"""Week 4: design of the team's own ABR controller ("Hybrid") and comparison with the hls.js default.

Why a new controller?  Week-3 measurements and the Python replay of hls.js showed
  (1) up-switch needs about 64 s after the bandwidth is back, because
      - the EWMA weight is the *download time*; fast downloads (high bandwidth) carry little
        weight, so the estimate rises slowly,
      - the estimate is min(fast, slow) with a 9 s slow half-life and the up factor is 0.7;
  (2) an unneeded dip to 360p at the 5 Mbit/s step (fragment-abandon rule).

Hybrid controller (one decision per downloaded segment, ~1 s):
  estimate  per-segment EWMA of the segment throughput (kbit/s): weight per *segment*, not per
            download time; reacts faster downwards (a_down) than upwards (a_up)
  down      pick the highest rendition with m_down * estimate >= BANDWIDTH; may skip levels;
            if the buffer is below buf_emerg also require 0.7 * min(estimate, last sample)
  up        one level at a time, only if m_up * estimate >= BANDWIDTH(next) for n_up consecutive
            segments, the buffer is at least buf_up and the last down-switch is older than hold s
  no fragment abandon (a segment is 1 s, aborting it wastes the data already received)

The same logic is ported to web/index.html (abr=custom); tests/test_abr_port.js checks that both
implementations give the same decisions.

Usage: python3 abr_custom.py [--data DIR] [--out DIR]
"""
import argparse, math, os, sys
from dataclasses import dataclass
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import abr_sim as m

ORDER = m.ORDER
BW = [m.LEVELS[k][0] for k in ORDER]        # master playlist BANDWIDTH, kbit/s
REAL = [m.LEVELS[k][1] for k in ORDER]      # real average bitrate incl. audio, kbit/s


# ------------------------------------------------------------------ controllers
class HlsDefault:
    """The hls.js v1 default as modelled in week 3 (abr_sim.py)."""
    name = "hls.js default"
    def __init__(self, up_f=m.UP_F, slow=m.SLOW_HL):
        self.up_f, self.slow = up_f, slow
        self.est = m.Estimator(slow=slow)
    def on_segment(self, level, kbit, dur_net, dur_total, buf, now):
        self.est.sample(dur_net, kbit)
        return ORDER.index(m.choose(self.est.get(), ORDER[level], m.DOWN_F, self.up_f))

PARAMS = dict(a_down=0.7, a_up=0.35, m_down=0.9, m_up=0.85, n_up=3, buf_up=1.5,
              buf_emerg=1.0, hold=6.0)

class Hybrid:
    name = "Hybrid (team)"
    def __init__(self, **kw):
        self.p = {**PARAMS, **kw}
        self.est = None; self.streak = 0; self.last_down = -1e9
    def _best(self, est, margin):
        t = 0
        for i in range(len(BW)):
            if margin * est >= BW[i]: t = i
        return t
    def on_segment(self, level, kbit, dur_net, dur_total, buf, now):
        p = self.p
        s = kbit / max(dur_total, 0.05)                      # throughput of this segment
        if self.est is None: self.est = s
        else: self.est += (p["a_down"] if s < self.est else p["a_up"]) * (s - self.est)
        cur = level
        target = self._best(self.est, p["m_down"])
        if target < cur:
            if buf < p["buf_emerg"]:
                target = min(target, self._best(min(self.est, s), 0.7))
            self.streak = 0; self.last_down = now
            return target
        ok = (cur < len(BW) - 1 and p["m_up"] * self.est >= BW[cur + 1]
              and buf >= p["buf_up"] and now - self.last_down >= p["hold"])
        self.streak = self.streak + 1 if ok else 0
        if self.streak >= p["n_up"]:
            self.streak = 0
            return cur + 1
        return cur


# ------------------------------------------------------------------ closed loop
@dataclass
class Run:
    t: list; level: list; buf: list; lat: list; stalls: int; stall_s: float; switches: int


BUF_BIAS = 0.5   # the model buffer is about 0.5 s lower than the player's (week 3: 1.95 s vs 2.49 s)

def run(ctrl, sched, t_end, sync=3, dt=0.05, noise=0.0, seed=0, start_level=2):
    """Same player model as abr_sim.simulate, with a pluggable controller and optional noise
    (lognormal factor per segment on the link rate)."""
    rng = np.random.default_rng(seed)
    level = start_level; sw = 0; stalls = 0; stall_s = 0.0
    play = 0.0; have = float(sync - 1); seg = sync - 1; stalled = False; infl = None
    rows = []; t = 0.0
    while t < t_end:
        edge = t + sync * m.SEG
        if have - play > (0.5 if stalled else 1e-9):
            play += dt; stalled = False
        else:
            if not stalled: stalls += 1; stalled = True
            stall_s += dt
        if infl is None and edge >= seg + 1:
            f = float(np.exp(rng.normal(0, noise))) if noise else 1.0
            infl = {"left": REAL[level] * m.SEG, "ttfb": m.TTFB, "t0": t, "lvl": level, "f": f, "xfer": 0.0, "rate": 1.0}
        if infl is not None:
            if infl["ttfb"] > 0: infl["ttfb"] -= dt
            else:
                infl["rate"] = m.capacity(sched, t) * infl["f"]
                infl["left"] -= infl["rate"] * dt; infl["xfer"] += dt
            if infl["left"] <= 0:
                kbit = REAL[infl["lvl"]] * m.SEG
                d_tot = t - infl["t0"] + dt
                d_xfer = infl["xfer"] + infl["left"] / infl["rate"]        # exact transfer time (left <= 0)
                have += m.SEG; seg += 1
                # Hybrid sees the exact segment time + 10 ms LAN request latency (the browser logs
                # end - start); the hls.js model keeps the week-3 input so that it is unchanged
                new = ctrl.on_segment(infl["lvl"], kbit, d_tot - m.TTFB, d_xfer + 0.01, have - play + BUF_BIAS, t)
                if new != level: sw += 1
                level = new; infl = None
        rows.append((t, level, have - play, edge - play))
        t += dt
    a = list(zip(*rows))
    return Run(list(a[0]), list(a[1]), list(a[2]), list(a[3]), stalls, stall_s, sw)


# ------------------------------------------------------------------ scenarios
def sched_B(data):
    abr = pd.read_csv(f"{data}/abr_log_B.csv"); tc = pd.read_csv(f"{data}/tc_B.csv")
    tt, lv, sch = m.metrics_real(abr, tc)
    return sch, tt[-1]

def sched_random_walk(seed, dur=300.0, step=5.0):
    rng = np.random.default_rng(100 + seed); x = math.log(2500.0); out = []
    for k in range(int(dur / step)):
        x = float(np.clip(x + rng.normal(0, 0.55) + 0.1 * (math.log(2500) - x), math.log(900), math.log(6000)))
        out.append((k * step, math.exp(x) / m.LINK_EFF))     # capacity() multiplies by LINK_EFF
    return out, dur

def sched_dips(dur=240.0):
    out = [(0.0, 5000.0)]
    for k in range(5, int(dur), 40):
        out += [(float(k), 700.0), (float(k + 3), 5000.0)]
    return out, dur


def summarise(r, name, scen, sch=None):
    lv = np.array(r.level); n = len(lv)
    d = dict(scenario=scen, controller=name, avg_bitrate_kbps=float(np.mean([REAL[i] for i in lv])),
             pct_720p=100.0 * float(np.mean(lv == 2)), pct_360p=100.0 * float(np.mean(lv == 0)),
             switches_per_min=r.switches / (n * 0.05 / 60.0), stalls=r.stalls, stall_s=round(r.stall_s, 2),
             min_buffer_s=float(np.min(r.buf)))
    if sch is not None:
        t = np.array(r.t)
        def first(tfrom, target):
            idx = np.where((t >= tfrom) & (lv >= target))[0]
            return float(t[idx[0]] - tfrom) if len(idx) else float("nan")
        d["down_to_540_s"] = float(t[np.where((t >= m.step_times(sch, 2500)[0]) & (lv <= 1))[0][0]] - m.step_times(sch, 2500)[0])
        d["up_to_540_s"] = first(m.step_times(sch, 2500)[1], 1)
        d["up_to_720_s"] = first(m.step_times(sch, 5000)[1], 2)
    return d


def evaluate(data):
    rows = []
    sch, T = sched_B(data)
    for mk in (lambda: HlsDefault(), lambda: Hybrid()):
        c = mk(); r = run(c, sch, T); rows.append(summarise(r, c.name, "B schedule (deterministic)", sch))
    for scen, gen, seeds, noise in [("B schedule + noise 10%", lambda s: (sch, T), range(10), 0.10),
                                    ("random walk 0.9-6 Mbit/s", sched_random_walk, range(10), 0.15),
                                    ("short 3 s dips to 0.7 Mbit/s", lambda s: sched_dips(), range(10), 0.15)]:
        for mk in (lambda: HlsDefault(), lambda: Hybrid()):
            ds = []
            for s in seeds:
                sc, tt = gen(s); c = mk(); ds.append(summarise(run(c, sc, tt, noise=noise, seed=s), c.name, scen))
            df = pd.DataFrame(ds); agg = {"scenario": scen, "controller": c.name}
            for k in df.columns[2:]: agg[k] = float(df[k].mean())
            agg["stalls"] = float(df["stalls"].sum()); agg["runs"] = len(ds)
            rows.append(agg)
    return pd.DataFrame(rows)


def sensitivity(data):
    sch, T = sched_B(data); rows = []
    base = PARAMS
    grid = [("base", {})] + [(f"n_up={v}", {"n_up": v}) for v in (1, 2, 5)] + \
           [(f"m_up={v}", {"m_up": v}) for v in (0.75, 0.95)] + [(f"hold={v}", {"hold": v}) for v in (0, 12)] + \
           [(f"a_up={v}", {"a_up": v}) for v in (0.2, 0.6)]
    for name, kw in grid:
        agg = []
        for scen, gen, noise in [("rw", sched_random_walk, 0.15), ("dips", lambda s: sched_dips(), 0.15)]:
            for s in range(10):
                sc, tt = gen(s); r = run(Hybrid(**kw), sc, tt, noise=noise, seed=s)
                agg.append(summarise(r, name, scen))
        df = pd.DataFrame(agg)
        r0 = run(Hybrid(**kw), sch, T)
        s0 = summarise(r0, name, "B", sch)
        rows.append(dict(variant=name, up_to_720_B_s=s0["up_to_720_s"], stalls_B=s0["stalls"],
                         avg_bitrate_kbps=df.avg_bitrate_kbps.mean(), switches_per_min=df.switches_per_min.mean(),
                         stalls_total=int(df.stalls.sum()), stall_s_total=df.stall_s.sum()))
    return pd.DataFrame(rows)


def main():
    here = os.path.dirname(__file__)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(here, "..", "data", "week3"))
    ap.add_argument("--out", default=os.path.join(here, "..", "results", "week4"))
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    # consistency: the generic loop with the hls.js model must reproduce week-3 abr_sim.simulate
    sch, T = sched_B(a.data)
    r1 = run(HlsDefault(), sch, T); r2 = m.simulate(sch, T)
    same = sum(ORDER[x] != y for x, y in zip(r1.level, r2.level))
    print(f"consistency check vs abr_sim.simulate: {same} differing samples of {len(r1.level)}")
    ev = evaluate(a.data); ev.to_csv(f"{a.out}/abr_custom_vs_default.csv", index=False)
    print(ev.round(2).to_string(index=False))
    se = sensitivity(a.data); se.to_csv(f"{a.out}/abr_custom_sensitivity.csv", index=False)
    print(se.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
