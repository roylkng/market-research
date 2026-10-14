# HG009 P007: source-bound action hazard control for 300 NSE equities

Frozen method date: October 14, 2026. Earliest paper price reference: October 15. Frozen H5 exit: October 22. **Live capital disabled.**

A future price ratio between NSE original open and close is not automatically economic shareholder total return. Dividend, bonus, split, rights, merger, share conversion and demerger entitlements may invalidate the raw price basis even when the listed symbol/ISIN remains unchanged.

HG009 P007 permanently preserves the original 300 symbol-and-ISIN slots, split into exactly three frozen 100-company groups. It reuses the existing H021 conservative corporate-action source scanner. The scanner can record original NSE API bytes and actual UTC retrieval receipts, detected events/ex-dates, unknown events, incorrect security identity, HTTP failure and source-coverage uncertainty.

**An empty successful corporate-action API response does NOT prove that no issuer events occurred.** Partial pagination/coverage and missing issuer documents mean no completed source clearance. Even when 300 rows report no detected event, the economic total return remains **blocked** until independently verified exhaustive exchange/issuer source coverage and source-backed adjustments.

## Reproduction

Use the deterministic CLI: python scripts/materialize_hg009_p007_actions.py. Check its signed immutable packet: python scripts/materialize_hg009_p007_actions.py --check. Run the tests: pytest -q tests/test_hg009_p007_actions.py.

The initial packet is a **before-outcome missing-source baseline**, not October 15 or October 22 observed corporate-action data. It states that all 300 issuer return clearances are blocked. When original NSE bytes become available, pass the raw file with its hash-bound receipt and a separately named output. Do not rewrite the original packet.

## Required source clearance before any return inference

1. Retain NSE/BSE original issuer filings and independently prove complete exchange actions report coverage for each date, with content-addressed raw bytes and true first retrieval UTC.
2. Link by immutable original symbol+ISIN, not latest name. Require legal entitlement and effective dates and financial value, including shares, stock splits, rights, dividends, demergers and investor distributions.
3. Preserve missing or ambiguous issuer observations as null in the predeclared 100-name denominator, never as zero share price return or an event-free clearance.
4. Match shareholder total-return basis with an appropriate index basis. Nifty500 price index is not Nifty500 total-return index.
5. Validate costs, after-tax execution, current order-book depth and factor/style baseline separately. A single observed 300-company cohort cannot establish causal or repeatable AI-generated stock-market alpha.

No P007-adjusted economic returns or capital deployment are permitted at this stage. P006's original price-only H1/H5 monitoring remains distinct.
