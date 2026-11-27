#!/usr/bin/env python3
"""Self-test of the week-4 measurement tools on synthetic streams with known answers (no board needed).
    python3 tests/test_tools.py [--quick]        needs ffmpeg + libx264, numpy, pandas; about 1.5 min
Writes data/week4/tools_validation.csv (one row per check) and exits 1 if a check fails."""
import csv, os, subprocess, sys, tempfile, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools"); rows = []; fails = 0


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, shell=isinstance(cmd, str), **kw)
    if r.returncode != 0: raise RuntimeError(cmd if isinstance(cmd, str) else " ".join(cmd) + "\n" + r.stderr[-400:])
    return r.stdout


def check(tool, name, expected, measured, tol):
    global fails
    ok = abs(measured - expected) <= tol; fails += (not ok)
    rows.append(dict(tool=tool, check=name, expected=expected, measured=round(measured, 2), tolerance=tol, result="PASS" if ok else "FAIL"))
    print("%-4s %-14s %-34s expected %8.1f measured %8.1f (tol %.1f)" % ("PASS" if ok else "FAIL", tool, name, expected, measured, tol))


def ff(*a): sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + list(a))


def main():
    quick = "--quick" in sys.argv
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        # --- av_sync: flash+beep clip, audio delayed by a known amount, through fMP4 HLS and back to a recording
        sh([os.path.join(TOOLS, "make_sync_clip.sh"), "clip.mp4", "20"])
        for nominal in ([-100, 0, 100] if quick else [-200, -100, 0, 100, 250]):
            f = "adelay=%d:all=1" % nominal if nominal >= 0 else "atrim=start=%.3f,asetpts=PTS-STARTPTS" % (-nominal / 1000)
            os.makedirs("h", exist_ok=True)
            ff("-i", "clip.mp4", "-af", f, "-c:v", "libx264", "-preset", "veryfast", "-g", "30", "-bf", "0", "-b:v", "2500k", "-c:a", "aac", "-b:a", "128k",
               "-f", "hls", "-hls_time", "1", "-hls_list_size", "0", "-hls_segment_type", "fmp4", "-hls_playlist_type", "vod",
               "-hls_segment_filename", "h/s%d.m4s", "h/p.m3u8")
            ff("-i", "h/p.m3u8", "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "rec.mkv")
            out = sh([sys.executable, os.path.join(TOOLS, "av_sync.py"), "rec.mkv"])
            med = float(out.split("median")[1].split()[0]); check("av_sync.py", "audio delayed %+d ms" % nominal, nominal, med, 10.0)
        # --- frame_stats: 10 s MJPEG with 13 frames removed in 3 gaps, and one with every frame sent twice
        ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30", "-t", "10", "-vf", "select='not(between(n,60,69)+between(n,150,151)+eq(n,200))'",
           "-c:v", "mjpeg", "-q:v", "3", "-fps_mode", "passthrough", "g.mkv")
        ff("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15", "-t", "10", "-r", "30", "-fps_mode", "cfr", "-c:v", "mjpeg", "-q:v", "3", "u.mkv")
        sys.path.insert(0, TOOLS); import frame_stats as fsm
        rg, _ = fsm.analyse(fsm.packets("g.mkv"), 30.0); ru, _ = fsm.analyse(fsm.packets("u.mkv"), 30.0)
        check("frame_stats.py", "frames removed (3 gaps)", 13, rg["missing_frames"], 0); check("frame_stats.py", "number of gaps", 3, rg["gaps"], 0)
        check("frame_stats.py", "duplicated frames (15->30 fps)", 150, ru["duplicated"], 0)
        # --- stability_report: 1 h log, healthy and with a 60 MB/h leak
        import stability_report as sr, pandas as pd
        rng = np.random.default_rng(1); t0 = dt.datetime(2026, 1, 1, 10)
        for leak in (0, 60):
            with open("m.csv", "w") as f:
                f.write("time,ffmpeg_cpu_pct_of_one_core,temp_c,throttled,mem_avail_mb,ffmpeg_rss_mb\n")
                for k in range(1800):
                    h = 2 * k / 3600
                    f.write("%s,%d,50,0x0,%d,%d\n" % ((t0 + dt.timedelta(seconds=2 * k)).strftime("%H:%M:%S"), rng.normal(210, 15), 3500 - leak * h + rng.normal(0, 6), 300 + leak * h + rng.normal(0, 2)))
            dd = sr.load("m.csv"); b, h95 = sr.slope(dd["t_s"].to_numpy() / 3600.0, dd["mem_avail_mb"].to_numpy(float))
            check("stability_report.py", "free-RAM slope MB/h, leak %d" % leak, -leak, b, max(3.0, h95))
    os.chdir(ROOT)
    out = os.path.join(ROOT, "data", "week4", "tools_validation.csv"); os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("%d checks, %d failed -> %s" % (len(rows), fails, out)); sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
