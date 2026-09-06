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
	$(PYTHON) -c "from marketlab.h002 import load_and_validate_rule; d=load_and_validate_rule('registry/h002_signal_rule.yaml'); print(f\"H002 rule valid: {d['id']} sha256={d['sha256']}\")"
	$(PYTHON) -c "from marketlab.execution import load_and_validate_execution_rule; d=load_and_validate_execution_rule('registry/h002_execution_rule.yaml'); print(f\"H002 execution valid: {d['id']} sha256={d['sha256']}\")"
	$(PYTHON) -c "from marketlab.prospective import load_and_validate_runner_rule; d=load_and_validate_runner_rule('registry/h002_runner_rule.yaml'); print(f\"H002 runner valid: {d['id']} sha256={d['sha256']}\")"
	$(PYTHON) -c "from marketlab.h003_sources import load_and_validate_source_rule; d=load_and_validate_source_rule('registry/h003_source_rule.yaml'); print(f\"H003 source rule valid: {d['id']} sha256={d['sha256']}\")"

demo:
	marketlab evaluate-signal data/fixtures/h002_feasibility.csv --signal-col ue --excess-col excess_vs_nifty
	marketlab evaluate-binary data/fixtures/h002_feasibility.csv --group-col ue_sign --excess-col excess_vs_nifty
