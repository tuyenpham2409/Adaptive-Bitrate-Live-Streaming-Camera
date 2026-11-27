#!/usr/bin/env python3
"""Audio/video synchronisation of a recorded stream (week 4, WP1 capture and encoding).

Two measurements on one recording of the HLS output (e.g.
  ffmpeg -i http://<pi>/hls/master.m3u8 -map 0:v:0 -map 0:a:0 -t 40 -c copy rec.mkv   # 720p variant
 or one rendition: -i http://<pi>/hls/720p/stream.m3u8):

 1. container   start-time offset and duration mismatch between audio and video (from ffprobe).
                Offset > 0: audio starts later than video.  Drift = audio end - video end.
 2. flash-beep  event offset: a clip with simultaneous flash + beep (make_sync_clip.sh) is played
                in front of the camera. Flash = rise of the mean luma, beep = rise of the audio
                level. offset = t_beep - t_flash per event; positive = sound LATE vs picture
                (standard A/V sync convention: > +45 ms or < -125 ms is noticeable, ITU-R BT.1359).

The result contains the delay of the playback device (screen + speaker) in the loop, so compare
runs and renditions with each other and read the absolute value with about +-50 ms uncertainty.

Usage: python3 av_sync.py rec.mkv [--csv events.csv] [--period 2.0]
"""
import argparse, json, re, subprocess, sys
import numpy as np


def run(cmd, binary=False):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        sys.exit("command failed: " + " ".join(cmd) + "\n" + p.stderr.decode(errors="replace")[-500:])
    return p.stdout if binary else p.stdout.decode()


def probe(path):
    j = json.loads(run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=index,codec_type,codec_name,start_time,duration,sample_rate,r_frame_rate:format=duration",
                        "-of", "json", path]))
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next(s for s in j["streams"] if s["codec_type"] == "audio")
    return v, a


def last_pts(path, stream_sel):
    out = run(["ffprobe", "-v", "error", "-select_streams", stream_sel, "-show_entries",
               "packet=pts_time,duration_time", "-of", "csv=p=0", path])
    t = 0.0
    for ln in out.splitlines():
        f = ln.split(",")
        if f[0] not in ("", "N/A"):
            end = float(f[0]) + (float(f[1]) if len(f) > 1 and f[1] not in ("", "N/A") else 0.0)
            t = max(t, end)
    return t


def container(path):
    v, a = probe(path)
    vs, as_ = float(v["start_time"]), float(a["start_time"])
    ve, ae = last_pts(path, "v:0"), last_pts(path, "a:0")
    return dict(video_start_s=vs, audio_start_s=as_, start_offset_ms=(as_ - vs) * 1000.0,
                video_end_s=ve, audio_end_s=ae, end_offset_ms=(ae - ve) * 1000.0,
                drift_ms=((ae - ve) - (as_ - vs)) * 1000.0)


def luma_series(path):
    """(pts_time, mean luma) of every video frame (signalstats YAVG)."""
    txt = run(["ffmpeg", "-v", "error", "-i", path, "-an", "-vf",
               "scale=160:90,signalstats,metadata=mode=print:file=-", "-f", "null", "-"])
    t = []; y = []; cur = None
    for ln in txt.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", ln)
        if m: cur = float(m.group(1)); continue
        m = re.search(r"lavfi\.signalstats\.YAVG=([0-9.]+)", ln)
        if m and cur is not None: t.append(cur); y.append(float(m.group(1)))
    return np.array(t), np.array(y)


def audio_level(path, a_start, win_ms=2.0):
    """(time, RMS) per window of decoded mono 48 kHz audio; time axis starts at the stream start_time."""
    sr = 48000
    raw = run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], binary=True)
    x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    w = int(sr * win_ms / 1000.0); n = len(x) // w
    rms = np.sqrt(np.mean(x[: n * w].reshape(n, w) ** 2, axis=1))
    return a_start + (np.arange(n) * w) / sr, rms


def rising_edges(t, y, min_gap, interpolate):
    """Times where the signal first exceeds the mid level between its median (baseline) and its 99.5th percentile.
    Video (interpolate=False): pts of the first bright frame, resolution one frame (33 ms at 30 fps).
    Audio (interpolate=True): linear interpolation of the crossing between 2 ms windows."""
    lo, hi = np.median(y), np.percentile(y, 99.5)      # baseline and flash/beep level (events last only a few % of the time)
    if hi - lo < 1e-6: return []
    th = (lo + hi) / 2.0
    above = y > th
    idx = np.where(above[1:] & ~above[:-1])[0] + 1
    out = []
    for i in idx:
        # interpolate the crossing between samples i-1 and i
        f = (th - y[i - 1]) / (y[i] - y[i - 1]) if (interpolate and y[i] != y[i - 1]) else 1.0
        te = t[i - 1] + f * (t[i] - t[i - 1])
        if not out or te - out[-1] > min_gap: out.append(te)
    return out


def flash_beep(path, period):
    v, a = probe(path)
    tv, yv = luma_series(path)
    ta, ra = audio_level(path, float(a["start_time"]))
    fl = rising_edges(tv, yv, 0.5 * period, False); bp = rising_edges(ta, ra, 0.5 * period, True)
    ev = []
    for f in fl:
        near = [b for b in bp if abs(b - f) < 0.5 * period]
        if near:
            b = min(near, key=lambda z: abs(z - f))
            ev.append((f, b, (b - f) * 1000.0))
    return ev, len(fl), len(bp)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file"); ap.add_argument("--period", type=float, default=2.0, help="flash period of the clip (s)")
    ap.add_argument("--csv", help="write the per-event offsets here"); ap.add_argument("--no-events", action="store_true")
    a = ap.parse_args()
    c = container(a.file)
    print("container: audio starts %+.1f ms after video, end mismatch %+.1f ms, drift over %.1f s: %+.1f ms"
          % (c["start_offset_ms"], c["end_offset_ms"], c["video_end_s"] - c["video_start_s"], c["drift_ms"]))
    if a.no_events: return
    ev, nf, nb = flash_beep(a.file, a.period)
    print("events: %d flashes, %d beeps, %d paired" % (nf, nb, len(ev)))
    if not ev: sys.exit("no flash/beep pairs found - was the clip in front of the camera and the speaker near the mic?")
    off = np.array([e[2] for e in ev])
    print("flash-beep offset (ms, + = sound late): median %+.1f  mean %+.1f  std %.1f  min %+.1f  max %+.1f"
          % (np.median(off), off.mean(), off.std(), off.min(), off.max()))
    if len(ev) >= 4:
        s = np.polyfit([e[0] for e in ev], off, 1)[0] * 60.0
        print("trend of the offset over time: %+.2f ms per minute" % s)
    ok = np.mean((off > -125) & (off < 45)) * 100.0
    print("events inside the ITU-R BT.1359 detectability window (-125..+45 ms): %.0f %%" % ok)
    if a.csv:
        with open(a.csv, "w") as f:
            f.write("t_flash_s,t_beep_s,offset_ms\n")
            for e in ev: f.write("%.4f,%.4f,%.2f\n" % e)


if __name__ == "__main__":
    main()
