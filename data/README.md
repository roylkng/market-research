# Data

This repository does not assume that current web tables equal historical point-in-time data.

## Directories

- `data/raw/` — local immutable source captures. Ignored by default.
- `data/normalized/` — local normalized datasets. Ignored by default.
- `data/fixtures/` — small redistributable fixtures used by tests or published experiments.

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
