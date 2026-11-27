#!/bin/bash
# Make a flash + beep test clip for the A/V sync test (week 4).
# Every PERIOD seconds the screen flashes white for FLASH s and a 1 kHz beep of the same length
# plays. Play it full screen on a laptop/phone in front of the camera, and put the speaker next
# to the webcam microphone.   Usage: ./make_sync_clip.sh [out.mp4] [seconds]
OUT=${1:-sync_clip.mp4}; DUR=${2:-40}; PERIOD=${PERIOD:-2}; FLASH=${FLASH:-0.1}
exec ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=black:s=1280x720:r=30:d=$DUR,geq=lum='if(lt(mod(T,$PERIOD),$FLASH),235,16)':cb=128:cr=128" \
  -f lavfi -i "aevalsrc='if(lt(mod(t,$PERIOD),$FLASH),0.8*sin(2*PI*1000*t),0)':s=48000:d=$DUR" \
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest "$OUT"
