#!/bin/bash
# 720p30 HW H.264 + AAC -> fMP4 HLS in /dev/shm/hls
mkdir -p /dev/shm/hls && rm -f /dev/shm/hls/*
exec ffmpeg -loglevel warning -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0 \
 -f alsa -i plughw:1,0 \
 -c:v h264_v4l2m2m -pix_fmt yuv420p -b:v 2500k -g 60 -bf 0 \
 -c:a aac -b:a 128k \
 -f hls -hls_time 2 -hls_list_size 6 -hls_flags delete_segments+independent_segments \
 -hls_segment_type fmp4 -hls_fmp4_init_filename init.mp4 -hls_segment_filename '/dev/shm/hls/seg%d.m4s' \
 /dev/shm/hls/stream.m3u8
