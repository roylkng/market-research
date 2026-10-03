# H024 Historical Maturity Extension v2

Status: FROZEN BEFORE ADDITIONAL POST-V1 RETURN MATERIALIZATION
Frozen: 2026-10-03
Live capital: DISABLED

## Objective

Advance the already-sealed H024-v1 historical event cohort to a later official
market-data cutoff without changing the signal, event set, investability rules,
outcome definitions, cost stress, robustness views or classification thresholds.

The only research question is:

> As the exact sealed H024 event cohort naturally matures, does the original
> 60-session primary coverage gate become satisfied, and if so what
> classification does the unchanged H024-v1 rule produce?

This is a maturity extension, not a new event-discovery backtest.

## Authoritative frozen event input

Exact repository artifact:

    research/historical/h024/challenge-2026-09-15/event-panel.json

Required event-panel SHA-256:

    65b957a2a66144194690f0298602ca0118eb4af8e725cce5df7549da6b1baec4

Required frozen event counts:

- 209 events;
- 79 distinct event symbols.

No event may be added, removed, re-aggregated, rescored or re-investability-tested.

In particular, filings previously excluded because their planned entry was after
the original challenge market cutoff remain excluded. v2 does not rebuild the
event panel from the 785-filings source panel.

## Frozen v1 reference

Sealed v1 summary:

    research/historical/h024/challenge-2026-09-15/outcome-summary.json

The v1 primary 60-session state was:

- mature events: 107;
- complete events: 105;
- complete distinct symbols: 42;
- complete share of mature: 98.13%;
- mean Nifty 500 excess: +11.67 percentage points;
- median excess: +6.60 percentage points;
- beat rate: 64.76%;
- symbol-cluster bootstrap 95% lower bound: +1.40 percentage points;
- classification: INSUFFICIENT_COVERAGE.

The failed gate was only the predeclared minimum of 50 distinct complete
symbols.

These v1 statistics are reference evidence only and do not change v2 rules.

## Extended market-data cutoff

New maturity cutoff:

    2026-10-01

Reason:

- 2026-10-01 is the latest completed NSE cash-market session before the
  2026-10-02 exchange holiday and 2026-10-03 weekend;
- official historical market files are expected to be fully published by the
  2026-10-03 freeze date.

No session after 2026-10-01 may enter v2.

## Calendar

Use the unchanged H024 historical calendar mechanics from
`src/marketlab/h024_historical.py`:

- start: 2026-01-01;
- same frozen weekday holidays already required before 2026-10-01;
- 2026-02-01 special Sunday Budget session;
- standard cash session otherwise.

Because v2 only appends later sessions after the original event-panel entries,
every sealed event must satisfy:

    sessions[event.entry_index].session_date
    ==
    event.entry_session_date

Any mismatch fails the entire extension.

No event index may be recomputed.

## Market data

Unchanged official sources:

- NSE CM UDiFF final bhavcopy for stock OHLC/identity;
- NSE daily index snapshot for Nifty 500 benchmark.

Exact source bytes and SHA-256 evidence are retained.

Only the 79 sealed event symbols require stock bars.

## Corporate actions

Unchanged v1 blocking semantics.

For every sealed event symbol, query the official NSE corporate-actions endpoint
over:

    2026-01-01 through 2026-10-01

The same blocked subjects remain:

- bonus;
- split / subdivision;
- consolidation;
- rights;
- demerger / spin-off;
- reduction of capital;
- scheme of arrangement;
- merger / amalgamation.

No adjustment-factor reconstruction.

An unresolved relevant corporate-action audit fails closed for affected outcomes.

## Outcome definitions

Unchanged H024-v1:

- entry price = sealed entry-session open;
- horizon session indexing:
  - 20 = entry_index + 19
  - 60 = entry_index + 59
  - 120 = entry_index + 119
- exit price = horizon-session close;
- stock identity = sealed entry symbol + ISIN;
- benchmark = Nifty 500 over identical open-to-close interval;
- gross excess = stock return minus benchmark return;
- cost-adjusted excess = gross excess minus 0.50 percentage point;
- benchmark beat = gross excess > 0.

## Statistical machinery

Unchanged:

- symbol-cluster bootstrap;
- 10,000 iterations;
- seed 24024;
- first-event-per-symbol robustness;
- non-overlapping-60 robustness;
- publication-month composition;
- frozen purchase-value composition buckets.

No new weighting, magnitude or actor feature enters the primary signal.

## Frozen primary classification

Coverage gate at 60 sessions remains:

- complete events >= 100;
- distinct complete symbols >= 50;
- completeness among mature events >= 80%.

If coverage fails:

    INSUFFICIENT_COVERAGE

Otherwise:

REJECTED:
- mean excess <= 0 OR median excess <= 0.

STRONG:
- mean excess >= +4.0pp;
- cluster-bootstrap 95% lower bound > 0;
- benchmark beat rate >= 55%;
- first-event-per-symbol mean excess > 0;
- non-overlapping-60 mean excess > 0.

PROMISING:
- mean excess >= +2.0pp;
- median excess > 0;
- benchmark beat rate >= 55%;
- both frozen robustness means > 0.

Otherwise:

    INCONCLUSIVE

Thresholds may not change after v2 outcomes open.

## Required comparison outputs

Report both the full v2 state and maturity delta versus sealed v1:

- mature-event delta;
- complete-event delta;
- complete-distinct-symbol delta;
- newly mature event IDs;
- newly complete event IDs;
- primary classification before/after;
- all unchanged primary metrics;
- 20/60/120 horizon summaries.

The maturity delta is descriptive only.

## Scientific boundary

v2 can answer whether the original historical cohort naturally satisfies its
coverage gate after more time passes.

v2 cannot:

- alter the H024 signal;
- add later source filings/events;
- validate purchase-value weighting;
- replace H024 prospective validation;
- authorize live capital.

If v2 becomes PROMISING or STRONG, H024 still requires prospective evidence.
If v2 remains INSUFFICIENT_COVERAGE or becomes weaker, no rescue/tuning is
permitted under this extension.
