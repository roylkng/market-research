# H022-P001 prospective outcome contract v1

## Status

`FROZEN_BEFORE_FIRST_PROSPECTIVE_SOURCE`

Frozen: 2026-09-14

Prospective source boundary: `2026-09-14T18:30:00Z` = `2026-09-15 00:00 IST`

Live capital: **DISABLED**

Future P001 returns inspected while freezing this contract: **NO**

## Purpose

This contract freezes how the already-defined H022-P001 management-information signal will be evaluated prospectively. It preserves the historical H022-X001 outcome and classification rules and adds only the operational executability constraint required by real-time acquisition.

No signal weight, horizon, benchmark, cost, rank rule, promotion threshold, or missing-data policy may be changed using future P001 return outcomes.

## Eligible signal records

The prospective signal ledger is the only source of P001 decisions.

A record enters outcome evaluation only when:

- its immutable P001 signal record validates;
- `signal_status == SIGNAL`;
- `primary_signal` is finite and non-null;
- the record belongs to the frozen U001 cohort;
- source/E002/signal provenance remains valid under the prospective stream contract.

`NO_SIGNAL_NO_PRIOR_TRANSCRIPT`, `NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP`, blocked unresolved-source candidates, and any source that never yielded a sealed signal are coverage evidence only. They do not receive synthetic zero returns and do not enter signal ranking.

## H022-X001 entry

The nominal entry session is the first completed NSE cash-market session whose official open timestamp is **strictly later** than `exchange_published_at_utc`.

Entry price is that session's official open.

For a prospective signal to be executable at this nominal H022-X001 entry:

```text
signal_frozen_at_utc <= nominal_entry_open_utc
```

If not, the record is classified:

`LATE_SIGNAL_FREEZE`

A late signal remains in acquisition/coverage diagnostics but is excluded from the primary first-open prospective outcome. It is not backdated and its primary entry is not silently moved to a later session.

Any future delayed-entry diagnostic must be separately frozen and reported as secondary.

## Horizons

The frozen H022 horizons are reused unchanged:

- 20 completed NSE sessions;
- **60 completed NSE sessions, primary**;
- 120 completed NSE sessions.

For an entry session at index `i`, the horizon exit session is index:

```text
i + horizon - 1
```

Exit price is the official close of that horizon session.

No calendar-day approximation is permitted.

## Frozen market calendar

Outcome session identity must come from reviewed frozen NSE cash-market calendar snapshots containing explicit session dates and UTC open/close timestamps.

A calendar with an unresolved possible special session cannot be used through that uncertainty. If an unresolved special-session date can alter the nominal entry or the session count before an exit, the affected outcome is pending with:

`CALENDAR_UNRESOLVED_SPECIAL_SESSION`

If the requested horizon extends beyond the reviewed calendar coverage, the status is:

`CALENDAR_COVERAGE_INSUFFICIENT`

These are pending calendar states, not negative outcomes.

The currently frozen FY27-Q2 calendar covers through 2026-12-31 and contains unresolved special date 2026-11-08. It is therefore sufficient for early 20-session observations but cannot be assumed sufficient for all 60/120-session P001 outcomes. Calendar continuity must be reviewed before those outcomes mature.

## Market data and identity

Stock bars reuse the H022 historical UDiFF identity contract:

1. exact current U001 ISIN when available;
2. current-symbol EQ fallback only when exact ISIN is absent and exactly one eligible row exists;
3. ambiguous identity fails closed.

Benchmark is official Nifty 500 index data.

Entry and exit bars must correspond to the exact frozen session dates. Missing stock or benchmark bars are explicit missing-data states, not zero returns.

## Corporate actions

The historical H022 corporate-action guard is reused unchanged.

Potentially return-distorting share actions between entry and exit, including split, bonus, rights, demerger, merger, consolidation, capital reduction, and scheme-of-arrangement events, block that horizon unless the outcome methodology is separately reviewed before seeing the affected result.

An unresolved corporate-action audit is an incomplete outcome, not a valid return.

## Return definition

For a complete horizon:

```text
stock_return_pct = 100 * (stock_exit_close / stock_entry_open - 1)
benchmark_return_pct = 100 * (nifty500_exit_close / nifty500_entry_open - 1)
gross_excess_pp = stock_return_pct - benchmark_return_pct
cost_adjusted_excess_pp = gross_excess_pp - 0.50
beat_benchmark = gross_excess_pp > 0
```

Frozen round-trip implementation cost: **0.50 percentage points**.

No dividend reconstruction, FX conversion, intraday optimization, stop loss, take profit, or discretionary exit enters the primary outcome.

## Primary cross-sectional evaluation

The existing H022 evaluation logic is reused:

- Spearman correlation between `primary_signal` and gross excess return;
- deterministic quintiles ranked by signal, with source ID as tie breaker;
- top-quintile and bottom-quintile mean excess;
- top-minus-bottom mean excess spread;
- top-quintile median excess;
- top-quintile mean cost-adjusted excess;
- top-quintile Nifty 500 beat rate;
- 10,000-iteration symbol-cluster bootstrap of the top-minus-bottom spread;
- bootstrap seed `22022`.

The primary classification is made only at the **60-session** horizon.

`LATE_SIGNAL_FREEZE` records are outside the executable primary population and do not enter its numerator or denominator.

Pending calendar states and `NOT_MATURE` do not count as mature observations.

Once a signal's horizon is chronologically mature, missing bars, unresolved corporate-action audit, or corporate-action blockage count as incomplete mature observations for the frozen completeness gate.

## Frozen classification gates

The historical H022 gates are reused without optimization:

- minimum complete primary observations: **200**;
- minimum complete share of mature executable observations: **80%**.

If either gate fails:

`INSUFFICIENT_COVERAGE`

Otherwise:

`REJECTED` when top-minus-bottom spread <= 0 or top-quintile mean excess <= 0.

`STRONG` when all are true:

- top-minus-bottom mean excess >= 4.0 percentage points;
- symbol-cluster bootstrap 95% lower bound > 0;
- top-quintile benchmark beat rate >= 55%.

`PROMISING` when all are true:

- top-minus-bottom mean excess >= 2.0 percentage points;
- top-quintile median excess > 0;
- top-quintile benchmark beat rate >= 55%.

Otherwise:

`INCONCLUSIVE`.

These labels are evidence summaries, not automatic live-capital authorization.

## Maturity and information firewall

Outcome acquisition may begin only after the relevant exit session has completed.

Before a horizon is mature, its return fields remain absent. The evaluator must not query future market data merely because an endpoint technically exposes it.

Outcome collection may use signal identity, publication time, signal freeze time, frozen universe identity, reviewed NSE calendar, official stock/benchmark market data, and corporate-action evidence.

It may not use later management calls, later P001 signals, H021, H013, H019, H020, valuation, post-publication narrative, or portfolio performance to alter an earlier signal or entry.

## Promotion boundary

No H022-P001 prospective result can authorize live capital by itself. Any future promotion requires a separate decision artifact after the frozen primary coverage/classification gates have been evaluated, with concentration, implementation, dependence, and comparison diagnostics reviewed independently.
