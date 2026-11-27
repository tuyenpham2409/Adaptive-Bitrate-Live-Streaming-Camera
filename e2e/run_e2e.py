#!/usr/bin/env python3
"""python3 run_e2e.py <default|custom> <out.csv> [step_s]  - drives the real web page in headless Chrome
through the tc-like steps (none,5M,2.5M,1.2M,0.7M,1.2M,2.5M,5M,none) and saves the page's own CSV log."""
import sys, time, json, urllib.request
from playwright.sync_api import sync_playwright
mode, out = sys.argv[1], sys.argv[2]; step = float(sys.argv[3]) if len(sys.argv) > 3 else 20
RATES = [100000, 5000, 2500, 1200, 700, 1200, 2500, 5000, 100000]
import os
HLSJS = open(os.environ.get("HLSJS", "hls.min.js")).read()   # get it with: npm pack hls.js@1  (package/dist/hls.min.js)
rate = lambda k: urllib.request.urlopen(f"http://127.0.0.1:8099/__rate?kbps={k*0.95}").read()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
                          args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
    pg.route("**/hls.min.js", lambda r: r.fulfill(body=HLSJS, content_type="application/javascript"))
    rate(100000)
    pg.goto(f"http://127.0.0.1:8099/index.html?abr={mode}")
    time.sleep(step)                                    # phase 0: no limit
    t0 = time.time()
    for k in RATES[1:]:
        rate(k); time.sleep(step)
    rows = pg.evaluate("log"); rate(100000)
    cols = list(rows[0].keys())
    open(out, "w").write("\n".join([",".join(cols)] + [",".join(str(r[c]) for c in cols) for r in rows]))
    print(mode, "rows", len(rows), "errors:", errs[:5])
    b.close()
