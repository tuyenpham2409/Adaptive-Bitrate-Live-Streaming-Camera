#!/usr/bin/env python3
"""Write test vectors for the JS port: random segment events and the decisions of the Python Hybrid."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import abr_custom as c

def main(out):
    rng = np.random.default_rng(7); cases = []
    for k in range(20):
        h = c.Hybrid(); now = 0.0; level = int(rng.integers(0, 3)); ev = []
        for i in range(200):
            now += float(rng.uniform(0.9, 1.3))
            cap = float(np.exp(rng.uniform(np.log(500), np.log(8000))))      # kbit/s
            kbit = float(c.REAL[level]); dur = kbit / cap + 0.01
            buf = float(rng.uniform(0.2, 3.5))
            new = h.on_segment(level, kbit, dur - 0.01, dur, buf, now)
            ev.append({"level": level, "kbit": kbit, "dur": dur, "buf": buf, "now": now, "out": int(new)})
            level = int(new)
        cases.append({"bw": c.BW, "events": ev})
    json.dump(cases, open(out, "w"))
    print("wrote", out, sum(len(x["events"]) for x in cases), "events")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "tests", "abr_vectors.json"))
