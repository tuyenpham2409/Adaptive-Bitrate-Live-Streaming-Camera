#!/usr/bin/env python3
"""What-if sweep on the tc schedule of run B: how do hls.js ABR parameters change
the up-switch delay, stalls and number of switches?  (week-4 tuning candidates)"""
import os, sys, itertools
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import abr_sim as m

def run(data, out):
    abr = pd.read_csv(f"{data}/abr_log_B.csv"); tc = pd.read_csv(f"{data}/tc_B.csv")
    tt, lv, sch = m.metrics_real(abr, tc)
    rows = []
    for up, slow in itertools.product([0.7, 0.8, 0.9], [9, 6, 4]):
        r = m.simulate(sch, tt[-1], up_f=up, slow=slow, sync=3)
        s = m.summarise(f"up={up} slow={slow}", r.t, r.level, r.buf, r.lat, r.stalls, sch)
        s.update(up_factor=up, slow_halflife=slow, switches=r.switches, stall_s=round(r.stall_s, 2))
        rows.append(s)
    df = pd.DataFrame(rows)
    df.to_csv(f"{out}/abr_whatif.csv", index=False)
    return df

if __name__ == "__main__":
    here = os.path.dirname(__file__)
    d = run(os.path.join(here, "..", "data", "week3"), os.path.join(here, "..", "results", "week3"))
    print(d[["up_factor", "slow_halflife", "up_to_540_s", "up_to_720_s", "stalls", "switches", "min_buffer_s"]].round(2).to_string(index=False))
