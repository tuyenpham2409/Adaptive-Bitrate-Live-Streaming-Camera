#!/usr/bin/env python3
"""Objective quality of the three renditions (PSNR, SSIM, VMAF if available) - week 4, WP1.

Each rendition of the ladder is encoded from the same reference clip with the same settings as the
streaming pipeline (GOP 30, no B-frames, constant target bitrate), decoded, scaled back to 1280x720
and compared with the reference, i.e. the quality a viewer sees on a 720p screen.

  reference   a recording of the camera's MJPEG stream (capture_check.sh makes one), 10-30 s
  encoders    h264_v4l2m2m (Pi hardware encoder, what the product uses) and libx264 (software,
              preset veryfast, as a yardstick: the slides say HW encoders have lower R-D efficiency)

Usage: python3 quality_eval.py ref.mkv --encoders h264_v4l2m2m,libx264 --out results/week4/quality.csv
"""
import argparse, json, os, re, subprocess, sys, tempfile, time

LADDER = [(1280, 720, 2500), (960, 540, 1200), (640, 360, 500)]


def ff(args, **kw):
    return subprocess.run(["ffmpeg", "-hide_banner", "-y"] + args, capture_output=True, text=True, **kw)


def has_filter(name):
    return name in subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout


def encode(ref, enc, w, h, kbps, seconds, out):
    opts = ["-c:v", enc, "-b:v", f"{kbps}k", "-g", "30", "-keyint_min", "30", "-bf", "0"]
    if enc == "libx264": opts += ["-preset", "veryfast", "-tune", "zerolatency", "-x264-params", "scenecut=0"]
    t0 = time.time()
    r = ff(["-i", ref, "-t", str(seconds), "-vf", f"scale={w}:{h}:flags=bicubic,format=yuv420p", "-r", "30", "-an"] + opts + [out])
    if r.returncode != 0: return None, r.stderr[-300:]
    return time.time() - t0, ""


def compare(ref, enc_file, seconds, metric, tmp):
    base = ("[0:v]scale=1280:720:flags=bicubic,format=yuv420p,setpts=PTS-STARTPTS[d];"
            "[1:v]scale=1280:720:flags=bicubic,format=yuv420p,setpts=PTS-STARTPTS,trim=duration=%s[r];" % seconds)
    if metric == "psnr":   fg, pat = base + "[d][r]psnr", r"PSNR y:\S+ u:\S+ v:\S+ average:([0-9.inf]+)"
    elif metric == "ssim": fg, pat = base + "[d][r]ssim", r"SSIM Y:\S+ \S+ U:\S+ \S+ V:\S+ \S+ All:([0-9.]+)"
    else:
        log = os.path.join(tmp, "vmaf.json")
        fg = base + f"[d][r]libvmaf=log_fmt=json:log_path={log}"; pat = None
    r = ff(["-i", enc_file, "-i", ref, "-t", str(seconds), "-filter_complex", fg, "-f", "null", "-"])
    if metric == "vmaf":
        try: return json.load(open(log))["pooled_metrics"]["vmaf"]["mean"]
        except Exception: return float("nan")
    m = re.search(pat, r.stderr)
    return float(m.group(1)) if m else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref"); ap.add_argument("--encoders", default="libx264"); ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--out", default="quality.csv")
    a = ap.parse_args()
    metrics = ["psnr", "ssim"] + (["vmaf"] if has_filter("libvmaf") else [])
    if "vmaf" not in metrics: print("note: this ffmpeg has no libvmaf filter -> PSNR and SSIM only (VMAF is skipped, not estimated)")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for enc in a.encoders.split(","):
            for (w, h, kb) in LADDER:
                f = os.path.join(tmp, f"{enc}_{h}.mp4")
                el, err = encode(a.ref, enc, w, h, kb, a.seconds, f)
                if el is None: print(f"skip {enc} {h}p: encoder failed: {err.strip()[-120:]}"); continue
                real = os.path.getsize(f) * 8 / a.seconds / 1000.0
                row = dict(encoder=enc, rendition=f"{h}p", target_kbps=kb, actual_kbps=round(real), encode_speed_x=round(a.seconds / el, 2))
                for m in metrics: row[m] = round(compare(a.ref, f, a.seconds, m, tmp), 4)
                rows.append(row); print(row)
    if rows:
        with open(a.out, "w") as f:
            keys = list(rows[0].keys()); f.write(",".join(keys) + "\n")
            for r in rows: f.write(",".join(str(r[k]) for k in keys) + "\n")
        print("saved", a.out)


if __name__ == "__main__":
    main()
