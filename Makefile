PY ?= .venv/bin/python
export PYTHONPATH := .

.PHONY: setup test gate eval eval-quick heal dashboard hydradb hydradb-reset record demo

setup:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

test:
	$(PY) -m pytest -q

gate:            ## prove custom writes + Cypher on HydraDB (needs HYDRADB_URI / HYDRADB_TOKEN)
	$(PY) scripts/gate_hydradb.py

eval:            ## full eval: 3 seeds, A vs B vs C, learning curve -> results/
	$(PY) -m eval.run --seeds 0,1,2 --rounds 4 --train-per-template 8 --test-per-template 6
	$(PY) -m eval.heal --seed 0
	$(PY) -m eval.calculator
	$(PY) scripts/update_readme.py

eval-quick:      ## one seed, smaller, for smoke testing
	$(PY) -m eval.run --seeds 0 --rounds 2 --train-per-template 4 --test-per-template 2

heal:
	$(PY) -m eval.heal --seed 0

dashboard:
	$(PY) -m uvicorn dashboard.app:app --port 8000

hydradb:         ## run a local HydraDB v0.4.0 node (build it first: see README)
	scripts/hydradb_node.sh

record:          ## record the backup demo from the running dashboard -> docs/demo.mp4
	$(PY) scripts/record_demo.py

demo:            ## start HydraDB node (if needed) + dashboard -> http://127.0.0.1:8000
	scripts/start_demo.sh

hydradb-reset:   ## stop the local node and wipe its (synthetic, regenerable) store
	-pkill -f target/release/graph-node
	rm -rf .hydradb/store .hydradb/cache
