# H021-P024: Original NSE Muhurat Sunday Source Collection

**Protocol registered 22 October 2026, before Sunday 8 November trading.**
**Classification:** future exchange-source acquisition, NOT a trading strategy,
not the 20-session H021 return, and not a capital authorization.

## Why this extension is necessary

Original H021-P003 froze its October 9 earnings-revision selection and
October 12 prospective opening-price reference. Original H021-P008
daily-market-price collection deliberately accepts only the fixed NSE-CM
calendar, whose weekday sessions excluded November 8 because the Muhurat
hours were not yet known.

The separately reviewed P023 amendment proves from NSE original circular
**NSE/CMTR/76941**, published 19 October and archived in Git 20 October,
that Sunday **8 November 2026 is H021's actual twentieth market session**.

The ordinary H021 P008 parser and resolver remain frozen and unchanged;
their failure to admit Sunday is not solved by editing the original
calendar, altering source records, or inventing an alternative exit.
This P024 is an explicitly *new*, narrow Sunday source collector.

## Strict official sources

The only admissible future data are exact original official NSE reports
for **2026-11-08**:

- CM-STK-EQ original UDiFF archive:
  https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261108_F_0000.csv.zip
- NSE Nifty 500 original price-index daily report:
  https://archives.nseindia.com/content/indices/ind_close_all_08112026.csv

These URLs are declared source targets, **not a claim that reports have
already been published or will necessarily be available on the URLs**.

All sources must be fetched after the conservative **16:15 IST**
(10:45 UTC) NSE trade-modification cutoff on 8 November. NSE's circular
distinguishes continuous market close (non-CAS 15:30 IST) and final
closing auction matching (CAS 15:35 IST); this collector does *not*
assert that the relevant stock-specific auction close bases have
been independently reconciled.

Any HTTP 401, 403, 429 is recorded as an ACCESS_BLOCKED original source,
with NO bypass or redirect; HTTP 404 means NOT_PUBLISHED; unrecognized
responses and malformed original ZIP/CSV stay failed or incomplete.
No alternate vendor, date, close, price or index is inferred.

## Scientific and source-integrity gate

Before every fetch, the collector verifies:

- immutable H021 P003 October 9 first cohort/October 12 first entry,
  original 100-member U001, and the ten original selected symbol/ISIN
  pairs, against pinned Git blob SHA;
- independently source-validated P023 signed NSE circular amendment,
  with Sunday November 8 as the exact 20th session;
- original NSE report URL and UTC capture timestamp after all actual
  source-publication and exchange cutoffs;
- exact stock EQ series, symbol AND ISIN for all ten original issuers,
  with independent original NSE Nifty 500 price-index parsing.

The packet only records original raw NSE OHLC values, which are
unadjusted **price observations, NOT executed fills or shareholder
total-return positions**. A missing stock, wrong ISIN, malformed index,
wrong source day, unavailable source or price parse failure remains
explicit, never zero-filled or excluded as a presumed winner/loser.

The record flags all of these as **FALSE** even when all ten rows
and the Nifty 500 price-index row are present:

- 20-session return/benchmark excess computed
- actual execution, liquidity and costs verified
- CAS/non-CAS security-specific close basis verified
- dividend, bonus, split, rights or demerger total-return basis verified
- official 2027 H60 calendar verified
- probability-weighted alpha or buy recommendation
- portfolio or live-capital permission

H021 H60 remains explicitly blocked with **four additional official
2027 market sessions required** after including Sunday.

## Scheduled implementation and custody

- Core: src/marketlab/h021_nov08_source.py
- Collector: scripts/collect_h021_nov08_source.py
- Regression: tests/test_h021_nov08_source.py
- Workflow: .github/workflows/h021-p024-nov08-original-source.yml
- Future evidence root:
  research/prospective/h021/special-sessions/2026-11-08/

The workflow tests all source, identity and no-capital invariants during
PR review and on main pushes; the source acquisition **does not run**
before November 8.

The first original NSE source attempt is scheduled after the 16:15
IST cutoff. Limited later source-publication recovery checks are
scheduled November 9–13 with **at most five immutable automatic
attempt receipts**. Each attempt persists its real UTC acquisition
timestamp and any original source raw bytes SHA-addressed.

Only source-complete reports are sealed once under:

  research/prospective/h021/special-sessions/2026-11-08/2026-11-08-original-ohlc-v1.json

Partial or denied source attempts have separate immutable receipts,
without replacing the original date or asserting a return.

The workflow also retains original response/attempt artifacts on
GitHub Actions. Scientific source-file and prospectively frozen
cohort changes during publication abort the push rather than
silently rewriting a prospective clock.

## Residual original-evidence needs

After 8 November, stock-specific auction eligibility must be
independently checked against NSE's original security records, and
dividend/share-entitlement cases such as VEDL must be evaluated
from corporate-action filings before any economic outcome can be
released. A later adapter may reuse P024 original Sunday ZIP/index
with HG009's **separately frozen October 15** 300-security cohort,
but **this P024 does not change or calculate HG009 outcomes**.

Any realized H021 economic alpha, stock recommendation and
50%-annual-return ambition remain unproven at this stage.
