# H002 deterministic paper execution v1

## Status

`H002-X001` is **FROZEN** and paper-only.

This rule does not assert that H002 is profitable. It defines how every prospective H002 signal will be observed so subsequent results cannot be improved by discretionary entry, exit, stock selection or fill reconstruction.

## Trading calendar

MarketLab does not infer NSE trading sessions from weekdays. H002-X001 consumes a versioned explicit NSE cash-market session calendar with timezone-aware open and close timestamps.

For a filing published on local exchange date `D`:

1. the event date itself is never an entry date,
2. the first trading session strictly after `D` is skipped,
3. the second trading session strictly after `D` is the paper-entry session,
4. entry uses that session's exact open,
5. entry session counts as holding session 1,
6. exit uses the close of holding session 20.

A weekday omitted from the versioned calendar is not silently recreated. This handles exchange holidays and special closures without generic weekday assumptions.

## Paper observation direction

Every H002 bucket other than `NO_SIGNAL` is observed as a long paper position. This includes `POSITIVE`, `ZERO` and `NEGATIVE`.

That does **not** mean negative UE is a buy recommendation. Keeping all buckets on the same return convention allows the prospective experiment to measure whether the groups separate without introducing a new short-selling hypothesis or asymmetric execution rules.

`NO_SIGNAL` is always `SKIPPED`.

## Evaluation timestamp

Every reconstruction receives a timezone-aware `as_of_utc` timestamp.

The engine distinguishes:

- entry has not opened yet: `PENDING / entry_not_due`,
- entry is due but exact open data is missing: `SKIPPED`,
- entry is due but tradability at the open is not confirmed: `SKIPPED`,
- exit close has not occurred yet: `PENDING / exit_not_due`,
- exit close is due but missing: `UNRESOLVED_EXIT`,
- exact entry and exit data exist: `COMPLETED`.

Any supplied market-data record with a source timestamp later than `as_of_utc` is rejected. This prevents a runner from smuggling future prices into an earlier report.

## No fabricated fills

The engine never infers an entry or exit from daily high, low, VWAP or a nearby price.

Entry requires:

- exact entry-session open,
- `tradable_at_open == true`,
- timestamped market-data source,
- explicit corporate-action version.

If these are absent after entry is due, the observation remains visible as `SKIPPED` rather than receiving an estimated fill.

Exit requires the exact exit-session close. A missing due exit is `UNRESOLVED_EXIT`, not a substituted prior/next close.

## Corporate actions

Entry and exit stock records require a corporate-action version. H002-X001 rejects a completed return when the entry and exit records use different versions because price comparability has not been established.

A future normalization system may support a version change across the holding window, but that requires its own explicit comparable-price transformation and tests. H002-X001 does not guess.

## Benchmarks

Required benchmark windows use the same entry-session open and exit-session close:

- `nifty_50`
- `nifty_200_momentum_30`

A sector-matched benchmark is optional only when a deterministic mapping was registered before the observation.

Missing benchmark data is reported as `MISSING`. It is never filled using another index or adjacent trading session.

## Costs

The initial paper report records gross return and fixed round-trip cost scenarios:

- 0 bps
- 25 bps
- 50 bps

These are sensitivity scenarios, not claims about a particular broker's actual all-in costs.

## Frozen rule

The canonical rule lives at:

`registry/h002_execution_rule.yaml`

Its SHA-256 is validated in tests and `make validate`. A change to entry timing, holding period, fill semantics, benchmark windows or cost convention requires a new execution-rule version.

## Explicit non-goals

H002-X001 does not contain:

- broker APIs,
- order placement,
- leverage,
- options,
- stop losses,
- take-profit rules,
- discretionary overrides,
- intraday optimization,
- sector/regime overlays.

Those features would answer different hypotheses and cannot be silently added to the H002 prospective test.
