# Week 4 runbook: what to run on the Pi, who runs it, what to send back

Everything below was written and tested without the board (synthetic streams with known answers, see `data/week4/*validation*`). The numbers of the report come from running it on the Pi, so each owner runs and signs their own part. Total time about 2 h. Order: setup, start monitor (T17), T19, T15, T16, T18, stop monitor, T20, T21 (T20/T21 stop the stream).

## 0. Once (Tuyên or Vân, 15 min)
    git checkout -b week4-all && unzip -o week4_all_repo_files.zip -d .          # in the repo root
    scp -r web scripts systemd tools g1pi@<IP>:~/Adaptive-Bitrate-Live-Streaming-Camera/
    ssh g1pi@<IP>
    sudo apt install -y v4l-utils python3-numpy                                      # numpy is only needed if you run tools/ on the Pi
    sudo cp ~/Adaptive-Bitrate-Live-Streaming-Camera/web/{index.html,hybrid_abr.js} /var/www/html/
    sudo cp ~/Adaptive-Bitrate-Live-Streaming-Camera/systemd/abr-* /etc/systemd/system/
    sudo systemctl daemon-reload && sudo systemctl restart abr-hls
    sudo systemctl enable --now abr-health.timer && systemctl list-timers | grep abr
On the laptop: `pip install numpy pandas matplotlib` (Ubuntu: also `ffmpeg`).
Set the stream to the chosen setting (1 s segments): uncomment `Environment=SEG=1` and `Environment=GOP=30` in `/etc/systemd/system/abr-hls.service` if not done yet.

## 1. Vân (WP3, player and ABR): T15 and T16, 25 min
Open the page with ?abr=custom&sync=3 (the 27 Nov message has the details): `http://<IP>/?abr=custom&sync=3` then `sudo ./tc_steps.sh wlan0 60` (T15); `http://<IP>/?sync=3` and the same (T16). Download the page CSV after each. Send: 2 page CSVs and 2 `tc_steps_*.csv`.

## 2. Tuyên (WP2, packaging and server)
### T18 N viewers, 20 min (the T17 monitor keeps running)
Laptop, for N = 1, 2, 3, 5:
    python3 tools/viewer_load.py http://<IP>/hls/master.m3u8 -n N -t 90 --stagger 3 --csv t18_abr_nN.csv
and once more worst-case with every viewer fixed on 720p: `-n 3 --level 720p --csv t18_720p_n3.csv`.
Read FFmpeg CPU and `nginx_conn` per N from the T17 log (the time of each run is in the viewer CSV).  Send: all `t18_*` files and the printed summaries.
### T17 stability log (no separate 1-hour run needed)
Start the monitor once at the beginning of the session and let it run through T19, T15, T16 and T18 (about 60 min together):
    cd ~/Adaptive-Bitrate-Live-Streaming-Camera/scripts && nohup ./monitor.sh t17_session.csv > /dev/null 2>&1 &
Stop it before T20/T21 (they stop the stream): `pkill -f monitor.sh`. Then `systemctl show abr-hls -p NRestarts` and
`python3 tools/stability_report.py t17_session.csv --md t17.md`. Report the real duration printed by the tool ("stability log of N min during T19, T15, T16, T18"), not "1 hour".
A log shorter than 30 min gets no leak verdict; with only 10 min run `./scripts/monitor.sh t17_10min.csv 600` with one page open and call it "10-minute stability run".
### Watchdog test, 5 min (also the demo step)
`sudo pkill -STOP ffmpeg`; wait up to 60 s; `journalctl -t abr-health --since "5 min ago"` must show the restart and the stream must come back; `sudo systemctl status abr-hls` shows a new start time.

## 3. Doanh (WP1, capture and encoding)
### T19 A/V sync, 20 min
Laptop: `tools/make_sync_clip.sh sync_clip.mp4 60`. Play it full screen at full brightness and volume on a phone or second screen, 30 cm in front of the webcam, speaker next to the webcam. Record each rendition for 40 s (the stream must be running):
    ffmpeg -i http://<IP>/hls/720p/stream.m3u8 -map 0:v:0 -map 0:a:0 -t 40 -c copy rec_720p.mkv
    (same for 540p and 360p)
    python3 tools/av_sync.py rec_720p.mkv --csv av_720p.csv
Expect about 18 paired events per 40 s. If fewer than 10, move the phone closer, raise the volume, or lower the room light. Send: three `rec_*.mkv` (or the printed output) and the CSVs.
### T20 frame rate and duplicated frames, 10 min
On the Pi: `./scripts/capture_check.sh t20` (stops the stream for about 2 min and restarts it). Repeat with the lens half covered. Send `t20/stats_dyn*.txt`, `t20/controls.txt`.
### T21 quality per rendition, 15 min
On the Pi: `sudo systemctl stop abr-hls`, then
    ffmpeg -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0 -t 12 -c copy ref.mkv
    python3 tools/quality_eval.py ref.mkv --encoders h264_v4l2m2m,libx264 --seconds 10 --out quality_pi.csv
    sudo systemctl start abr-hls
Use a scene with movement and detail (a person moving, a book page), not a white wall. If `h264_v4l2m2m` cannot encode 540p, the script prints which rendition it skipped. VMAF is computed only if `ffmpeg -filters | grep libvmaf` shows the filter. Send `quality_pi.csv`.

## 4. Send back
One folder `week4_pi/` with all files above, or zip it. I (or whoever writes Report week 4) will read the CSVs, update the numbers in the report and mark each result as measured. Do not edit the numbers by hand.

## What the tools can and cannot tell you
- `av_sync.py`: the offset includes the phone's screen and speaker delay; read the absolute value as +-50 ms, compare renditions and runs with each other. The tool itself was checked on streams with known offsets (error about 1 ms in tests/test_tools.py).
- `frame_stats.py`: measured on the camera's MJPEG, before the encoder; a static scene does not create duplicates by itself.
- `quality_eval.py`: PSNR/SSIM follow the quality of the encoder against the camera frame; they do not say how it looks.
- `viewer_load.py`: viewers on one laptop share the laptop's Wi-Fi card; the number that matters is what the Pi serves (monitor log), not each viewer's speed.
