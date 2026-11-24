#!/bin/bash
# Bandwidth step test: limit the Pi's outgoing rate (Pi -> browser) step by step.
# The limit is ALWAYS removed when the script ends. Ctrl+C stops the whole test.
# Usage: sudo ./tc_steps.sh [interface] [seconds_per_step]
#   e.g. sudo ./tc_steps.sh wlan0 60
IF=${1:-wlan0}
STEP=${2:-60}
RATES="none 5mbit 2500kbit 1200kbit 700kbit 1200kbit 2500kbit 5mbit none"   # never below ~500kbit: SSH uses the same link
LOG=tc_steps_$(date +%Y%m%d_%H%M%S).csv

cleanup() { tc qdisc del dev "$IF" root 2>/dev/null; echo "limit removed on $IF"; }
trap cleanup EXIT
trap 'echo "stopped by user"; exit 1' INT TERM HUP

[ "$(id -u)" -ne 0 ] && { echo "run with sudo"; exit 1; }
ip link show "$IF" >/dev/null 2>&1 || { echo "no interface $IF"; exit 1; }

echo "clock,rate" | tee "$LOG"
for r in $RATES; do
  if [ "$r" = none ]; then
    tc qdisc del dev "$IF" root 2>/dev/null
  else
    tc qdisc replace dev "$IF" root tbf rate "$r" burst 32kbit latency 400ms
  fi
  echo "$(date +%T),$r" | tee -a "$LOG"
  sleep "$STEP"
done
