# Adaptive-Bitrate Live Streaming Camera

Raspberry Pi 4 camera node that streams live video and sound as HLS with three renditions; a web player picks the rendition that fits the viewer's network.
Course project *Multimedia Embedded Systems* (HUST), project #1. Team: Lê Hà Hải Vân (20233886), Phạm Minh Tuyên (20233885), Đỗ Đại Doanh (20233837).

```
USB webcam (MJPEG 720p30 + mic)
   -> FFmpeg: 3 x h264_v4l2m2m (720p 2500k / 540p 1200k / 360p 500k) + AAC 128k
   -> fMP4 HLS, 1 s segments, GOP 30, in RAM (/dev/shm/hls)
   -> Nginx -> browser: hls.js with the team's Hybrid ABR controller (web/hybrid_abr.js)
```

Everything starts at boot (`systemd/abr-hls.service`): video appears about 53 s after power-up. `systemd/abr-health.timer` restarts the service if the playlists stop updating.

## Work packages

| Package | Owner | Code in this repo |
|---|---|---|
| WP1 A/V capture, HW H.264 + AAC encoding | Đỗ Đại Doanh | `scripts/run_abr.sh`, `scripts/capture_check.sh`, `tools/av_sync.py`, `tools/frame_stats.py`, `tools/quality_eval.py`, `tools/make_sync_clip.sh` |
| WP2 multi-rendition HLS segmenting, server, reliability | Phạm Minh Tuyên | `systemd/`, `scripts/monitor.sh`, `scripts/healthcheck.sh`, `tools/stability_report.py`, `tools/viewer_load.py`, `models/multi_viewer_sim.py` |
| WP3 bandwidth-adaptive switching in the web player | Lê Hà Hải Vân | `web/`, `scripts/tc_steps.sh`, `models/abr_sim.py`, `models/abr_custom.py`, `tests/`, `e2e/` |

Who did which part of each week is written in `docs/reports/`. Modelling tools: UML (PlantUML, `models/uml/`), SystemC 2.3.4 (`models/abr_pipeline_v3.cpp`), Python (`models/*.py`).

## Run it on the Pi

    git clone https://github.com/tuyenpham2409/Adaptive-Bitrate-Live-Streaming-Camera.git
    cd Adaptive-Bitrate-Live-Streaming-Camera
    sudo apt install ffmpeg nginx v4l-utils alsa-utils
    ./scripts/run_abr.sh                       # test in a terminal first; SEG=1 GOP=30 for the 1 s setting
    sudo cp web/index.html web/hybrid_abr.js /var/www/html/
    sudo cp systemd/abr-hls.service systemd/abr-health.* /etc/systemd/system/
    sudo systemctl daemon-reload && sudo systemctl enable --now abr-hls abr-health.timer

Open `http://<pi-ip>/` (hls.js default ABR) or `http://<pi-ip>/?abr=custom` (Hybrid). Options: `?sync=3` live-sync segments, `?src=` playlist URL. The page shows level, bandwidth estimate, buffer, latency, stalls and can download its log as CSV.
Device names and the user in the unit file (`g1pi`, Sonix webcam, ALSA card) are those of our board: check `v4l2-ctl --list-devices` and `arecord -l`.

## Tests

| Test | Command | Needs |
|---|---|---|
| Bandwidth steps (none, 5M, 2.5M, 1.2M, 0.7M and back) | `sudo scripts/tc_steps.sh wlan0 60` | Pi |
| Resource log | `scripts/monitor.sh log.csv [seconds]` then `python3 tools/stability_report.py log.csv` | Pi, numpy + pandas on the laptop |
| A/V sync | `tools/make_sync_clip.sh`, record the stream, `python3 tools/av_sync.py rec.mkv` | stream + phone |
| Missing / duplicated frames | `scripts/capture_check.sh` | Pi (stops the service for ~2 min) |
| PSNR / SSIM / VMAF per rendition | `python3 tools/quality_eval.py ref.mkv --encoders h264_v4l2m2m,libx264` | Pi for the HW encoder |
| N viewers | `python3 tools/viewer_load.py http://<pi>/hls/master.m3u8 -n 5 -t 120` | laptop on the same network |
| ABR port JS = Python | `node tests/test_abr_port.js` | node |
| Page in headless Chrome | see `e2e/README.md` | Chrome, playwright |

Step-by-step plan for the Pi: `docs/week4_runbook.md`. Demo script: `docs/DEMO.md`.

## Repository layout

    scripts/   run_abr.sh, tc_steps.sh, monitor.sh, healthcheck.sh, capture_check.sh
    systemd/   abr-hls.service, abr-health.service/.timer
    web/       index.html (player + logger), hybrid_abr.js (ABR controller)
    tools/     measurement and analysis tools (A/V sync, frames, quality, stability, viewers)
    models/    Python models, SystemC model, UML
    tests/ e2e/ data/ results/ docs/reports/
