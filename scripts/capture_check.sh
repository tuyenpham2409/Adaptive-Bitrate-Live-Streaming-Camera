#!/bin/bash
# Week 4 (WP1): check the camera's own frame rate and the dynamic-frame-rate control.
# Stops the stream service (the camera can only be opened once), records 30 s of the raw MJPEG
# stream with exposure_dynamic_framerate = 1 and = 0, then restarts the service.
# Usage: ./capture_check.sh [outdir]      needs: v4l2-utils, ffmpeg, python3-numpy
OUT=${1:-capture_check}; DEV=${VIDEO_DEV:-/dev/video0}; DUR=${DUR:-30}
mkdir -p "$OUT"; here=$(cd "$(dirname "$0")" && pwd)
echo "== camera controls ==" | tee "$OUT/controls.txt"
v4l2-ctl -d "$DEV" --list-ctrls | tee -a "$OUT/controls.txt"
v4l2-ctl -d "$DEV" --list-formats-ext > "$OUT/formats.txt"
sudo systemctl stop abr-hls
for dyn in 1 0; do
  v4l2-ctl -d "$DEV" -c exposure_dynamic_framerate=$dyn 2>/dev/null || echo "control exposure_dynamic_framerate not available"
  echo "== exposure_dynamic_framerate=$dyn : recording ${DUR} s =="
  ffmpeg -hide_banner -loglevel error -y -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i "$DEV" \
         -t "$DUR" -c copy -fps_mode passthrough "$OUT/cap_dyn$dyn.mkv"
  python3 "$here/../tools/frame_stats.py" "$OUT/cap_dyn$dyn.mkv" --fps 30 --csv "$OUT/frames_dyn$dyn.csv" | tee "$OUT/stats_dyn$dyn.txt"
done
v4l2-ctl -d "$DEV" -c exposure_dynamic_framerate=0 2>/dev/null   # keep the fixed rate for the stream
sudo systemctl start abr-hls
echo "Done. Results in $OUT/ (stats_dyn1.txt, stats_dyn0.txt). Cover the lens halfway and repeat for a dim-light test."
