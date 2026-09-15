# H024 historical challenge implementation v1

Status: **FROZEN BEFORE H024 RETURN INSPECTION**

Frozen: 2026-09-15
Signal/protocol source: H024-R001 and `research/H024_PROSPECTIVE_PROTOCOL_V1.md`
Historical source window: 2026-05-01 through 2026-09-15
Market-data cutoff: 2026-09-15 completed NSE session
Live capital: disabled

## Purpose

Implement the already frozen H024-v1 historical point-in-time challenge without introducing outcome-dependent choices. This document resolves only mechanical details needed to execute the protocol. It does not change the signal, actor categories, source contract, investability hurdle, entry convention, horizons, cost assumption, evidence gates, or promotion thresholds.

No H024 stock return, benchmark return, or post-event price path may be opened until this implementation contract and its code path are committed.

## Frozen source panel

The challenge begins from `research/historical/h024/prefreeze-original-purchase-source-panel-v1.json`.

The raw file SHA-256 is fixed at:

`94bb81839c7d868736f830e88a3feb83538a04dfc7be01d546a7839e2bf3d101`

It contains 785 qualifying Original filings across 158 symbols. It is derived only from the pre-return NSE Regulation 7(2) source audit and H024-R001 transaction semantics.

## Revision reconstruction

The historical challenge re-queries the official NSE PIT-GG discovery feed for 2026-05-01 through 2026-09-15 in bounded windows and retains exact discovery bytes/hashes.

For each source-panel Original filing, any same-symbol Regulation 7(2) `Revision` whose official exchange dissemination timestamp is strictly after that Original and strictly before the planned entry open blocks that Original. `prevAppId` is not required because H024-v1 deliberately uses the conservative symbol-level rule.

A same-symbol same-entry event survives when at least one qualifying Original mapped to that entry remains unblocked.

## Calendar and entry

The reconstruction uses the NSE cash-market session calendar from 2026-01-01 through 2026-09-15.

Known 2026 closed weekdays used by the deterministic calendar are:

- 2026-01-15
- 2026-01-26
- 2026-03-03
- 2026-03-26
- 2026-03-31
- 2026-04-03
- 2026-04-14
- 2026-05-01
- 2026-05-28
- 2026-06-26
- 2026-09-14

The 2026-02-01 Union Budget Sunday session is included as a special session.

Every expected session must be confirmed by an official Nifty 500 index snapshot. Closed weekdays/weekends are probed so an unregistered special session fails the run rather than silently changing horizon counts.

H024's same-calendar-day prohibition is applied literally. The planned entry is the first NSE session whose **calendar date in Asia/Kolkata is strictly later** than the official `exchdisstime` calendar date. A pre-open disclosure therefore still enters the next trading date, not the same date.

## Horizon indexing

The entry session counts as completed holding session 1. Therefore:

- 20-session exit index = `entry_index + 19`;
- 60-session exit index = `entry_index + 59`;
- 120-session exit index = `entry_index + 119`.

This matches the already implemented H022 historical outcome convention and prevents H024 from receiving a different horizon definition.

## Official market data

Equity prices, identity, series, and traded value come from official NSE CM UDiFF final bhavcopy files.

A usable equity row must be:

- `Sgmt = CM`;
- `Src = NSE`;
- `FinInstrmTp = STK`;
- `SctySrs = EQ`;
- exact requested ticker symbol;
- positive open and close prices;
- non-negative `TtlTrfVal` traded value.

The Nifty 500 benchmark comes from the official NSE daily index snapshot used by the existing PF001/H022 source contract.

Exact source bytes are retained in the workflow artifact store. Compact repository evidence retains URLs, hashes, and derived records.

## Point-in-time H004 investability subset

For each planned entry:

