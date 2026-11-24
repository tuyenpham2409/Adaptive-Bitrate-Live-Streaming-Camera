#!/bin/bash
# Week 3: 3-rendition adaptive HLS (fMP4) on the Pi 4 hardware encoder.
# 720p @ 2500k, 540p @ 1200k, 360p @ 500k, 30 fps, AAC 128k, master playlist.
# Output: /dev/shm/hls/master.m3u8 + /dev/shm/hls/{720p,540p,360p}/
#
# Override any setting from the command line, e.g.:
#   H540=544 ./run_abr.sh          # if 960x540 fails on h264_v4l2m2m
#   SEG=1 GOP=30 ./run_abr.sh      # low-latency test
#   ENC360=libx264 ./run_abr.sh    # fallback: software encoder for 360p only

VIDEO_DEV=${VIDEO_DEV:-/dev/video0}
AUDIO_DEV=${AUDIO_DEV:-plughw:1,0}     # check with: arecord -l
H540=${H540:-540}                      # 540, or 544 if the encoder rejects 540
SEG=${SEG:-2}                          # segment length (s)
GOP=${GOP:-60}                         # keyframe interval = SEG * 30
ENC360=${ENC360:-h264_v4l2m2m}
OUT=${OUT:-/dev/shm/hls}
STATS=${STATS:--stats}                # -nostats when run as a service

X264_OPTS=""
[ "$ENC360" = "libx264" ] && X264_OPTS="-preset:v:2 veryfast -tune:v:2 zerolatency"

mkdir -p "$OUT"/720p "$OUT"/540p "$OUT"/360p
rm -rf "$OUT"/*.m3u8 "$OUT"/720p/* "$OUT"/540p/* "$OUT"/360p/*

exec ffmpeg -hide_banner -loglevel warning $STATS \
 -thread_queue_size 512 -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i "$VIDEO_DEV" \
 -thread_queue_size 512 -f alsa -i "$AUDIO_DEV" \
 -filter_complex "[0:v]split=3[a][b][c]; \
   [a]format=yuv420p[v720]; \
   [b]scale=960:${H540},format=yuv420p[v540]; \
   [c]scale=640:360,format=yuv420p[v360]; \
   [1:a]aresample=async=1:first_pts=0,asplit=3[a1][a2][a3]" \
 -map "[v720]" -map "[v540]" -map "[v360]" -map "[a1]" -map "[a2]" -map "[a3]" \
 -c:v:0 h264_v4l2m2m -b:v:0 2500k \
 -c:v:1 h264_v4l2m2m -b:v:1 1200k \
 -c:v:2 "$ENC360"    -b:v:2 500k $X264_OPTS \
 -g "$GOP" -keyint_min "$GOP" -bf 0 \
 -c:a aac -b:a 128k -ar 48000 \
 -f hls -hls_time "$SEG" -hls_list_size 6 \
 -hls_flags delete_segments+independent_segments \
 -hls_segment_type fmp4 \
 -master_pl_name master.m3u8 \
 -var_stream_map "v:0,a:0,name:720p v:1,a:1,name:540p v:2,a:2,name:360p" \
 -hls_segment_filename "$OUT/%v/seg%d.m4s" \
 "$OUT/%v/stream.m3u8"
