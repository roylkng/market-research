# HG007-P010: Original NSE Post-QIP Reg31 Shareholding Evidence

Status: SOURCE-DISCOVERY / FINANCIAL BASIS, NOT A FAIR-VALUE OR BUY MODEL.
Created 12 October 2026, before the planned 9:15 IST H021 research
entry observation. This is independent company-level research, not
an H021 score or selection change.

## Why

The prior HG005-D001 Oct 1 valuation used March31 2026 reported
fully diluted shares (403,959,665), which became stale after
INOXGREEN's 29 September QIP added 18,110,473 issued shares.

HG007-P008 corrected two dated **basic** market capitalization
references, but the company-specific current post-QIP fully diluted
share count, promoter encumbrance and share class composition
were still unverified.

Secondary September ownership tables show promoter shareholding
around 53.7%, compared with 56.12% at June. This percentage change
alone is expected from QIP denominator dilution and is NOT a
verified promoter sale. Secondary reports regarding promoter pledges
or encumbrance are not used as original filing evidence.

## Exact original source acquisition

- NSE shareholding pattern API:
  https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN
- Verify NSE master original JSON bytes and SHA-256.
- Do **not** assume the filing must be a standard calendar quarter end:
  an issuer may publish a shareholding pattern as of 29 September
  after a QIP. Only original report dates on/after 29 September
  and with broadcast timestamps already publicly observed are valid.
- Select the most recent eligible report date and latest published
  revision. Duplicate or tied official record identities fail closed.
- Fetch only the exact selected original XBRL URL, from an
  approved official NSE archive HTTPS host.
- Verify content SHA-256, original issuer Symbol, aggregate
  ShareholdingPattern_ContextI basic/diluted facts with exact
  shares unit, and the post-issuance minimum basic count.
- Independently parse issuer-reported promoter, public,
  mutual fund and three encumbrance indicators using the
  established GF001 parser; preserve any incomplete status.

An NSE 403/429 or unrecognized source is **BLOCKED**. No
alternative provider, silent report substitution, future
broadcast leakage, stock-price backfill or credential bypass.

Original successful source bytes and a timestamped receipt
are retained append-only under:

research/hg007/inoxgreen-post-qip-reg31/

Until a complete valid post-QIP original filing is available,
the GitHub workflow retains the blocked capture receipt as
a run artifact and may try again on subsequent October weekdays.

## Precise meaning of share counts

If the original report gives:
- fully paid-up issued shares;
- fully diluted shares including warrants, ESOP and convertible
  securities;

then their difference is an aggregate **dilution-instrument
increment**. Do not automatically label it all as ESOPs or
assume every instrument is vested/in-the-money.

The report date and exchange broadcast are separate from the
capture date; they do not establish that there were no
subsequent capital changes as of a later proposed trade.

Promoter pledge/encumbrance fields are source-reported facts,
not independent evidence of the underlying bank collateral
agreement or absence of later release/additional pledges.

## No portfolio authorization

Even successful original XBRL counts do not prove:
- latest cash proceeds actually held after QIP and WWIL funding;
- WWIL operating cash flow, interest subordination and target value;
- current net debt or fully diluted consolidated EV;
- after-report share/option conversions;
- price target or risk-adjusted expected returns.

The same source cannot retrospectively change the frozen
HG002 28-company cohort or H021 October top decile. Every
portfolio, live-capital and investment confidence flag remains false.

## Files

- src/marketlab/hg007_reg31_check.py
- scripts/acquire_hg007_post_qip_reg31.py
- tests/test_hg007_reg31_check.py
- .github/workflows/hg007-inoxgreen-post-qip-reg31.yml

The GitHub workflow runs once on merge and attempts bounded
source recovery on October weekdays if no complete original
post-QIP report has been accepted.

All original NSE XML bytes, if available, are checked with
independent SHA-256. Missing data remain explicitly missing.
