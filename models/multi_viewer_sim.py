#!/usr/bin/env python3
"""Several viewers on one shared uplink (week 4, WP2): how many can the camera serve?

The Pi serves all viewers through one Wi-Fi uplink of capacity C (kbit/s). Viewers that are
downloading a segment at the same moment share C equally (TCP fair share, processor sharing).
Every viewer has the week-3 player model (1 s segments, live-sync 3 segments, stall when the buffer
is empty, resume at 0.5 s) and its own ABR controller instance, either the hls.js default (week 3) or
the team's Hybrid controller (week 4). Viewers join one after another (--stagger).

Reported for the window after the last viewer joined + 30 s:
  avg bitrate  mean real video+audio bitrate of the chosen rendition (kbit/s)
  stalls       number of stall events in the window, summed over viewers (stall_s: seconds)
  switches     rendition changes per viewer per minute
  fairness     Jain index of the viewers' average bitrates (1 = equal, 1/N = one viewer takes all)
  util         delivered data / link capacity

The model is a hypothesis for the 2-5 viewer test on the board (tools/viewer_load.py): it ignores
Wi-Fi contention between separate client devices, TCP slow start and Nginx CPU.

Usage: python3 multi_viewer_sim.py [--out results/week4]
"""
import argparse, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import abr_sim as m
import abr_custom as ac

SEG = m.SEG; TTFB = m.TTFB; REAL = ac.REAL; BW = ac.BW


class Viewer:
    def __init__(self, ctrl, join, sync=3, start_level=0):
        self.ctrl, self.join, self.sync = ctrl, join, sync
        self.level = start_level; self.play = 0.0; self.have = float(sync - 1); self.seg = sync - 1
        self.stalled = False; self.infl = None
        self.levels = []; self.stall_t = []; self.switches = []; self.rx_kbit = 0.0; self.stall_dt = []

    def phase1(self, t, dt):
        tl = t - self.join
        if tl < 0: return
        if self.have - self.play > (0.5 if self.stalled else 1e-9):
            self.play += dt; self.stalled = False
        else:
            if not self.stalled: self.stall_t.append(t); self.stalled = True
            self.stall_dt.append(t)
        if self.infl is None and tl + self.sync * SEG >= self.seg + 1:
            self.infl = dict(left=REAL[self.level] * SEG, ttfb=TTFB, t0=tl, lvl=self.level, xfer=0.0)
        if self.infl is not None and self.infl["ttfb"] > 0: self.infl["ttfb"] -= dt
        self.levels.append((t, self.level))

    def transferring(self):
        return self.infl is not None and self.infl["ttfb"] <= 0

    def phase2(self, t, dt, rate):
        i = self.infl
        if i is None or i["ttfb"] > 0: return
        i["left"] -= rate * dt; i["xfer"] += dt; self.rx_kbit += rate * dt
        if i["left"] <= 0:
            tl = t - self.join
            kbit = REAL[i["lvl"]] * SEG
            d_tot = tl - i["t0"] + dt
            d_xfer = i["xfer"] + i["left"] / max(rate, 1e-9)
            self.have += SEG; self.seg += 1
            new = self.ctrl.on_segment(i["lvl"], kbit, d_tot - TTFB, d_xfer + 0.01, self.have - self.play + ac.BUF_BIAS, tl)
            if new != self.level: self.switches.append(t)
            self.level = new; self.infl = None


def simulate(make_ctrl, n, cap_kbps, t_end=240.0, stagger=3.0, dt=0.05, sync=3):
    vs = [Viewer(make_ctrl(), i * stagger, sync) for i in range(n)]
    t = 0.0
    while t < t_end:
        for v in vs: v.phase1(t, dt)
        act = [v for v in vs if v.transferring()]
        rate = cap_kbps / len(act) if act else 0.0
        for v in act: v.phase2(t, dt, rate)
        t += dt
    return vs


def metrics(vs, cap_kbps, t_end, stagger):
    n = len(vs); t0 = (n - 1) * stagger + 30.0
    avg = []; sw = 0; stalls = 0; stall_s = 0.0; rx = 0.0
    for v in vs:
        lv = np.array([l for (t, l) in v.levels if t >= t0]); avg.append(float(np.mean([REAL[i] for i in lv])))
        sw += sum(1 for s in v.switches if s >= t0)
        stalls += sum(1 for s in v.stall_t if s >= t0); stall_s += 0.05 * sum(1 for s in v.stall_dt if s >= t0)
    a = np.array(avg); jain = float(a.sum() ** 2 / (n * (a ** 2).sum()))
    dur = t_end - t0
    return dict(viewers=n, link_kbps=cap_kbps, avg_bitrate_kbps=float(a.mean()), stalls=stalls, stall_s=round(stall_s, 1),
                switches_per_viewer_min=sw / n / (dur / 60.0), fairness=jain,
                util_pct=100.0 * sum(v.rx_kbit for v in vs) / (cap_kbps * t_end))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="results/week4")
    ap.add_argument("--links", default="6000,10000,20000"); ap.add_argument("--nmax", type=int, default=8)
    ap.add_argument("--t", type=float, default=240.0); ap.add_argument("--stagger", type=float, default=3.0)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    rows = []
    for cap in [float(x) for x in a.links.split(",")]:
        for n in range(1, a.nmax + 1):
            for name, mk in (("hls.js default", lambda: ac.HlsDefault()), ("Hybrid (team)", lambda: ac.Hybrid())):
                vs = simulate(mk, n, cap, a.t, a.stagger)
                r = metrics(vs, cap, a.t, a.stagger); r["controller"] = name; rows.append(r)
                print("C=%5.0f N=%d %-15s avg %5.0f kbit/s  stalls %3d (%5.1f s)  sw/min %.2f  Jain %.3f  util %3.0f%%"
                      % (cap, n, name, r["avg_bitrate_kbps"], r["stalls"], r["stall_s"], r["switches_per_viewer_min"], r["fairness"], r["util_pct"]))
    pd.DataFrame(rows)[["link_kbps", "viewers", "controller", "avg_bitrate_kbps", "stalls", "stall_s",
                        "switches_per_viewer_min", "fairness", "util_pct"]].round(3).to_csv(os.path.join(a.out, "multi_viewer_sim.csv"), index=False)


if __name__ == "__main__":
    main()
