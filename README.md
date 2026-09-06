# market-research

A research-first laboratory for testing Indian equity-market hypotheses with reproducible, falsifiable experiments.

The project is deliberately **not** a stock-prediction product and does not permit live-capital deployment from unvalidated research. Its purpose is to build a durable evidence ledger: hypotheses are frozen before testing, every failed experiment is retained, and complexity must beat simple benchmarks before it is promoted.

## Current status

| Hypothesis | Question | Status |
|---|---|---|
| H001 | Does raw revenue/profit/margin acceleration predict post-results returns? | **REJECTED** |
| H002 | Does positive unexpected earnings produce post-earnings-announcement drift in liquid Indian equities? | **INCONCLUSIVE — prospective paper test required** |

No model in this repository is approved for live capital.

## Research principles

1. Freeze hypotheses before observing outcomes.
2. Point-in-time data only for production-grade backtests.
3. Missing data stays missing. Never fabricate fills or historical values.
4. Compare every complex signal with simple investable benchmarks.
5. Track all attempted variants to limit backtest overfitting.
6. Separate market-regime, sector, event, and stock-selection models by horizon.
7. Promote models only after walk-forward and prospective paper evidence.

See `docs/research-protocol.md` and `registry/hypotheses.yaml` once the research foundation PR is merged.
