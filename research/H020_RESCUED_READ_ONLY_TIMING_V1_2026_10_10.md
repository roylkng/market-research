# H020 Technical Timing Diagnostic: Current-Main Salvage (2026-10-10)

Status: **DEVELOPMENT / RESEARCH CONTEXT ONLY**. Original PR #61 remains an
unvalidated historical development branch and is not safe to merge wholesale.

## Why this exists

The September H020 branch contained a deterministic technical-feature
calculator but also hundreds of provider-specific historical JSON reports
that were not obtained under today's official point-in-time source contracts.
The tool's heuristic thresholds, scores and "PAPER_ENTRY_ELIGIBLE" labels
were *not* validated on untouched prospective NSE returns.

This PR copies only the independent calculation into a clean, source-agnostic
module on the current main branch and strengthens its input invariants.
It does **not** import the historical Yahoo collector, September run results,
candidate ranking, primary H021 signal or live capital capability.

## Input and chronology contract

- Both stock and benchmark inputs must have unique, timezone-aware,
  monotonically increasing timestamp indices and finite positive adjusted
  close observations.
- The caller **must** explicitly specify the completed as-of trading
  session. There is no implicit "latest available bar" fallback.
- All rows newer than this decision date are dropped before indicators.
  The required common latest stock/benchmark bar must equal the as-of
  session.
- At least 205 *common* sessions are required. A missing as-of session,
  zero last-session volume, missing or nonfinite prices, invalid volume,
  duplicated timestamps or inadequate history fail closed.
- RSI, MACD, moving averages, relative strength, volatility, volume and
  20-day breakouts are all descriptive heuristics, not calibrated outcome
  probabilities.
- A timing action labeled PAPER_ENTRY_ELIGIBLE in the legacy classifier
  **is not an executable order**. Every output explicitly retains
  portfolio_eligibility_allowed=false, live_capital_allowed=false and
  probability_calibrated=false.

## Safe offline execution

Input CSV schema: date,adj_close,volume. Both sources should cover the
same official NSE completed sessions.

    python scripts/evaluate_h020_offline.py \
      --stock-csv /path/to/sourced-stock.csv \
      --benchmark-csv /path/to/sourced-index.csv \
      --symbol SYMBOL \
      --as-of-session YYYY-MM-DD \
      --output /tmp/h020-research-only.json

The output includes each exact CSV SHA-256 and explicitly states that
independent adjusted-price and corporate-action verification is not proven
by merely passing the CSV schema. No network provider is contacted.

The module is not wired to H021 primary selection, to PF001 portfolio
eligibility, or to any automated stock recommendation system.

## Scientific gate to progress

Before proposing H020 to time prospective paper orders, freeze independent
source and observation timestamps, the stock/index adjusted price basis,
universe, trigger thresholds, costs and holding horizon. Evaluate separately
against a next-open no-timing counterfactual using prospective decisions,
including bearish markets and low-liquidity stress.

The original September names (Transrail, Genus Power, etc.) informed the
development and **cannot** serve as untouched validation.

No past result is reclassified as a successful H020 test.
