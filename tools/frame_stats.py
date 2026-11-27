#!/usr/bin/env python3
"""Frame timing of a recording: effective frame rate, missing and duplicated frames (week 4, WP1).

Why: the UVC webcam lowers its frame rate in dim light when exposure_dynamic_framerate = 1 (the
driver then delivers fewer frames, FFmpeg fills the gaps by duplicating frames, and the picture
looks jerky). We measure it on the camera's own MJPEG stream, before the encoder, where every
frame is an independent JPEG:

    ffmpeg -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0 \\
           -t 30 -c copy -fps_mode passthrough cap.mkv        (scripts/capture_check.sh does this)

  missing    gap between two timestamps larger than 1.5 frame periods; missing = round(gap*fps) - 1
  duplicated two consecutive packets with identical size and CRC (exact repeat of a frame)
  jitter     standard deviation and 99th percentile of the frame interval

The same tool works on the HLS output (H.264) to check that the encoder keeps 30 fps; duplicates
are then detected only if the encoder emits byte-identical packets (rare).

Usage: python3 frame_stats.py cap.mkv [--fps 30] [--csv per_second.csv]
"""
import argparse, subprocess, sys
import numpy as np


def packets(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0", "-c", "copy",
                        "-f", "framecrc", "-"], capture_output=True, text=True)
    if p.returncode != 0: sys.exit(p.stderr[-500:])
    tb = 1.0; rows = []
    for ln in p.stdout.splitlines():
        if ln.startswith("#tb"):
            n, d = ln.split(":")[1].strip().split("/"); tb = float(n) / float(d)
        elif ln and not ln.startswith("#"):
            f = [x.strip() for x in ln.split(",")]
            rows.append((int(f[2]) * tb, int(f[4]), f[5]))        # pts (s), size, crc
    rows.sort(key=lambda r: r[0])
    return rows


def analyse(rows, fps):
    t = np.array([r[0] for r in rows]); dt = np.diff(t); per = 1.0 / fps
    gaps = dt[dt > 1.5 * per]
    missing = int(sum(round(g * fps) - 1 for g in gaps))
    dup = sum(1 for a, b in zip(rows, rows[1:]) if a[1] == b[1] and a[2] == b[2])
    dur = t[-1] - t[0] + per
    sec = np.floor(t - t[0]).astype(int)
    per_sec = np.bincount(sec)
    res = dict(frames=len(t), duration_s=float(dur), fps_effective=float((len(t) - 1) / (t[-1] - t[0])),
               fps_expected=fps, dt_median_ms=float(np.median(dt) * 1000), dt_std_ms=float(dt.std() * 1000),
               dt_p99_ms=float(np.percentile(dt, 99) * 1000), dt_max_ms=float(dt.max() * 1000),
               gaps=int(len(gaps)), missing_frames=missing, missing_pct=100.0 * missing / (len(t) + missing),
               duplicated=int(dup), duplicated_pct=100.0 * dup / len(t),
               min_fps_in_a_second=int(per_sec[:-1].min()) if len(per_sec) > 1 else len(t))
    return res, per_sec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file"); ap.add_argument("--fps", type=float, default=30.0); ap.add_argument("--csv")
    a = ap.parse_args()
    rows = packets(a.file)
    if len(rows) < 3: sys.exit("too few frames")
    r, per_sec = analyse(rows, a.fps)
    print("%d frames in %.1f s -> %.2f fps (expected %.0f)" % (r["frames"], r["duration_s"], r["fps_effective"], a.fps))
    print("frame interval: median %.1f ms, std %.2f ms, p99 %.1f ms, max %.1f ms"
          % (r["dt_median_ms"], r["dt_std_ms"], r["dt_p99_ms"], r["dt_max_ms"]))
    print("gaps: %d, missing frames: %d (%.2f %%)" % (r["gaps"], r["missing_frames"], r["missing_pct"]))
    print("exact duplicates: %d (%.2f %%)" % (r["duplicated"], r["duplicated_pct"]))
    print("lowest frames in any whole second: %d" % r["min_fps_in_a_second"])
    if a.csv:
        with open(a.csv, "w") as f:
            f.write("second,frames\n")
            for i, n in enumerate(per_sec): f.write("%d,%d\n" % (i, n))


if __name__ == "__main__":
    main()
