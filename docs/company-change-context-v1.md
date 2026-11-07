# CC001 P007: historical evidence and dated price context

This connects a reported operating/cash change to historical context and the
valuation assumptions a dated market price requires. It does not invent
normalized owner earnings, share counts or forward-growth estimates.

## Implemented

The module reuses the persisted current financial anchor and existing NSEClient.
It discovers prior issuer filings with bounded pagination and exact response-byte
retention, then reads up to four original XML/HTML documents per issuer. Retrieval
prioritizes the exact year-ago end and nearby annual dates. A March end never
proves that a period is annual. Original context dates and scope control joins.
Historical evidence is observed now, not backdated into a prediction experiment.

Reported year-ago figures retain both source documents. Different disclosures
are labelled cross-source, not implicitly restatement-reconciled. Additive
trailing flows use annual + current interim - exact prior interim. EPS and shares
are never added or subtracted. Missing cash inputs stay missing.

The preferred price input is the official NSE quote response, with symbol,
ISIN, EQ series, source timestamp and finite-price validation. If that public
endpoint fails, a separate official NSE CM UDiFF archive can supply a session
close. The first live run returned HTTP 403 for all three quote API requests.
Historical filings succeeded. No access check is bypassed and no price is guessed.

`company_change_prices` validates the original ZIP member name, source CSV date,
NSE/CM/STK/EQ classification, exact symbol/ISIN, positive close and positive volume.
It probes at most eight dated archive paths. A retrieved invalid file does not
cause a search for older convenient prices. Session-close evidence retains only
the actual DATE precision and observation time, not an invented 15:30 timestamp.
The newest retrieved archive is not a certified trading-calendar assessment.

Corporate-action responses are retained separately. A split, bonus, rights issue
or unclassified purpose after the annual EPS period end blocks the ratio. Earlier
corporate actions are not automatically applied a second time. Dividends alone
do not change the share denominator. Empty action responses are not represented
as independent proof that no issuance, dilution or restatement exists.

## What the price calculation means

When required observations pass, show price / last full-year REPORTED diluted
EPS. This is not normalized, trailing or forecast P/E. Reverse a transparent
five-year 15% price-return hurdle at exit P/E assumptions of 12, 15 and 18:

    required_growth = ((price / reported_annual_eps) * 1.15**5 / exit_pe)**(1/5) - 1

This is a sensitivity, not a prediction. No growth rate, exit multiple, fair value
or multibagger probability is claimed as learned. Dividends, investor taxes,
transaction costs and future share-basis changes are excluded. A known rejected
current extraction cannot supply an attractive ratio. Quotes older than seven
calendar days are blocked. No card approves an investment or trade.

## Operation

```bash
python -m marketlab.company_change_context --workspace .marketlab/cc001 --limit 3
python -m marketlab.company_change_context --workspace .marketlab/cc001 --symbols CONCOR KRSNAA UPL --limit 3
```

Without an explicit list, select never-enriched or least-recently enriched issuers
already present in the workspace. Prefer consolidated anchors when available.
Do not mix standalone and consolidated history. The named three-issuer command
is a regression/integration case from the preceding cash analysis, not a portfolio.

Immutable context records live in the workspace database. Content-addressed
reports live under reports/context and are included in existing checkpoints.
Optional --output-prefix writes latest-view HTML/JSON exports with an explicit
report date. Original responses remain in the source byte store.

The existing daily workflow rotates through three issuer-context updates, with
at most four historical originals per issuer, in addition to its unchanged
40-document discovery batch. The schedule is unchanged. It persists context
results and state even when price/history enrichment reports partial failure.
Current status/count/hash are cleared on failure rather than promoting an old
report as fresh. This bounded pilot is not a promise of current valuation
coverage for the whole market.

## Verification boundaries

Tests cover prices, exact dates, issuer/scope, nil inputs, corporate actions,
nonpositive bases, prior-period ordering, trailing arithmetic, quote timestamps,
ZIP/date/identity mismatches and checkpoint-safe daily integration. A separate
live-source workflow restores a copy of cc001-state. It writes no state branch
and auto-approves no facts. It retains the exact code alongside original evidence.

No model endpoint, paid inference, credentials, broker or commercial service is
created. No frozen H-series/HG009/AE001 cohort, outcome or capture rule changes.
Source/licensing permissions remain a commercial-launch requirement. Public
repository state must not receive private documents or restricted paid-feed data.

Normalized owner earnings, current fully diluted shares, multi-year seasonality,
independent semantic labels and genuine prospective performance are distinct
remaining requirements. A successful source-arithmetic replay does not establish
investment alpha or independent extraction accuracy.

Primary references consulted:
- NSE corporate actions: https://www.nseindia.com/companies-listing/corporate-filings-actions
- NSE official daily reports: https://www.nseindia.com/all-reports
- XBRL period contexts: https://www.xbrl.org/dates-in-xbrl/
