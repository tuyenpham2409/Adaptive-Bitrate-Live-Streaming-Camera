# Demo script (about 6 minutes)

Prepare: Pi powered, laptop on the same network, `http://<pi-ip>/?abr=custom&sync=3` open full screen in one tab, a second terminal ssh'd to the Pi. Rehearse once; do not rely on a first run.

| min | What to show | What to say | If it goes wrong |
|---|---|---|---|
| 0:00 | Unplug and plug the Pi power, start a stopwatch | Boot to live video takes about 53 s, no keyboard or login needed (systemd) | Show the recorded boot time from the week-3 report |
| 1:00 | The page: live video, level, estimate, buffer, latency about 3 s | 3 renditions, 1 s fMP4 segments, hardware H.264, latency 9 s (week 2) -> 3.2 s (week 3) | - |
| 2:00 | `sudo scripts/tc_steps.sh wlan0 20` in the terminal; watch the level fall to 540p/360p and come back | The controller drops at once and rises one step at a time after 3 good segments; hls.js default needed about 64 s to rise on the board; the team's controller needs a few seconds in the simulation and in the headless-Chrome test (board numbers in Report week 4) | Use `sudo tc qdisc replace dev wlan0 root tbf rate 1mbit burst 32kbit latency 400ms` by hand, then `sudo tc qdisc del dev wlan0 root` |
| 3:30 | Second laptop/phone opens the page | Two viewers share the uplink; model and test results for N viewers in the report | Run `tools/viewer_load.py -n 4 -t 30` instead |
| 4:30 | `sudo pkill -STOP ffmpeg` (hang), wait up to 60 s; show `journalctl -t abr-health` and the stream coming back | systemd restarts a crashed FFmpeg; the health timer also restarts a hung one | `sudo pkill ffmpeg` shows the systemd restart |
| 5:30 | `python3 tools/stability_report.py` on the 1-hour log, the model figures | Models: UML, SystemC, Python; measured vs simulated | - |

Always end with `sudo tc qdisc del dev wlan0 root` and `sudo pkill -CONT ffmpeg`.
