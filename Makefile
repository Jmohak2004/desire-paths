PY ?= .venv/bin/python
export PYTHONPATH := .

.PHONY: setup test gate eval eval-quick heal dashboard

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

eval-quick:      ## one seed, smaller, for smoke testing
	$(PY) -m eval.run --seeds 0 --rounds 2 --train-per-template 4 --test-per-template 2

heal:
	$(PY) -m eval.heal --seed 0

dashboard:
	$(PY) -m uvicorn dashboard.app:app --port 8000
