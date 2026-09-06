# Data

This repository does not assume that current web tables equal historical point-in-time data.

## Directories

- `data/raw/` — local immutable source captures. Ignored by default.
- `data/normalized/` — local normalized datasets. Ignored by default.
- `data/fixtures/` — small redistributable fixtures used by tests or published experiments.

## Published fixture

`data/fixtures/h002_feasibility.csv` contains the 24 observations from the September 6, 2026 H002 historical feasibility pilot for which the delayed entry and exit price pair was independently verified in the pilot workbook.

It exists for three reasons:

1. make the CLI examples runnable after a fresh clone,
2. allow the published H002 statistics to be recomputed,
3. give future data pipelines an explicit example schema.

The fixture is deliberately tagged by context as **feasibility-only**. It is not a production-grade point-in-time dataset because the historical accounting inputs came from source-linked consolidated tables viewed later rather than a complete immutable archive of the original filing state.

Do not use this fixture to authorize live capital.

## Production-grade event record

A future earnings observation should include at least:

```text
company_id
symbol
event_type
filing_timestamp
source_url
raw_hash
reported_period
reported_eps
reported_revenue
reported_operating_profit
reported_margin
consensus_timestamp
consensus_eps
consensus_revenue
price_day_minus_2
entry_timestamp
entry_price
exit_timestamp
exit_price
benchmark_entry
benchmark_exit
corporate_action_state
transform_version
```

Where consensus is unavailable, the expected-earnings model must be specified before the result and versioned.

## Licensing

Do not commit licensed market data unless redistribution is permitted. Store reproducible acquisition metadata and hashes instead.
