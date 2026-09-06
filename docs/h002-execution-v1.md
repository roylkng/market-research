# H002 deterministic paper execution v1

## Status

`H002-X001` is **FROZEN** and paper-only. It defines how prospective H002 signals are observed. It does not imply that H002 is profitable or validated.

## Calendar and schedule

MarketLab consumes an explicit, versioned NSE cash-market session calendar. Weekdays are never treated as trading sessions implicitly.

For a filing published on exchange-local date `D`:

1. `D` is never an entry date,
2. the first trading session strictly after `D` is skipped,
3. the second trading session strictly after `D` is the paper-entry session,
4. entry uses the exact session open,
5. entry session is holding session 1,
6. exit uses the exact close of holding session 20.

The canonical SHA-256 of the version plus ordered session list is recorded in every paper position. The position identifier also binds to that calendar hash.

## Signal timing

For every non-`NO_SIGNAL` observation, the signal decision timestamp must be strictly earlier than the scheduled entry open. A signal computed after the entry price became observable is invalid rather than backfilled.

`NO_SIGNAL` is always `SKIPPED` and never creates a paper trade.

`POSITIVE`, `ZERO` and `NEGATIVE` are all observed long under the same execution convention. This is an experimental return convention, not a recommendation to buy every bucket.

## Evaluation timestamp and availability

Every reconstruction uses timezone-aware `as_of_utc`.

Market-data records with source timestamps later than `as_of_utc` are treated as unavailable. They are not consumed and do not trigger a future-data exception merely because they exist in the caller's larger dataset.

State transitions are:

- before entry open: `PENDING / entry_not_due`,
- entry information incomplete before entry-session close: `PENDING`,
- entry information still missing or non-tradable after entry-session close: `SKIPPED`,
- valid entry but before exit close: `PENDING / exit_not_due`,
- exit missing or non-tradable after due close: `UNRESOLVED_EXIT`,
- exact valid entry and exit: `COMPLETED`.

This distinction prevents a delayed data feed from turning a not-yet-observable fill into a false missing-data failure.

## No fabricated fills

The engine never reconstructs execution from high, low, VWAP, adjacent sessions or another security.

Entry requires:

- exact entry-session open,
- `tradable_at_open == true`,
- timestamped source,
- corporate-action version.

Exit requires:

- exact exit-session close,
- `tradable_at_close == true`,
- timestamped source,
- corporate-action version.

The source timestamp for an open value cannot predate the session open. The source timestamp for a close value cannot predate the session close.

Duplicate market bars for the same instrument/session are rejected rather than silently overwritten.

## Entry/exit provenance

Paper positions record separately:

- entry price source,
- exit price source,
- entry corporate-action version,
- exit corporate-action version.

A completed return requires matching entry and exit corporate-action versions. If future normalization supports a version change across a holding window, that must be a separately specified and tested transformation.

## Benchmarks

Required benchmark windows use the same entry-session open and exit-session close:

- `nifty_50`
- `nifty_200_momentum_30`

A sector benchmark is optional only when a deterministic mapping was registered before the observation.

Benchmark data newer than the evaluation timestamp is unavailable. Missing benchmark data remains explicitly `MISSING`. It is never imputed or replaced with an adjacent session.

## Costs

Paper results record fixed round-trip sensitivity scenarios:

- 0 bps,
- 25 bps,
- 50 bps.

These are research stress scenarios, not claims about a specific broker's actual costs.

## Frozen rule

The canonical contract is `registry/h002_execution_rule.yaml`.

Its SHA-256 is checked by tests and repository validation. Any material change to timing, session counting, fill semantics, benchmark windows, tradability, provenance or cost convention requires a new execution-rule version.

## Explicit non-goals

H002-X001 contains no broker integration, live orders, leverage, options, stops, targets, discretionary overrides, intraday optimization or regime overlays. Those would be separate hypotheses and cannot be added silently to H002.
