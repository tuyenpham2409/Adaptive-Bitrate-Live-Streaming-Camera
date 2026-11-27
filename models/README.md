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

## Week 4: team ABR controller ("Hybrid")
| File | What it does |
|---|---|
| `abr_custom.py` | Hybrid controller (Python reference), generic closed-loop simulator, comparison with the hls.js default, parameter sensitivity |
| `make_figs_w4.py`, `fig_e2e.py` | figures in `results/week4/` |
| `gen_vectors.py` | writes `tests/abr_vectors.json` (Python decisions) for the JS port test |
| `../web/hybrid_abr.js` | the same algorithm for the browser (loaded by `index.html?abr=custom`) |
| `../tests/test_abr_port.js` | `node tests/test_abr_port.js`: JS and Python give the same decisions |
| `../e2e/` | end-to-end test of the page in headless Chrome |
