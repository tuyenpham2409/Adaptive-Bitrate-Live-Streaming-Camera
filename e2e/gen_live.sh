#!/bin/bash
# Live HLS test stream similar to the Pi: 3 renditions, fMP4, 1 s segments, GOP 30, audio
OUT=${1:-/tmp/live}; mkdir -p $OUT
exec ffmpeg -loglevel error -re -f lavfi -i "testsrc2=size=1280x720:rate=30" -f lavfi -i "sine=frequency=440:sample_rate=48000" \
 -filter_complex "[0:v]split=3[a][b][c];[a]format=yuv420p[v0];[b]scale=960:540,format=yuv420p[v1];[c]scale=640:360,format=yuv420p[v2];[1:a]asplit=3[a0][a1][a2]" \
 -map "[v0]" -map "[v1]" -map "[v2]" -map "[a0]" -map "[a1]" -map "[a2]" \
 -c:v libx264 -preset ultrafast -tune zerolatency -profile:v main -g 30 -keyint_min 30 -sc_threshold 0 \
 -b:v:0 2500k -maxrate:v:0 2500k -bufsize:v:0 2500k -b:v:1 1200k -maxrate:v:1 1200k -bufsize:v:1 1200k -b:v:2 500k -maxrate:v:2 500k -bufsize:v:2 500k \
 -c:a aac -b:a 128k -ar 48000 \
 -f hls -hls_time 1 -hls_list_size 6 -hls_flags delete_segments+independent_segments -hls_segment_type fmp4 \
 -master_pl_name master.m3u8 -var_stream_map "v:0,a:0,name:720p v:1,a:1,name:540p v:2,a:2,name:360p" \
 -hls_segment_filename "$OUT/%v/seg%d.m4s" "$OUT/%v/stream.m3u8"
