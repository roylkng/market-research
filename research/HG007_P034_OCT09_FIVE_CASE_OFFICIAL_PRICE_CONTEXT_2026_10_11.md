# HG007-P034: One Official NSE 9 October Price Source for Five Hidden-Gem Cases

Frozen implementation date: **11 October 2026 IST**, before the
next 12 October 2026 trading session. Status: **past-session source
observation only, not a new return-predictive hypothesis or stock ranking**.

## Why this is the next missing piece

The existing HG007-P033 five-case underwriting board still has
1 October 2026 *historical* closing prices. That matters especially
for special-situation stocks whose observed October prices moved sharply.

The system already has an immutable SS002-P007 official NSE
9 October UDiFF observation for INOXGREEN and SAMBHV, but not
independently anchored October 9 market context for the full
five-company HG005 family:

ANANTRAJ, DEVX, INOXGREEN, NPST, SAMBHV.

P034 reuses the **same exact original NSE 9 October full-market
UDiFF bhavcopy ZIP**, pinned byte-for-byte by SHA-256:

    8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c

Official source URL:

https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261009_F_0000.csv.zip

If a server returns anything other than the exact original source
bytes from SS002-P007, acquisition is **blocked**. No Yahoo,
substitute price, invented ISIN, alternate-day close or synthetic
capitalization is admitted.

## Preconditions and source comparison

- Pin original HG005-D001 October 1 five-symbol context and Git blob SHA.
- Pin original SS002-P007 October 9 official source and Git blob SHA.
- Pin latest HG007-P033 five-case economic-source-readiness and Git blob SHA.
- Preserve each original symbol and payoff model. A date update does
  not change the chosen candidates or imply trading authorization.
- Parse the original NSE EQ UDiFF STK rows only, requiring exact date/source.
- Refuse missing, duplicate, inconsistent or malformed equity records.
- Recheck original P007 recorded INOXGREEN INR128.92 and
  SAMBHV INR160.41 as October 9 official closing prices.
- Record original NSE ISIN with each symbol, open/high/low/close,
  traded volume, turnover and trade count. Independent ISIN
  joins to shareholding and corporate action filings still need
  formal approval per issuer.
- Record raw October 1 to October 9 observed price change only as
  a **date-reference difference**, not portfolio realized return.

## Scientific limits

Neither an official closing auction price nor daily traded
volume is an executable investor fill at that price.

Five original HG005 October 1 share counts were not all proven
current on 9 October. In particular, INOXGREEN September 29
fully diluted shares and promoter pledge data were first published
by NSE on **8 October**, so they cannot be backfilled as knowledge
available at an earlier October 1 investor decision.

For all five stocks, subsequent share issues, rights/splits,
dividends, debt, cash funding, completion probabilities and
intraday liquidity require separate verification.

P034 does not compute a current fully diluted market cap,
enterprise value, post-transaction fair value, Nifty 500 excess
return, profit target, probability-weighted payoff, H021
prospective return or PF001 position.

## Implementation

- src/marketlab/hg007_five_case_market_oct9.py
- scripts/acquire_hg007_five_case_oct9.py
- tests/test_hg007_five_case_market_oct9.py
- .github/workflows/hg007-five-case-oct9-source.yml

When the original NSE file is accessible, the workflow retains
the whole exact ZIP, its SHA and the dated five-case source-only
packet under:

    research/hg007/oct09-five-case-market/

When HTTP 403/429 or a SHA mismatch occurs, the run preserves
an explicit unsuccessful receipt, never fabricating a market
observation or company target value.

On-merge acquisition plus bounded October retries are enabled.
Source success must be verified from the actual Git artifact,
not assumed from successful workflow status.

**No current stock recommendation, return hypothesis promotion,
portfolio entitlement or live capital allowed.**
