# HG007-P041: All 28 Hidden-Gem Companies, 20-Sessions of Original NSE Turnover

Prepared **12 October 2026** as a retrospective research evidence diagnostic.
**NOT** an ex-ante prediction, live trading strategy, expected return, or
company investment ranking.

## Why this gap matters

The original HG002-D001 28 companies were selected by frozen full-market
nonfinancial/event/asset/governance evidence. Subsequent HG007-P035/P036/P037
measured detailed liquidity only for **five** later payoff-framework names.
That unintentionally leaves the other 23 original candidates without a
consistent measure of how limited actual cash-market turnover might have
been. Selecting companies solely for exciting operating stories while
ignoring a lack of turnover makes even a small-cap thesis hard to execute.

Do not falsely turn this into an alpha trial: this period was already
known when the hidden-gem screen was assembled.

## The source universe is independently fixed

- Original cohort: research/hg002-d001-result-v1.json,
  Git blob SHA e4313bd333595fce068dc8fd0882dec16f2ec8b6.
- Exactly 28 original names in the original order, including cancelled,
  completed, indirect and text-pending transaction cases.
- Historical market source and company control:
  research/hg007/twenty-session-liquidity/twenty-session-liquidity-v1.json,
  original Git blob f2e3d33288a432326235bd72db1911bc17b742ea.
- Use the **same original complete 20 whole-market NSE CM UDiFF ZIPs**
  previously collected, from 10 September through 9 October 2026.
- Dates and session closure must match the already source-pinned NSE
  2026 CM calendar. The October 9 original was previously verified in
  HG007-P035; all other 19 original ZIPs retain matching daily receipts,
  official URLs, SHA-256s and actual post-close acquisition timestamps.

No new market provider, paid API, stock chart scraper, subsequent quotes
or temporary price reconstruction is involved.

The original **five** company turnover rows must independently reproduce
from the 20 raw ZIPs, matching per-day symbol, ISIN, OHLC, volume,
executed transaction count and turnover. One inconsistent control is a
research integrity failure for the whole 28-company report.

## What is recorded per company

For every one of the 28 fixed symbols, preserve the state of every one
of the 20 official days. An NSE EQ row is considered verified only if:

- precisely one EQ/ISIN row appears for that symbol on that date;
- price/volume/value and trade count pass finite-positive and internal
  OHLC/VWAP/quantity checks;
- no more than one distinct ISIN appears across verified observations;
- dates cover all 20 original completed sessions exactly.

A missing market row is NEVER interpreted as a zero rupee turnover.
Changed ISIN, contradictory rows, zero/nontrading source quantities and
missing sessions remain blocked, preserving exact dates. For an
incomplete 20-session identity, no 20-session median is published.

For a fully observed symbol, describe:

- Median, minimum, maximum, nearest-rank p10 and p25 daily **value traded**.
- October 9 original value traded.
- Hypothetical INR 1 lakh and INR 10 lakh divided by **1% of its
  historical median daily value traded**.

The last quantities are **descriptive ratios, not the number of trading
days needed, market-impact forecasts, achievable tickets or evidence
any order could fill at the NSE open**. One percent is a declared
comparison reference, not a guaranteed accessible fraction of trades.

## Why it affects future research

The existing original five-company study already found that DEVX had
a 20-session median daily value traded of only about **INR 0.408 crore**,
and that INR 10 lakh is roughly **24.48 times 1%** of that historical
median. That makes depth/participation diligence particularly relevant
before proposing a meaningful position. Those numbers are not
execution projections.

For all remaining 23, the P041 generated result enables **same-source**
liquidity review alongside genuine company cash-flow, dilution,
governance and transaction conditions. An attractive payoff sensitivity
with poor source coverage or historical turnover remains uninvestable
until independently verified.

## Source retention, replay and limitations

- Module: src/marketlab/hg007_28_liquidity.py
- Reproducer: scripts/build_hg007_28_liquidity.py
- Tests: tests/test_hg007_28_liquidity.py
- GitHub job: .github/workflows/hg007-all-28-liquidity.yml
- Immutable after merge:
  research/hg007/twenty-session-liquidity/twenty-session-28-stock-v1.json

Run the offline replay:

    python scripts/build_hg007_28_liquidity.py \
      --output /tmp/hg007-original-all28-liquidity.json

The output is SHA-sealed. The original five source families, 20 original
NSE raw files and cohort identities are validated without altering any
original HG005/HG006 underwriting or prior H021 prospective experiment.

**Not authorized:** prediction of price appreciation, liquidity
forecast, portfolio position size, bid/ask or market impact estimates,
execution probability, alpha discovery claim or live capital. The
separate expected-return / quality / valuation / survival gates still
need independent official evidence.
