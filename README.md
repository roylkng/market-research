# market-research

A research-first laboratory for testing Indian equity-market hypotheses with reproducible, falsifiable experiments.

The project is deliberately **not** a stock-prediction product and does not permit live-capital deployment from unvalidated research. Its purpose is to build a durable evidence ledger: hypotheses are frozen before testing, every failed experiment is retained, and complexity must beat simple benchmarks before it is promoted.

## Current status

| Hypothesis | Question | Status |
|---|---|---|
| H001 | Does raw revenue/profit/margin acceleration predict post-results returns? | **REJECTED** |
| H002 | Does positive unexpected earnings produce post-earnings-announcement drift in liquid Indian equities? | **INCONCLUSIVE — prospective paper test required** |

**No model in this repository is approved for live capital.**

## Why this repository exists

The first market-research iteration failed in a useful way: explanations were improving faster than prediction quality. This repository changes the process from conversational iteration to pre-registered experiments with explicit rejection outcomes.

The first feasibility pilot found:

- raw earnings acceleration had essentially zero relationship with subsequent excess returns,
- ranked unexpected-earnings magnitude did not cleanly replicate at a 20-session horizon,
- positive unexpected earnings showed a weak positive directional hint, but uncertainty crossed zero and winner dependence was high.

See `reports/experiments/2026-09-06-feasibility-pilot.md`.

## Research principles

1. Freeze hypotheses before observing outcomes.
2. Point-in-time data only for production-grade backtests.
3. Missing data stays missing. Never fabricate fills or historical values.
4. Compare every complex signal with simple investable benchmarks.
5. Track all attempted variants to limit backtest overfitting.
6. Separate market-regime, sector, event, and stock-selection models by horizon.
7. Promote models only after walk-forward and prospective paper evidence.
8. Preserve rejected hypotheses instead of rewriting them until they work.

## Repository layout

```text
market-research/
├── docs/                 # protocol, data policy, evaluation, architecture
├── hypotheses/           # immutable human-readable hypotheses
├── experiments/          # frozen specs and results
├── registry/             # machine-readable hypothesis/experiment ledger
├── src/marketlab/        # evaluation and validation code
├── tests/                # invariants and metric tests
├── reports/              # published research reports
├── data/                 # local/raw policy and future fixtures
└── artifacts/            # artifact manifests and hashes
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Commands

Validate the research ledger:

```bash
marketlab validate-registry registry/hypotheses.yaml
```

Evaluate a continuous signal from a CSV:

```bash
marketlab evaluate-signal data.csv \
  --signal-col ue \
  --excess-col excess_vs_nifty
```

Evaluate a pre-defined binary split and winner dependence:

```bash
marketlab evaluate-binary data.csv \
  --group-col ue_sign \
  --excess-col excess_vs_nifty
```

Run repository checks:

```bash
make lint
make test
make validate
```

## Current next experiment

H002 receives **prospective paper testing only**.

The next-grade experiment must capture in real time:

- original exchange filing and timestamp,
- original reported financials,
- pre-result consensus or pre-registered expected-EPS model,
- exact decision/entry timestamps,
- benchmark prices,
- corporate-action state,
- and immutable raw hashes.

No rule changes are permitted after observations begin without creating a new hypothesis/version.

## Future architecture

Only after multiple independent signals survive prospective testing should this evolve toward specialized regime, earnings, momentum, and event models with a meta-allocator and separate risk model. See `docs/architecture.md`.
