# H021-P004 Official First-Entry Source Observation Contract

Status: **source-only implementation, outcome-blind**. Frozen before the planned 12 October 2026 next-open observation. No capital authorization.

## Scope

H021-P003's 9 October 2026 primary top decile **already contains exactly ten names**. P004 never recalculates ranks, chooses another stock, checks realized returns, picks a later entry, or claims a filled trade.

The next-session open is expected at **09:15 IST, 12 October 2026**, according to the frozen NSE-CM calendar. NSE publishes completed market-session data after the session. Therefore the collector must **not request or seal opening-price evidence before the 12 October 15:30 IST close**. A post-close acquisition observes that session's official OHLC but does not prove a participant could have purchased at the reported open.

## Source-of-record

Only the exact publicly accessible NSE source URLs for 2026-10-12 are used:

- official CM UDiFF final bhavcopy ZIP for NSE EQ stocks
- official NSE index-close-all daily CSV for the Nifty 500 price index

The marketlab.pf001_marketdata parsers are reused. Both original responses retain:

- URL, HTTP status, UTC capture timestamp, original byte count and SHA-256
- content-addressed raw ZIP/CSV files
- explicit access-blocked, not-published and fetch-failed states
- packet-level SHA-256 after canonical serialization

A redirect to an unverified domain is **not** followed. HTTP 401, 403 and 429 are recorded without further bypass or retries. Missing official reports remain missing.

## Security and source integrity

Both frozen inputs must reproduce byte-for-byte by Git blob hash before acquisition:

- original H021-P003 decision intent
- U001 100-company universe
- source H021 comparison and NSE calendar, checked by the existing pre-entry module

Only the ten original listed symbol/ISIN pairs and EQ series are accepted. Per-symbol absence, malformed OHLC, duplicate rows and mismatched ISIN remain failed observations. A parser error for one company never authorizes filling its price from a later session or another vendor.

All ten successful stock rows plus the Nifty 500 index row are required before the source-complete record can be sealed.

## Interpretation and scientific boundaries

The frozen 60-completed-session primary and 20-session secondary **outcome rules remain unchanged**. P004 does not compute or open either outcome, return, target, benchmark excess, expected return, portfolio decision or position size.

Raw NSE price data are **not corporate-action adjusted**. Separate split/bonus/rights/dividend checks must be completed for the holding interval. The observed benchmark is **Nifty 500 price index**, not Nifty 500 TRI. The price-only benchmark's dividend mismatch must be disclosed or resolved before an investable total-return comparison.

The observation status OFFICIAL_OHLC_OBSERVED_NOT_EXECUTABLE_FILL does **not** establish market depth, order execution feasibility, liquidity, bid/ask slippage, preopen-auction participation, or broker availability. The paper return is a hypothetical official open-price proxy only, not a simulated real fill.

All 10 stock rows retain tradability_confirmed=false and actual_trade_fill_confirmed=false. The observation retains return_outcomes_opened=false, execution_and_liquidity_verified=false, corporate_action_adjustments_verified=false and live_capital_allowed=false.

## Operation and failure recovery

Workflow: .github/workflows/h021-first-entry-observation.yml

- Redundant post-close scheduled attempts at 18:15, 18:45 and 19:15 IST on weekdays, gated to **12 to 30 October 2026**.
- Future run attempts stop after an already sealed complete result.
- Each attempted acquisition is anchored append-only under research/prospective/h021/entry-observations/attempts by unique GitHub run ID and attempt.
- Each downloaded original is durably committed under research/prospective/h021/entry-observations/raw/sha256. CI artifacts are supplementary, not the sole evidence store.
- A complete original source observation is anchored once at research/prospective/h021/entry-observations/2026-10-12-first-entry-v1.json.
- Partial attempts do not overwrite prior receipts and are not promoted to the complete path.
- After fetch, the runner refuses to push if any frozen source, evaluation code or contract changed on main. Unrelated main updates may be rebased safely. Unresolvable push conflicts retain the run artifact.

The collector never falsely dates a missing Oct 12 source to Oct 13. A subsequent recovery still requests Oct 12 original official files and records the true later acquisition timestamp.

Reproduce invariants without any market service:

    pytest -q tests/test_h021_entry_observation.py tests/test_h021_first_entry_intent.py

## Remaining independent gates

1. Real 12 October source acquisition and original SHA/ISIN verification. Impossible until the market session completes.
2. 20/60-session official equity and Nifty 500 interval prices, identical entry/exit convention, corporate-action and dividends basis.
3. Independently verified official 2027 NSE trading calendar for the 60-session exit. The frozen 2026 calendar covers only 55 sessions from the expected entry.
4. Multiple prospective monthly H021 decision cohorts, mature return observations, and preregistered benchmark/cost comparisons.
5. Distinguish research proxy from real investability. P004 does not promote PF001 or override the lack of multiplicity-robust alpha evidence.
