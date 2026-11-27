#!/bin/bash
# Log FFmpeg CPU load, SoC temperature, throttling and free RAM every 2 s to a CSV file.
# Week 4 adds four columns at the end (the first five are unchanged, so week-3 analysis still works):
#   ffmpeg_rss_mb  resident memory of ffmpeg (leak check)
#   shm_used_mb    size of the HLS directory in RAM (must stay constant: delete_segments)
#   nginx_conn     established TCP connections to port 80 (viewers)
#   restarts       systemd NRestarts of abr-hls (0 = FFmpeg never crashed)
# If FFmpeg restarts the script follows the new process instead of exiting.
# Usage: ./monitor.sh [output.csv] [duration_s]      (stop with Ctrl+C; duration 0 = until Ctrl+C)
OUT=${1:-monitor_$(date +%Y%m%d_%H%M%S).csv}
LIMIT=${2:-0}
HLS=${HLS_DIR:-/dev/shm/hls}
INT=2
HZ=$(getconf CLK_TCK)
getpid() { pidof ffmpeg | awk '{print $1}'; }
PID=$(getpid)
[ -z "$PID" ] && { echo "ffmpeg is not running"; exit 1; }

ticks() { awk '{print $14 + $15}' /proc/$PID/stat 2>/dev/null; }
echo "time,ffmpeg_cpu_pct_of_one_core,temp_c,throttled,mem_avail_mb,ffmpeg_rss_mb,shm_used_mb,nginx_conn,restarts" | tee "$OUT"
prev=$(ticks); start=$(date +%s)
while true; do
  sleep $INT
  [ "$LIMIT" -gt 0 ] && [ $(( $(date +%s) - start )) -ge "$LIMIT" ] && break
  if ! kill -0 "$PID" 2>/dev/null; then          # ffmpeg died: wait for the new process
    PID=$(getpid); [ -z "$PID" ] && { echo "$(date +%T),,,,,,,," | tee -a "$OUT"; continue; }
    prev=$(ticks); continue
  fi
  now=$(ticks) || continue
  cpu=$(( (now - prev) * 100 / (HZ * INT) )); prev=$now
  temp=$(vcgencmd measure_temp | grep -o '[0-9.]*')
  thr=$(vcgencmd get_throttled | cut -d= -f2)
  mem=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  rss=$(awk '/VmRSS/ {print int($2/1024)}' /proc/$PID/status 2>/dev/null)
  shm=$(du -sm "$HLS" 2>/dev/null | cut -f1)
  conn=$(ss -H -tn state established '( sport = :80 )' 2>/dev/null | wc -l)
  rst=$(systemctl show abr-hls -p NRestarts --value 2>/dev/null)
  echo "$(date +%T),$cpu,$temp,$thr,$mem,$rss,$shm,$conn,${rst:-0}" | tee -a "$OUT"
done
echo "monitor finished; log saved to $OUT"
