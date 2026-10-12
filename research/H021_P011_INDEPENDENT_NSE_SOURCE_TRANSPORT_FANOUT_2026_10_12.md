# H021-P011: Preserve Full-Market NSE Source Despite a Missing First-Cohort EQ Row

Frozen source-integrity amendment: **12 October 2026, after the first
H021 opening auction but before any 13 October P008 daily source capture**.
No stock-selection, entry-date, ranking, holding-period or outcome change.

## Bug

P008 correctly marked the original first H021 ten-company observation
SOURCE_INCOMPLETE when one of its ten stock rows was missing, its
ISIN mismatched, or its source could not be verified.

However, its first implementation wrote a permanent daily market
packet **only** if the original ten and the Nifty 500 benchmark were
all present. P009, intended to fan out the *same raw official full-market*
NSE UDiFF file to future monthly H021 P005 cohorts, also accepted only
a packet whose **original ten** were complete.

This is an invalid coupling. An absent VEDL stock row, for example, does
not make a source-bound Reliance or any other independently selected
stock in the same original official UDiFF ZIP unavailable. This could
create avoidable, first-cohort-dependent missing data across subsequent
unrelated prospective experiments.

## Corrected source evidence boundary

The original P008 packet keeps its unchanged classification, exact ten
selected names, original missing-row markers, immutable original URL,
content hashes, original Nifty 500 index, post-market-close dates and
all no-capital/no-return flags.

A **separate, strictly validated transport readiness gate** now requires:

- Exact original NSE UDiFF and original Nifty 500 index report URLs
  for that verified 2026 session, HTTP 200 and content SHA-256s.
- All original P008 source-record/canonical packet SHA checks.
- Official indexed Nifty 500 price index parsed, positive, and
  explicitly **not a total-return index**.
- At least one verified first-cohort EQ row to establish the archive
  parses; all ten original identities and row states must reconcile.
- Every originally missing/invalid EQ stock row retains null prices,
  an explicit error state and no execution/corporate-action clearance.
- The original ten remain SOURCE_INCOMPLETE unless **all** ten
  individual EQ rows passed; no false promotion to complete.

When these conditions hold, P008 may commit an immutable dated
SOURCE_INCOMPLETE packet alongside both original content-hashed source
files. The first cohort is **still missing its required prices**.

The daily resolver records that calendar date separately as
first_cohort_partial_but_transport_ready_sessions and proceeds to
the next verified completed session rather than repeatedly recapturing
identical raw reports. Incomplete fetches or an invalid/missing Nifty
500 row still use the original bounded retry/missing-source mechanism.

P009 accepts these strict **transport-ready** partial-first-cohort
packets and re-parses each new cohort's independently frozen symbol/ISIN
from the same original raw NSE bytes. A new cohort is COMPLETE only
if every stock in *its own* frozen selection has a verified EQ row.
Every absent name retains null prices and INCOMPLETE_NO_SUBSTITUTION.

No late price substitution, alternate provider, portfolio treatment
or future return is permitted.

## Chronological and scientific protection

- H021 P003's October 9 first cohort, October 12 official entry
  observation, primary 60 completed sessions, secondary 20 completed
  sessions and Nifty 500 benchmark family are unchanged.
- P005 future cohort intent MUST have been frozen before its next NSE
  open with original symbol, ISIN and source hashes.
- The original frozen special-session/calendar blockers remain.
- Corporate actions, dividends, benchmark price-vs-TRI, bid/ask
  liquidity and executable fills remain separate unresolved gates.
- Source transport is not profitability or evidence of investable alpha.

## Code and CI

- src/marketlab/h021_daily_prices.py
- src/marketlab/h021_cohort_source.py
- scripts/resolve_h021_daily_session.py
- scripts/fanout_h021_future_cohorts.py
- .github/workflows/h021-daily-official-prices.yml
- tests/test_h021_daily_prices.py
- tests/test_h021_cohort_source.py

Offline regression runs:

    pytest -q tests/test_h021_daily_prices.py tests/test_h021_cohort_source.py

Important negative cases:
1. Genuine full-market original ZIP and index, but one initial ten-stock
   row absent: preserve original SOURCE_INCOMPLETE, allow independent
   future cohort to observe its own present stock.
2. Missing/unverified index or UDiFF: no source fanout, no false prices.
3. Mismatched EQ identity/ISIN: no fill and explicit initial failure.
4. Tampered canonical packet, source SHA, or complete-state/count:
   fail closed, never promote an incomplete original first cohort.

**No actual 12/13 October price source was fetched or inferred in this
patch.** First H021 opening auction occurred today, but official
complete-session bhavcopy is scheduled for source capture after close.
