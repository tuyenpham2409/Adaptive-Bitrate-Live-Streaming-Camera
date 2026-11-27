#!/usr/bin/env python3
"""Long-run stability report from monitor.sh logs (week 4, WP2 packaging and server).

Reads the CSV written by scripts/monitor.sh (week-3 files with 5 columns work too) and reports:
  duration, sampling gaps (monitor or FFmpeg stopped), FFmpeg CPU, SoC temperature, throttling flags,
  memory trend (free RAM, FFmpeg RSS) as a least-squares slope with a 95 % interval, RAM-disk use
  of the HLS directory (must be flat), viewers (connections) and FFmpeg restarts.
Verdict rules (printed with the numbers so that they can be questioned):
  leak suspected  slope of free RAM or FFmpeg RSS is significant (95 % interval excludes 0) AND the
                  extrapolated change over 24 h exceeds 10 % of total RAM (4 GB) / 100 MB for RSS
  throttling      any non-zero 'throttled' flag (bit 0 under-voltage now, bit 16 under-voltage has
                  occurred, bit 2 throttled, bit 18 throttling has occurred, bit 3 soft temperature limit)

Usage: python3 stability_report.py monitor.csv [--md out.md]
"""
import argparse, sys
import numpy as np
import pandas as pd

BITS = {0: "under-voltage now", 1: "ARM frequency capped now", 2: "throttled now", 3: "soft temperature limit now",
        16: "under-voltage has occurred", 17: "frequency cap has occurred", 18: "throttling has occurred",
        19: "soft temperature limit has occurred"}


def slope(t_h, y):
    """Least-squares slope per hour and its 95 % half-width (normal approximation)."""
    ok = ~np.isnan(y)
    t, y = t_h[ok], y[ok]
    if len(t) < 10 or np.ptp(t) <= 0: return float("nan"), float("nan")
    A = np.vstack([t, np.ones_like(t)]).T
    (b, a), res, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - (a + b * t); n = len(t)
    s2 = float(r @ r) / max(n - 2, 1)
    # successive samples are correlated: use an effective sample size from the lag-1 autocorrelation
    rho = float(np.corrcoef(r[:-1], r[1:])[0, 1]) if n > 3 and r.std() > 0 else 0.0
    neff = max(n * (1 - max(rho, 0)) / (1 + max(rho, 0)), 3)
    se = np.sqrt(s2 / (np.sum((t - t.mean()) ** 2) * (n / neff)))
    return float(b), float(1.96 * se)


def load(path):
    d = pd.read_csv(path)
    t = pd.to_datetime(d["time"], format="%H:%M:%S")
    sec = (t - t.iloc[0]).dt.total_seconds().to_numpy()
    sec = np.where(np.diff(sec, prepend=sec[0]) < -3600, sec + 86400, sec)      # midnight wrap
    sec = np.maximum.accumulate(np.where(np.diff(sec, prepend=sec[0]) < 0, np.nan, sec))
    d["t_s"] = pd.Series(sec).ffill()
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv"); ap.add_argument("--md"); ap.add_argument("--ram-mb", type=float, default=4096.0)
    a = ap.parse_args()
    d = load(a.csv); t = d["t_s"].to_numpy(); th = t / 3600.0
    L = []
    P = lambda s="": (print(s), L.append(s))
    dur = t[-1] - t[0]
    P("samples: %d over %.1f min (%.2f h)" % (len(d), dur / 60, dur / 3600))
    gaps = np.diff(t); big = np.where(gaps > 6)[0]
    P("sampling gaps > 6 s: %d%s" % (len(big), "" if not len(big) else " (longest %.0f s)" % gaps[big].max()))
    miss = d["ffmpeg_cpu_pct_of_one_core"].isna().sum()
    if miss: P("samples without FFmpeg (process missing): %d" % miss)
    c = d["ffmpeg_cpu_pct_of_one_core"].dropna()
    P("FFmpeg CPU (%% of one core): mean %.0f, p95 %.0f, max %.0f" % (c.mean(), c.quantile(.95), c.max()))
    tp = d["temp_c"].dropna()
    P("temperature: mean %.1f, max %.1f C" % (tp.mean(), tp.max()))
    thr = d["throttled"].dropna().astype(str).unique().tolist()
    nz = [x for x in thr if int(x, 16) != 0]
    if nz:
        flags = sorted({BITS.get(b, "bit %d" % b) for x in nz for b in range(32) if int(x, 16) >> b & 1})
        P("THROTTLING FLAGS SEEN: %s -> %s" % (", ".join(nz), "; ".join(flags)))
    else:
        P("throttling: none (0x0 in every sample)")
    verdict = []
    long_enough = dur >= 1800          # a trend from a shorter run cannot be extrapolated to 24 h
    if not long_enough: P("note: run shorter than 30 min -> slopes are printed but no leak verdict is given")
    m = d["mem_avail_mb"].to_numpy(float); b, h = slope(th, m)
    P("free RAM: start %.0f MB, end %.0f MB, min %.0f MB; slope %+.1f MB/h (95%% +-%.1f)" % (m[0], m[-1], np.nanmin(m), b, h))
    if long_enough and not np.isnan(b) and abs(b) > h and b < 0 and -b * 24 > 0.10 * a.ram_mb: verdict.append("free RAM falls %.0f MB/day" % (-b * 24))
    if "ffmpeg_rss_mb" in d and d["ffmpeg_rss_mb"].notna().sum() > 10:
        r = d["ffmpeg_rss_mb"].to_numpy(float); b2, h2 = slope(th, r)
        P("FFmpeg RSS: start %.0f MB, end %.0f MB; slope %+.1f MB/h (95%% +-%.1f)" % (r[~np.isnan(r)][0], r[~np.isnan(r)][-1], b2, h2))
        if long_enough and abs(b2) > h2 and b2 > 0 and b2 * 24 > 100: verdict.append("FFmpeg RSS grows %.0f MB/day" % (b2 * 24))
    if "shm_used_mb" in d and d["shm_used_mb"].notna().sum() > 10:
        s = d["shm_used_mb"].dropna()
        P("HLS RAM disk: min %.0f, max %.0f MB (flat = old segments are deleted)" % (s.min(), s.max()))
    if "nginx_conn" in d:
        P("established connections on port 80: mean %.1f, max %d" % (d["nginx_conn"].mean(), d["nginx_conn"].max()))
    if "restarts" in d and d["restarts"].notna().any():
        r = d["restarts"].dropna().astype(int)
        P("FFmpeg restarts by systemd during the run: %d" % (r.iloc[-1] - r.iloc[0]))
        if r.iloc[-1] > r.iloc[0]: verdict.append("%d FFmpeg restart(s)" % (r.iloc[-1] - r.iloc[0]))
    if nz: verdict.append("throttling/under-voltage flags")
    if len(big): verdict.append("%d sampling gap(s)" % len(big))
    P("VERDICT: " + ("; ".join(verdict) if verdict else ("no leak trend, " if long_enough else "no leak verdict (run too short), ") + ("no restart, " if "restarts" in d else "restarts not logged, ") + "no throttling, no gap in this run"))
    if a.md:
        open(a.md, "w").write("```\n" + "\n".join(L) + "\n```\n")


if __name__ == "__main__":
    main()
