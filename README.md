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

## Prospective coverage panel

H002 v1 will use universe rule `U001`:

> For each earnings cohort, take current Nifty 200 constituents, remove the NSE macro sector `Financial Services`, rank the remainder by NSE free-float market capitalization, then freeze the top 100 for that cohort.

This is a research panel, not a portfolio. See `docs/universe-v1.md` and `registry/universes.yaml`.

A separate curated development cohort in `registry/development_companies.yaml` is used to stress acquisition, extraction and company-intelligence workflows. Those companies cannot enter H002 by exception.

## Source of record

For prospective earnings events, NSE Integrated Filing - Financials is the primary source of record when available. Web JSON endpoints can assist discovery, but the retained provenance points to the original exchange Details/XBRL document and preserves its hash and exchange timestamps. See `docs/source-decision.md`.

## Repository layout

```text
market-research/
├── docs/                 # protocol, data policy, source/universe decisions
├── hypotheses/           # immutable human-readable hypotheses
├── experiments/          # frozen specs and results
├── registry/             # hypothesis, experiment, universe and dev-company ledgers
├── research/             # historical reconstruction manifests
├── src/marketlab/        # evaluation, acquisition, parsing and universe code
├── tests/                # invariants and metric tests
├── reports/              # published research reports
├── data/                 # data policy and small published fixtures
└── artifacts/            # artifact manifests and hashes
```

## Setup

Python 3.11+ is required. On Linux, `python3` is the safest bootstrap command because many systems do not install an unversioned `python` executable.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

If your system exposes only a versioned interpreter, for example `python3.12`, use that in the first command:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Commands

Validate the research ledger:

```bash
marketlab validate-registry registry/hypotheses.yaml
```

The repository ships a small **feasibility-only** fixture so the evaluator commands are runnable immediately. It reproduces the 24 exact-return observations from the published H002 pilot. It is not production-grade point-in-time data.

Evaluate the continuous unexpected-earnings signal:

```bash
marketlab evaluate-signal data/fixtures/h002_feasibility.csv \
  --signal-col ue \
  --excess-col excess_vs_nifty
```

Evaluate positive versus negative UE and winner dependence:

```bash
marketlab evaluate-binary data/fixtures/h002_feasibility.csv \
  --group-col ue_sign \
  --excess-col excess_vs_nifty
```

Freeze a 100-company prospective universe snapshot from current NSE metadata:

```bash
marketlab snapshot-universe \
  --cohort-id FY27-Q2 \
  --selection-size 100 \
  --output data/snapshots/FY27-Q2-universe.json
```

The snapshot command fails rather than silently skipping an unclassified high-ranked constituent. Commit a reviewed cohort snapshot before prospective result scoring begins.

Reconstruct an old source-derived filing fixture without making it prospective evidence:

```bash
marketlab reconstruct-event \
  data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html \
  --source-url https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_178875_27072026202614_iXBRL_WEB.html \
  --store .marketlab
```

The local content-addressed store is ignored by Git. See `docs/historical-reconstruction.md`.

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

## Historical reconstruction

Older free filings and historical news can be used to build and test acquisition and company-intelligence capabilities. Such records are labelled `HISTORICAL_RECONSTRUCTION`. They cannot be counted as prospective validation because their subsequent outcomes are already knowable.

The first reconstruction cases are seeded in `research/historical-reconstruction/cases.yaml` for INFY, CCL and SHAILY. Source-derived parser fixtures are intentionally labelled as derived and their hashes must never be represented as original exchange-file hashes.

## Future architecture

Only after multiple independent signals survive prospective testing should this evolve toward specialized regime, earnings, momentum, and event models with a meta-allocator and separate risk model. See `docs/architecture.md`.
