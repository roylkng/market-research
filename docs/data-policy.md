# Data policy

The largest threat to this project is not model capacity. It is historical-data leakage.

## Point-in-time requirements

Production-grade research must preserve the information set that was actually available at the decision timestamp.

For every event, retain where applicable:

- original exchange filing URL and release timestamp
- raw filing bytes / content hash
- original reported values
- later restatements as separate versions
- pre-event consensus snapshot and timestamp
- corporate-action state at the time
- market price source and timestamp
- pre-auction and official closing prices when closing-auction effects matter

## Raw data

Raw inputs are immutable. New corrections create new versions. Never overwrite history silently.

`data/raw/` is ignored by default because licensed or large data should not be committed accidentally. Explicit small, redistributable research fixtures may be committed under `data/fixtures/`.

## Missing data

Missing data stays missing.

Examples of prohibited substitutions:

- estimating an opening fill from OHLC data
- treating today's restated quarterly table as guaranteed point-in-time history
- substituting a futures close for a cash-equity close
- deriving analyst consensus from a source published after the result

## Provenance

Every normalized observation should eventually expose:

- `source_url`
- `source_timestamp`
- `retrieved_at`
- `raw_hash`
- `transform_version`

## Experiment reproducibility

Every experiment record should identify:

- dataset version / content hash
- code commit SHA
- hypothesis version
- environment / package lock when introduced

## Current feasibility-pilot limitation

The September 2026 feasibility pilot uses source-linked consolidated historical quarterly tables viewed after the fact. Those values are sufficient to test whether an idea is worth deeper investigation, but they are **not** sufficient to claim a production-grade point-in-time backtest.
