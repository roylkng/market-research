PYTHON ?= python3

.PHONY: install test lint validate

install:
	$(PYTHON) -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check src tests

validate:
	marketlab validate-registry registry/hypotheses.yaml
