PYTHON ?= python3

.PHONY: install test lint validate demo

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check src tests

validate:
	marketlab validate-registry registry/hypotheses.yaml

demo:
	marketlab evaluate-signal data/fixtures/h002_feasibility.csv --signal-col ue --excess-col excess_vs_nifty
	marketlab evaluate-binary data/fixtures/h002_feasibility.csv --group-col ue_sign --excess-col excess_vs_nifty