1. an exact NSE `STK` / `EQ` row must exist on the entry session;
2. the entry ISIN becomes the event identity;
3. at least 60 prior completed NSE sessions must contain an `STK` / `EQ` row for the same symbol and same ISIN;
4. the previous 20 completed market sessions are used exactly, not the previous 20 observed trading rows;
5. a missing/mismatched row in those 20 sessions contributes zero traded value;
6. median prior-20 `TtlTrfVal` must be at least INR 20,000,000.

This implements the frozen H004 primary liquidity/history hurdle without importing H004 catalyst or momentum logic.

A missing entry row, insufficient same-ISIN history, or sub-threshold median turnover excludes the event before outcomes are evaluated.

## Identity continuity

The entry-session ISIN is frozen as the event security identity. An exit row with the same symbol but a different ISIN is not guessed through and produces an incomplete horizon status.

## Corporate actions

Corporate-action evidence is fetched from the official NSE corporate-actions endpoint for each challenge symbol and retained by exact source hash.

Consistent with the earlier H022 historical engine, raw-price outcomes are blocked when the holding interval contains any action whose subject indicates:

- bonus;
- split / sub-division;
- consolidation;
- rights;
- demerger / spin-off;
- reduction of capital;
- scheme of arrangement;
- merger / amalgamation.

The v1 challenge does not introduce an after-the-fact adjustment-factor parser. A source failure or unparseable relevant corporate-action date also fails closed for the affected symbol/horizon.

## Event aggregation

After revision and investability filters, all surviving qualifying Original filings for one `(symbol, planned_entry_session)` create exactly one binary H024 event.

Purchase value, quantity, actor count, filing count, and ownership delta are descriptive only.

## Frozen outcomes and statistics

For each complete horizon:

- stock return = entry-session open to horizon-session close;
- benchmark return = Nifty 500 entry-session open to the same horizon-session close;
- gross excess = stock return minus benchmark return;
- cost-adjusted excess = gross excess minus 0.50 percentage point;
- benchmark beat = gross excess > 0.

The primary 60-session summary reports complete event count, distinct symbols, mean and median excess, benchmark beat rate, mean cost-adjusted excess, and a 10,000-iteration symbol-cluster bootstrap 95% confidence interval for mean excess with seed `24024`.

## Frozen robustness implementation

`first_event_per_symbol` retains the earliest complete eligible event per symbol.

`non_overlapping_60` processes each symbol chronologically, retains the earliest complete event, and excludes any later event whose entry session is on or before the retained event's 60-session exit session. The process then continues from the next non-overlapping event.

Publication-month composition uses the Original filing exchange-dissemination month.

Purchase-value composition uses fixed source-only INR buckets, chosen before return inspection:

- `<1cr`: value < INR 10,000,000;
- `1-10cr`: INR 10,000,000 to < INR 100,000,000;
- `10-100cr`: INR 100,000,000 to < INR 1,000,000,000;
- `>=100cr`: INR 1,000,000,000 or more.

Industry composition is diagnostic only. It may be reported only if a defensible pre-event industry source is available. A current-only classification must not be mislabeled as point-in-time. If no such source is available in v1, the diagnostic is explicitly marked unavailable and does not affect the already frozen primary classification.

## Classification

The classification is exactly the H024-v1 protocol:

Coverage gate at 60 sessions:

- at least 100 complete events;
- at least 50 distinct complete-event symbols;
- at least 80% completeness among mature eligible events.

If the gate fails: `INSUFFICIENT_COVERAGE`.

Otherwise:

- `REJECTED` if mean excess <= 0 or median excess <= 0;
- `STRONG` if mean excess >= 4.0 percentage points, symbol-cluster bootstrap 95% lower bound > 0, benchmark beat rate >= 55%, and both frozen robustness mean excess returns are positive;
- `PROMISING` if mean excess >= 2.0 percentage points, median excess > 0, benchmark beat rate >= 55%, and both frozen robustness mean excess returns are positive;
- otherwise `INCONCLUSIVE`.

Historical classification is development evidence only. It cannot authorize capital and cannot modify H024-v1.