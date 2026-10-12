# HG007-P042: Original NSE Series Classification for 16 Missing EQ Observations

Frozen source-only investigation: **12 October 2026 IST**.
No alpha, price targets, research exclusion, execution or capital authorization.

## Why this study is necessary

HG007-P041 independently re-parsed 20 original NSE full-market UDiFF
sources for all 28 originally selected outside-U001 hidden-gem names.
Twenty-session EQ coverage was fully valid for 26 names. Two had a
missing **EQ-series** row:

- ORBTEXP: 9 of 20 completed NSE EQ sessions, **11 EQ-row gaps**.
- RETAIL: 15 of 20 completed NSE EQ sessions, **5 EQ-row gaps**.

A missing EQ row is **not** the same as zero trading, security
suspension, delisting, lack of liquidity across other series, ticker
change or a stock-specific negative alpha signal. Those claims require
independent official exchange classification and date-aware legal
evidence.

## Correct scientific method

Reuse *exactly* the original full-market raw files already saved for
HG007-P036/P041, retaining their official NSE source SHA-256, URL and
historical completed session chronology. No additional live source,
different price vendor or free-form name matching.

Anchor the exact, unchanged P041 28-company packet by source Git blob
a01b9823a29cdfe94f5e2f21e84159b66a949c75 and require its complete
20-session audit status. Only original two frozen missing-company names
and their 16 missing EQ dates are reviewed.

For each of the original source dates, inspect the entire source
CSV with the official cash-market CM/STK/NSE identity filters,
**including all stock security series, not only EQ**.

For every missing EQ date, retain original same-symbol alternative:
- security series (such as BE, BZ or other source-provided label);
- ISIN, compared with the documented EQ-series ISIN;
- reported trading volume, traded value and executed transaction
  count when numeric/valid;
- explicit absence of any same-symbol CM/STK row where appropriate;
- source day and original whole-market raw-file SHA.

An alternate series may have different settlement rules, trade-to-trade
restrictions and market behavior. Its turnover cannot automatically be
promoted to an NSE EQ fill or used to complete a 20-day EQ turnover
series. An ISIN mismatch or renamed symbol needs a separate dated
corporate-action and exchange-identity investigation.

The original 26 source-complete companies remain unchanged. No
previously failed company is silently removed or given invented
trading values.

## Reproduce / source gate

- Analyzer: src/marketlab/hg007_eq_absence_review.py
- CLI: scripts/review_hg007_missing_eq_series.py
- Tests: tests/test_hg007_eq_absence_review.py
- Workflow: .github/workflows/hg007-original-eq-gap-review.yml
- Result after merge:
  research/hg007/twenty-session-liquidity/eq-absence-series-review-v1.json

Offline original-data reproduction:

    python scripts/review_hg007_missing_eq_series.py \
      --out /tmp/hg007-missing-equity-series.json

This is a **retrospective source interpretation** from already-known
historical exchange trading data. Neither NSE volume nor an apparent
series tag proves an order was executable at a quoted open, nor
does it provide an investment thesis.

All HG005/HG006 valuation, completing-transaction, corporate action,
future returns, portfolio eligibility and live-capital gates are
unchanged and disabled.
