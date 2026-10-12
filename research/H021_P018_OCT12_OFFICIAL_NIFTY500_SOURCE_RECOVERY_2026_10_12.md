# H021-P018: Original NSE Nifty 500 Entry Index Source Recovery

Status: POST-ENTRY DATA AVAILABILITY AND MEASUREMENT INTEGRITY.
Established: 12 October 2026 IST. **NO H021 RETURNS OR LIVE CAPITAL.**

## Exact unresolved evidence

The first observed H021 next-session opening prices belong to 12 October
2026 and were acquired in one original official NSE CM UDiFF bhavcopy
(207,055 bytes, SHA-256
818f673b3cdb96ae8ec4e466c7c4fd3a28d035482173a675dd24f9437a3ecd99).

That first capture was 10/10 complete for the frozen EQ/ISIN observations
and was recorded at 2026-10-12T12:03:09Z, but the original index source

https://archives.nseindia.com/content/indices/ind_close_all_12102026.csv

returned HTTP 404 NOT_PUBLISHED at that exact time. It was
scientifically correct to preserve the original first attempt with a
null Nifty 500 benchmark instead of fabricating a return.

P017 recorded two independent measurement caveats:
- IDEA had a positive percentage EPS revision because a *negative*
  prior EPS denominator reverses the economic change in forecast loss.
- VEDL had an Oct14 announced dividend record date requiring an
  independently verified ex-date, cash entitlement and price-vs-TRI
  comparability review.

The original 9 October selection is fully preserved. The first
observed NSE opens are a source-only *hypothetical* entry proxy,
not verified executable fills.

## Postclose only. Exact original 12 Oct market report.

P018 declares only two approved, exact NSE-host URLs for the same
12 October original index report:

1. Primary original hostname:
   https://archives.nseindia.com/content/indices/ind_close_all_12102026.csv
2. NSE archive mirror hostname:
   https://nsearchives.nseindia.com/content/indices/ind_close_all_12102026.csv

**These are source-location alternatives, not different benchmark
calculations.** The original first 404 is immutable.

The collector never follows redirects, bypasses access denied, uses
unverified third-party index values, requests a different date, or
uses a share-price weighted aggregate as a stand-in for Nifty 500.
After Oct12 official close it tries each fixed NSE URL with bounded
retries and records raw HTTP status and UTC timestamp.

A response is considered parsed only when the existing verified
PF001 parser finds **exactly one Nifty 500 row dated 12 October 2026**,
with finite positive opening and closing index values.

### Source promotion and contradictions

- **Primary valid, mirror missing:** index source may be sealed under
  official primary archive evidence.
- **Both NSE sources valid and equal:** source corroborated and sealable.
- **NSE secondary mirror only:** original byte source preserved but
  marked PENDING PRIMARY CORROBORATION. Never promoted to an
  authorized or confirmed benchmark outcome.
- **Conflicting NSE hosts:** no source seal, no chosen winning close.
- **Missing/blocked/unparseable:** preserve an explicit attempt/byte
  receipt, never substitute another provider.

A source can be acquired later while still corresponding to the
original 12 October session. The later actual retrieval timestamp is
recorded. No backdating is allowed.

## Exact provenance

This recovery rechecks original Git blob identities of:
- 9 October H021 P003 immutable ten-name research entry intent;
- 100-name U001 ISIN universe;
- first original Oct12 reconstructed P004 attempt;
- original NSE UDiFF ZIP SHA;
- original 28-day consensus EPS comparison;
- original NSE FY27Q2 calendar.

All ten actual first-session EQ open/high/low/close data are independently
re-parsed from original UDiFF bytes and verified against the first
reconstructed attempt. No selected symbols or values change.

Each successful source response is preserved as original CSV bytes
under a content-addressed sha256 path and its true capture time.
Each attempt is independently append-only with GitHub run ID.
A separate immutable supplement is published **only if a primary NSE
original is validated or both NSE host copies agree**:

research/prospective/h021/index-recovery/2026-10-12-official-index-supplement-v1.json

First source attempt and P017 measurement caveats remain unchanged.

## Implementation and scientific consequences

- src/marketlab/h021_index_recovery.py
- scripts/recover_h021_nifty500_original.py
- tests/test_h021_index_recovery.py
- .github/workflows/h021-index-source-recovery.yml

The GitHub workflow attempts on merge, then at scheduled exchange-safe
times until the October date gate closes; explicit manual recovery may
be triggered later. A blocked or not-yet-published official source is
**not considered a successful data observation**.

Even after Nifty 500 *price index* open is recovered:
- Nifty 500 *total return* basis remains unverified;
- all ten equity dividends/corporate actions need independent review;
- 8 November Muhurat session needs official verification;
- 60-session outcome needs official 2027 NSE calendar;
- four monthly-equivalent prospective cohorts and their 60-session
  return outcomes are not mature;
- real-world spread, auction liquidity, fees and order fills are not verified;
- the original EPS-negative IDEA sign and VEDL dividend warning stay
  documented.

Therefore this step cannot publish a trading return, expected alpha,
stock recommendation, completed paper fund result, or live capital.
It fixes a **source availability/recovery gap**, not the predictive
validity or investability of H021.
