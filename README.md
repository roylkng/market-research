# market-research

A research-first laboratory for testing Indian equity-market hypotheses with reproducible, falsifiable experiments.

The project is deliberately **not** a stock-prediction product and does not permit live-capital deployment from unvalidated research. Its purpose is to build a durable evidence ledger: hypotheses are frozen before testing, every failed experiment is retained, and complexity must beat simple benchmarks before it is promoted.

## Current status

| Hypothesis | Question | Status |
|---|---|---|
| H001 | Does raw revenue/profit/margin acceleration predict post-results returns? | **REJECTED** |
| H002 | Does positive unexpected earnings produce post-earnings-announcement drift in liquid Indian equities? | **FROZEN — prospective evaluation required** |
| H003 | Does prior management delivery credibility predict 120-session sector-relative returns? | **FROZEN — prospective evaluation required** |

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

## Frozen prospective coverage panel

H002 and H003 use universe rule `U001`. The first cohort is now frozen at:

`research/prospective/universes/FY27-Q2-2026-09-06.json`

Canonical SHA-256:

`cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb`

U001 v2 is mechanical:

1. take exact Nifty 200 membership, Industry and ISIN from the official NSE constituent CSV,
2. take point-in-time free-float market capitalization from the NSE Nifty 200 index payload,
3. require exact symbol-set agreement between both 200-name sources,
4. exclude `Financial Services`,
5. rank by FFMC descending and symbol ascending,
6. freeze the top 100 for the full earnings cohort.

The frozen cohort contains 100 unique non-financial names and preserves hashes of both official source artifacts. This is a research panel, not a portfolio or a list of companies expected to outperform. See `docs/universe-v1.md` and `registry/universes.yaml`.

A separate curated development cohort in `registry/development_companies.yaml` is used to stress acquisition, extraction and company-intelligence workflows. Those companies cannot enter H002/H003 by exception.

## Source of record

For prospective earnings events, NSE Integrated Filing - Financials is the primary source of record when available. Web JSON endpoints can assist discovery, but retained provenance points to the original exchange Details/XBRL document and preserves its hash and exchange timestamps. See `docs/source-decision.md`.

## Frozen H002 signal

The first prospective earnings-surprise rule is `H002-UE-v1`:

```text
expected_eps = basic_eps from the same quarter one year earlier
unexpected_eps = actual_basic_eps - expected_eps
UE = unexpected_eps / price_day_minus_2
```

Rule SHA-256:

`24eb8325216e68db8e3f14db440a0f470f9f576a3d1aea034b570812c70686ff`

The rule uses sign buckets (`POSITIVE`, `ZERO`, `NEGATIVE`) and returns `NO_SIGNAL` for missing or non-comparable inputs. It deliberately does not add analyst-consensus, momentum, valuation, guidance or LLM overlays. See `docs/h002-ue-v1.md` and `registry/signals/H002-UE-v1.json`.

## Repository layout

```text
market-research/
├── docs/                 # protocol, data policy, source/universe decisions
├── hypotheses/           # immutable human-readable hypotheses
├── experiments/          # frozen specs and results
├── registry/             # hypothesis, signal, experiment, universe and dev-company ledgers
├── research/             # historical reconstruction, company intelligence, prospective data
├── src/marketlab/        # evaluation, acquisition, parsing and feature code
├── tests/                # invariants, provenance and leakage tests
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

If your system exposes only a versioned interpreter, for example `python3.12`, use that in the first command.

## Commands

Validate the research ledger:

```bash
marketlab validate-registry registry/hypotheses.yaml
```

Validate the frozen U001 cohort:

```bash
marketlab validate-universe research/prospective/universes/FY27-Q2-2026-09-06.json
```

The repository ships a **feasibility-only** H002 fixture so evaluator commands are runnable immediately. It is not production-grade point-in-time data.

```bash
marketlab evaluate-signal data/fixtures/h002_feasibility.csv \
  --signal-col ue \
  --excess-col excess_vs_nifty

marketlab evaluate-binary data/fixtures/h002_feasibility.csv \
  --group-col ue_sign \
  --excess-col excess_vs_nifty
```

Reconstruct an old source-derived filing fixture without making it prospective evidence:

```bash
marketlab reconstruct-event \
  data/fixtures/filings/ccl_fy27_q1_consolidated_source_derived.html \
  --source-url https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_178875_27072026202614_iXBRL_WEB.html \
  --store .marketlab
```

Inspect management delivery evidence without leaking future outcomes:

```bash
marketlab delivery-feature research/company-intelligence/claims_v1.yaml \
  --symbol CCL \
  --as-of 2026-09-06
```

Run repository checks:

```bash
make lint
make test
make validate
```

## Current next experiments

H002's expectation/signal rule is now frozen. Its next gate is **H002-C deterministic paper execution and benchmark reconstruction**: trading calendar, second-session entry, 20-session exit, exact price provenance, sector/broad/momentum benchmarks, corporate actions and explicit non-tradable/skipped observations.

H003 is separately frozen at a 120-session horizon. Its next gate is expanding pre-existing claim/delivery history across U001 while enforcing the `as_of` cutoff, then testing future sector-relative returns.

No rule changes are permitted after observations begin without creating a new hypothesis/version.

## Historical reconstruction

Older free filings and historical news can be used to build and test acquisition and company-intelligence capabilities. Such records are labelled `HISTORICAL_RECONSTRUCTION`. They cannot be counted as prospective validation because their subsequent outcomes are already knowable.

The first reconstruction cases are seeded for INFY, CCL and SHAILY. Source-derived parser fixtures are intentionally labelled as derived and their hashes must never be represented as original exchange-file hashes.

## Future architecture

Only after multiple independent signals survive prospective testing should this evolve toward specialized regime, earnings, momentum, and event models with a meta-allocator and separate risk model. See `docs/architecture.md`.
