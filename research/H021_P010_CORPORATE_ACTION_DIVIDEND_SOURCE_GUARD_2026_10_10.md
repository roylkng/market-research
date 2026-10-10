# H021-P010: Conservative NSE Share-Action and Dividend Risk Screen

Frozen as infrastructure/protocol before H021 market-price outcomes:
**10 October 2026 IST**.

## Risk being closed

The original market-data helper in this repository can yield a nominal
"READY" when an NSE action response contains a split/bonus event or when
an unsupported response is treated as an empty set. This is **not**
evidence that an unadjusted share-price return is comparable over a
multi-session period.

Even complete-looking NSE corporate-action API responses cannot establish
independently reviewed, exhaustive window coverage merely because a JSON
array was empty. Some endpoints are paginated, delayed, or incomplete;
certain effective share changes may appear in separate exchange or
company filings. Cash dividends are absent from raw closing-price
appreciation and must be treated separately.

A raw Nifty 500 **price index** is not the investable **total-return index**.

## Protocol and original source identity

P010 screens source bytes and is **not** a certificate of adjustment.

Each proposed source receipt must include:

- exact URL rooted at the HTTPS NSE corporate-action endpoint;
- source UTC capture timestamp, after the requested evaluation window
  has actually ended;
- original raw JSON bytes, HTTP 200 and matching SHA-256;
- explicit interval start and end, symbol and frozen U001 ISIN identity.

Any unsupported URL, wrong raw hash, malformed JSON schema, future window,
blocked source, undated notice, unknown corporate event, mismatching
identity, or incomplete source **fails closed**.

Candidate share-basis hazards include share splits, bonuses, rights,
demergers, mergers, schemes, preferential allotments, capital reductions,
buybacks and warrant conversions. Dividends are separately classified
as cash income.

P010 treats such strings conservatively as hazards, not as complete
transaction classification. An unrelated corporate action is not a
valid stock split merely because a keyword appears.

## What is guaranteed

Every H021 selected stock retains:

- raw-price-return eligibility: **FALSE**
- exhaustive corporate-action coverage verified: **FALSE**
- share-change adjustment factors verified: **FALSE**
- cash dividend/total-return treatment verified: **FALSE**
- outcome returns opened: **FALSE**
- portfolio and live-capital permission: **FALSE**

Even an empty valid NSE response is
SOURCE_SCREENED_COVERAGE_NOT_CERTIFIED rather than "all clear".

The explicit require_h021_price_basis_clearance gate **always rejects
a P010-only source screen**. A subsequent, separately frozen source
coverage, dividend and adjustment-factor audit must approve the actual
horizon before a researcher may open a 20/60-session return calculation.

That later audit must reconcile effective share/ISIN identity changes,
the correct ex-dates, cash dividends, stock-price adjustment factors,
matching Nifty 500 index/TRI return basis and transaction costs.

## Replayable commands

Without an original source:

    python scripts/screen_h021_corporate_actions.py \
      --interval-end 2026-10-12 \
      --out /tmp/h021-action-screen.json

With a previously retained official source and provenance:

    python scripts/screen_h021_corporate_actions.py \
      --interval-end YYYY-MM-DD \
      --raw-json /path/to/nse-original-response.json \
      --source-url 'https://www.nseindia.com/api/corporates-corporateActions?index=equities' \
      --captured-at-utc 2026-XX-XXTXX:XX:XXZ \
      --out /tmp/h021-source-hazard.json

No network activity is performed by the screening script and no
exchange data are fabricated. Future capture is a separate sourced task.

Regression suite:

    pytest -q tests/test_h021_corporate_action_guard.py

## Scientific boundaries

This is not an investment research result and does not re-rank H021's
ten original stocks or change any prospective EPS signal. It also does
not estimate company-level expected returns, alpha, or complete missing
official evidence.

P010 is a **safety precondition and an honest blocked state**, not
a workaround for the unresolved November Muhurat session or the
unpublished official 2027 trading calendar.
