#!/bin/bash
# Log FFmpeg CPU load, SoC temperature and throttling every 2 s to a CSV file.
# Usage: ./monitor.sh [output.csv]      (stop with Ctrl+C)
OUT=${1:-monitor_$(date +%Y%m%d_%H%M%S).csv}
INT=2
HZ=$(getconf CLK_TCK)
PID=$(pidof ffmpeg | awk '{print $1}')
[ -z "$PID" ] && { echo "ffmpeg is not running"; exit 1; }

ticks() { awk '{print $14 + $15}' /proc/$PID/stat; }
echo "time,ffmpeg_cpu_pct_of_one_core,temp_c,throttled,mem_avail_mb" | tee "$OUT"
prev=$(ticks)
while kill -0 "$PID" 2>/dev/null; do
  sleep $INT
  now=$(ticks) || break
  cpu=$(( (now - prev) * 100 / (HZ * INT) )); prev=$now
  temp=$(vcgencmd measure_temp | grep -o '[0-9.]*')
  thr=$(vcgencmd get_throttled | cut -d= -f2)
  mem=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  echo "$(date +%T),$cpu,$temp,$thr,$mem" | tee -a "$OUT"
done
echo "ffmpeg stopped; log saved to $OUT"
