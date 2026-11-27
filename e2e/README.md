# End-to-end test of the web page without the Pi

Runs the real `web/index.html` (hls.js + `hybrid_abr.js`) in headless Chrome against a synthetic live HLS stream
(3 renditions, fMP4, 1 s segments, same BANDWIDTH values as the Pi) through a rate-limited server.
It checks that the controller integrates with hls.js and compares the default ABR with the Hybrid ABR.
It does NOT replace the measurement on the Pi (different encoder, no Wi-Fi).

    npm pack hls.js@1 && tar xzf hls.js-*.tgz            # gives package/dist/hls.min.js
    ./gen_live.sh /tmp/live &                             # needs ffmpeg with libx264
    python3 serve.py /tmp/live ../web 8099 &              # /__rate?kbps=N sets the link rate
    HLSJS=package/dist/hls.min.js python3 run_e2e.py default ../data/week4/e2e_default.csv 20
    HLSJS=package/dist/hls.min.js python3 run_e2e.py custom  ../data/week4/e2e_custom.csv 20

Needs `pip install playwright` and Google Chrome (path in `run_e2e.py`).
