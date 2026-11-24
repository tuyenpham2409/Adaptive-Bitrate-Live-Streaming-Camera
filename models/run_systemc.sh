#!/bin/bash
# Build the SystemC model and run all scenarios -> results/systemc_results.csv
# SYSTEMC=/path/to/systemc (default /opt/systemc, see README: build SystemC 2.3.4 from accellera-official/systemc)
set -e
cd "$(dirname "$0")"; SC=${SYSTEMC:-/opt/systemc}; OUT=../results/week3; mkdir -p "$OUT"
g++ -std=c++17 -O2 -I"$SC/include" abr_pipeline_v3.cpp -L"$SC/lib" -lsystemc -o abr_pipeline_v3 2>&1 | grep -v "^$" | grep -v -i "info:" || true
{
echo "scenario,ladder,seg_s,sync,nominal_load_pct,busy_pct,frames,dropped,enc_lat_mean_ms,enc_lat_max_ms,segments,audio_per_seg,join_lat_min_s,join_lat_mean_s,join_lat_max_s"
./abr_pipeline_v3 --name S1_planned_A --ladder planned --seg 2 --sync 3
./abr_pipeline_v3 --name S1_planned_B --ladder planned --seg 1 --sync 3
./abr_pipeline_v3 --name S1_planned_C --ladder planned --seg 1 --sync 2
./abr_pipeline_v3 --name S2_plus1080p  --ladder plus1080 --seg 1 --sync 3
./abr_pipeline_v3 --name S3_plus480p   --ladder plus480  --seg 1 --sync 3
} 2>/dev/null | grep -E '^(scenario|S[0-9])' > "$OUT/systemc_results.csv"
cat "$OUT/systemc_results.csv"
