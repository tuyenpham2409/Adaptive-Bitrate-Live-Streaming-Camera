# Models (week 3)

| Tool | File | What it does |
|---|---|---|
| UML (PlantUML) | `uml/*.puml` (+ rendered `.png`) | component diagram, ABR sequence diagram, test loop |
| SystemC 2.3.4 | `abr_pipeline_v3.cpp`, `run_systemc.sh` | capture -> shared HW encoder -> segmenter, audio branch, HLS client latency |
| Python | `abr_sim.py`, `whatif.py`, `make_figs.py` | hls.js ABR model: replay of logged throughput, closed-loop simulation, what-if sweep |

Run (from `models/`):

    python3 abr_sim.py && python3 whatif.py && python3 make_figs.py     # needs numpy, pandas, matplotlib
    SYSTEMC=/opt/systemc ./run_systemc.sh                               # needs SystemC built from accellera-official/systemc (tag 2.3.4)
    java -jar plantuml.jar -tpng uml/*.puml

Measured logs are in `data/week3/` (A = 2 s segments, B = 1 s / sync 3 (chosen), C = 1 s / sync 2), results and figures in `results/week3/`.
