# L002: independent liquidity-conditioned momentum control (not H004)

Created 2026-10-17. Status: noncanonical diagnostic; no trade suggestions, no alpha claims and no forward outcomes.

**Purpose:** Test the Indian-market literature hypothesis that liquid stocks can exhibit stronger momentum continuation, while illiquid stocks may exhibit stronger short-term reversal. This must be a separately preregistered challenger, NOT a modification of H004's frozen earnings/catalyst thresholds.

## Implemented

Code: src/marketlab/l002_liquidity_momentum.py.

- Require at least 252 observed, uniquely identified session records with the same symbol and ISIN, positive adjusted closes and nonnegative traded value.
- Deny information first available after the exact decision cutoff, an unknown price-adjustment basis, mismatched ISIN, future-dated sessions, source hashes of malformed form, duplicates or incomplete history.
- Compute a predeclared *descriptive* 12-minus-1 momentum using t-252 to t-21, skipping the most recent 21 completed sessions. This does not optimize a threshold or use subsequent returns.
- Compute median traded value over the latest 20 observed sessions, and group using H004-style comparative bands: Rs 2 crore daily primary, Rs 25 lakh discovery, below discovery threshold. H004 itself is unmodified.
- Emit NON_CANONICAL_PIT_MOMENTUM_DIAGNOSTIC, explicitly flags source original bytes as not independently verified, and denies return forecasts, investment ranking and capital permission.

## Required next prospective test before any signal promotion

1. Preserve canonical H004 and its outcomes untouched.
2. Capture fully point-in-time original daily equity prices, traded value, adjustment version, NSE verified session calendar, first availability timestamp and universe membership.
3. Freeze formation windows (6/12 months, optional skip-month alternatives) *as separate registered variants before measuring new outcomes*. This initial candidate uses 252 sessions with a 21-session skip; do not tune based on observed results.
4. Evaluate 20/60/120-session after-cost returns, size/sector and liquidity matched, versus simple momentum, H004 catalyst watchlist and a no-signal baseline. Include false discoveries and trial count, nonexecutability due to upper circuit or limits, and market-impact costs.
5. Report results in multiple prospective periods and liquidity buckets. Claim no edge if it loses to simple momentum after costs.

## Limitations

A submitted source digest and adjustment status are upstream assertions, not proof original exchange bytes were independently replayed. The supplied calendar dates are not checked against actual NSE holidays in this prototype. This feature *alone* cannot create an investable trade or validated backtest.

Tests: pytest -q tests/test_l002_liquidity_momentum.py

Full CI required prior to merge. No change to H004 selection, price filters, prospective outcomes or alpha ledgers.
