# CC001 P007: historical evidence and dated price context

This adds the missing connection between a reported operating/cash change and
the valuation assumptions a current price requires. It does not fabricate
normalized owner earnings, shares or forward-growth estimates.

## Completed engineering path

- Reuse the persisted current financial anchor and existing NSEClient.
- Discover prior issuer filings with bounded pagination, retaining exact response
  bytes. Fetch up to four original XML/HTML documents per issuer, including the
  exact year-ago reporting end when available. Date targets prioritize retrieval
  only. A March end is never assumed to prove that a statement is annual.
- Parse exact financial context dates and accounting scope using the existing
  original-document adapters. Historical documents are observed NOW, not backdated.
- Compare reported revenue/profit/cash with the exact prior-year period. Different
  disclosures are labelled as cross-source, not implicitly restatement-reconciled.
- Compute additive trailing flows as annual plus current interim minus the exact
  prior interim when all three periods fit. EPS and shares are never added or
  subtracted. Missing cash values remain missing.
- Capture an exact NSE quote response and validate symbol, ISIN, EQ series,
  timestamp and positive finite price. Last traded price is not mislabelled as
  an executable closing price. Quotes older than seven calendar days block ratios.
- Capture corporate-action responses. A known split, bonus, rights issue or any
  unclassified action blocks price/EPS comparisons pending share-basis review.
  Dividends alone do not change a denominator. An empty response is not claimed
  to independently prove no issuance, dilution or restatement.
- Show price divided by the last full year's reported diluted EPS only when the
  required observations pass. This is NOT a normalized, forward or trailing P/E.
- Reverse the return hurdle: what EPS growth over five years would be needed to
  earn 15% annualized price appreciation at exit P/E assumptions of 12, 15 or 18?
  No exit multiple, growth rate, fair value or probability is claimed as learned.

The reverse calculation is:

    required_growth = ((price / reported_annual_eps) * 1.15**5 / exit_pe)**(1/5) - 1

Dividends, investor taxes, costs and future share-basis changes are excluded.
This is an explicit sensitivity, not a forecast or investment approval.

## Execute

```bash
python -m marketlab.company_change_context --workspace .marketlab/cc001 --limit 3
```

Without an explicit issuer list, the module rotates through never-enriched or
least-recently enriched issuers already present in the workspace. Consolidated
anchors are preferred when present. Standalone data are not mixed into a
consolidated history. An explicit list can be used for a review case:

```bash
python -m marketlab.company_change_context --workspace .marketlab/cc001 --symbols CONCOR KRSNAA UPL --limit 3
```

Those three are integration examples drawn from the preceding cash review, not
an investment shortlist. Neither this module nor the comparison tests change
frozen H-series, HG009 or AE001 experiments, capture schedules or outcomes.

Immutable per-run context records live in the workspace database and dated,
content-addressed HTML/JSON reports live under reports/context. Original source
responses and documents use the existing byte store. Failed retrievals remain
explicit. No production provider endpoint, secret, paid API call or broker is
introduced. The original research workflow remains independently usable.

## Evidence standards

Software tests exercise source timestamps, quote identity, stale prices,
corporate actions, period matching, restatements, units, negative bases and
trailing-flow arithmetic. The separate live-source workflow restores a COPY of
the existing workspace, then retrieves actual documents and market context.
It does not push its state or auto-approve facts. All outputs remain research-only.

A successful network request does not establish independent semantic accuracy.
The current-price ratio does not resolve normalized owner earnings, future
capital needs or current diluted-share reconciliation. Prospective alpha,
independently labelled model accuracy and licensed multi-user hosting remain
separate acceptance requirements, not successes implied by passing these tests.

Primary references consulted:
- NSE corporate actions: https://www.nseindia.com/companies-listing/corporate-filings-actions
- NSE equity market quote notes: https://www.nseindia.com/market-data/live-equity-market
- XBRL date contexts: https://www.xbrl.org/dates-in-xbrl/
