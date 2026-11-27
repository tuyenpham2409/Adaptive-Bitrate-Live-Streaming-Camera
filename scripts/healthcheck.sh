#!/bin/bash
# Watchdog for the stream (week 4, WP2): restart abr-hls if the playlists stop being updated.
# systemd's Restart=always only reacts when FFmpeg EXITS; a hung FFmpeg (camera/USB stall) keeps the
# process alive but the segments stop. Run every 30 s by systemd/abr-health.timer.
HLS=${HLS_DIR:-/dev/shm/hls}; MAX_AGE=${MAX_AGE:-15}; SERVICE=${SERVICE:-abr-hls}
PL="$HLS/720p/stream.m3u8"
systemctl is-active --quiet "$SERVICE" || exit 0                       # service stopped on purpose
up=$(awk '{print int($1)}' /proc/uptime)
state=$(systemctl show "$SERVICE" -p ActiveEnterTimestampMonotonic --value 2>/dev/null)
age_service=$(( up - ${state:-0} / 1000000 ))
[ "$age_service" -lt 30 ] && exit 0                                    # give a fresh start time to produce segments
if [ ! -f "$PL" ]; then age=999999; else age=$(( $(date +%s) - $(stat -c %Y "$PL") )); fi
if [ "$age" -gt "$MAX_AGE" ]; then
  logger -t abr-health "playlist $PL is ${age}s old (> ${MAX_AGE}s): restarting $SERVICE"
  systemctl restart "$SERVICE"
fi
