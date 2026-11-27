#!/usr/bin/env python3
"""N simulated HLS viewers against the camera (week 4, WP2 packaging and server).

Each viewer is a thread that behaves like a live player at the HTTP level: it reads master.m3u8,
polls the media playlist, downloads every new fMP4 segment as soon as it is listed (init segment
once per rendition) and chooses the rendition from its own measured throughput. It does not decode.
All viewers share the Pi's Wi-Fi uplink and Nginx, which is what we want to load.

  late segment   download time longer than the segment duration: that viewer cannot keep up
  A viewer that is late for many segments in a row would stall in a real player.

Run it from a laptop on the same network while  scripts/monitor.sh  runs on the Pi:
    python3 viewer_load.py http://<pi>/hls/master.m3u8 -n 5 -t 120 --stagger 3 --csv viewers_n5.csv
Options:  --level 720p   every viewer stays on one rendition (worst-case load)
          --policy abr   (default) pick the highest rendition with 0.8 * throughput >= BANDWIDTH
"""
import argparse, csv, re, threading, time, sys, statistics
import http.client
from urllib.parse import urlparse, urljoin


class Conn:
    def __init__(self, url):
        u = urlparse(url); self.host, self.port = u.hostname, u.port or 80; self.c = None
    def get(self, url):
        p = urlparse(url); path = p.path + ("?" + p.query if p.query else "")
        for attempt in (0, 1):
            try:
                if self.c is None: self.c = http.client.HTTPConnection(self.host, self.port, timeout=15)
                self.c.request("GET", path, headers={"Connection": "keep-alive"})
                r = self.c.getresponse(); body = r.read()
                return r.status, body
            except Exception:
                try: self.c.close()
                except Exception: pass
                self.c = None
                if attempt: return 0, b""


def parse_master(txt, base):
    out = []; lines = txt.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("#EXT-X-STREAM-INF"):
            bw = int(re.search(r"BANDWIDTH=(\d+)", ln).group(1)) / 1000.0
            out.append((bw, urljoin(base, lines[i + 1])))
    return sorted(out)


def parse_media(txt, base):
    seq = int(re.search(r"#EXT-X-MEDIA-SEQUENCE:(\d+)", txt).group(1))
    init = re.search(r'#EXT-X-MAP:URI="([^"]+)"', txt)
    segs = []; dur = None
    for ln in txt.splitlines():
        if ln.startswith("#EXTINF"): dur = float(ln.split(":")[1].split(",")[0])
        elif ln and not ln.startswith("#"): segs.append((seq + len(segs), urljoin(base, ln), dur))
    return (urljoin(base, init.group(1)) if init else None), segs


def viewer(vid, url, t_end, level, policy, rows, lock):
    cn = Conn(url)
    st, body = cn.get(url)
    if st != 200:
        with lock: rows.append((vid, time.time(), "master", 0, 0.0, 0.0, st, 0)); return
    variants = parse_master(body.decode(), url); names = {}
    cur = len(variants) - 1 if level is None else next((i for i, v in enumerate(variants) if level in v[1]), len(variants) - 1)
    est = None; last = None; have_init = set()     # last = newest segment number fetched (same numbering in all renditions)
    while time.time() < t_end:
        mpl = variants[cur][1]
        t0 = time.time(); st, body = cn.get(mpl); dt = time.time() - t0
        if st != 200:
            with lock: rows.append((vid, time.time(), "playlist", cur, 0, dt, st, 0))
            time.sleep(1); continue
        init, segs = parse_media(body.decode(), mpl)
        if init and init not in have_init:
            st, b = cn.get(init); have_init.add(init)
        new = [s for s in segs if last is None or s[0] > last]
        if last is None and new: new = new[-1:]                  # a joining viewer starts at the live edge
        if not new: time.sleep(0.25); continue
        for seq, surl, dur in new:
            t0 = time.time(); st, b = cn.get(surl); d = time.time() - t0
            kbps = len(b) * 8 / 1000.0 / max(d, 1e-3)
            late = int(d > (dur or 1.0))
            last = seq
            with lock: rows.append((vid, time.time(), variants[cur][1].split("/")[-2], cur, len(b), d, st, late))
            if st == 200 and policy == "abr" and level is None:
                est = kbps if est is None else 0.5 * est + 0.5 * kbps
                tgt = max([i for i, v in enumerate(variants) if 0.8 * est >= v[0]] or [0])
                if tgt != cur: cur = tgt; break
            if time.time() >= t_end: break


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url"); ap.add_argument("-n", type=int, default=3); ap.add_argument("-t", type=float, default=60)
    ap.add_argument("--stagger", type=float, default=2.0); ap.add_argument("--level"); ap.add_argument("--policy", default="abr")
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = []; lock = threading.Lock(); t0 = time.time(); th = []
    for i in range(a.n):
        t = threading.Thread(target=viewer, args=(i + 1, a.url, t0 + a.t, a.level, a.policy, rows, lock), daemon=True)
        t.start(); th.append(t); time.sleep(a.stagger if i < a.n - 1 else 0)
    for t in th: t.join(a.t + 20)
    rows.sort(key=lambda r: r[1])
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["viewer", "t_s", "rendition", "level", "bytes", "download_s", "http", "late"])
            for r in rows: w.writerow([r[0], round(r[1] - t0, 3), r[2], r[3], r[4], round(r[5], 4), r[6], r[7]])
    seg = [r for r in rows if r[2] not in ("master", "playlist")]
    print("viewers: %d, duration %.0f s, segments downloaded: %d, HTTP errors: %d" % (a.n, a.t, len(seg), sum(1 for r in rows if r[6] != 200)))
    tot = sum(r[4] for r in seg) * 8 / 1000.0 / a.t
    print("aggregate download rate: %.0f kbit/s" % tot)
    for v in range(1, a.n + 1):
        s = [r for r in seg if r[0] == v]
        if not s: print("viewer %d: no segments" % v); continue
        lv = {}; [lv.__setitem__(r[2], lv.get(r[2], 0) + 1) for r in s]
        ds = sorted(r[5] for r in s)
        print("viewer %d: %d segs, mean %.0f kbit/s, download p50 %.2f s p95 %.2f s, late %d, renditions %s"
              % (v, len(s), sum(r[4] for r in s) * 8 / 1000.0 / max(sum(r[5] for r in s), 1e-3), ds[len(ds) // 2],
                 ds[min(int(len(ds) * .95), len(ds) - 1)], sum(r[7] for r in s), lv))


if __name__ == "__main__":
    main()
