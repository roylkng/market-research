# H002 deterministic paper execution v1

## Status

`H002-X001` is **FROZEN** and paper-only.

This rule does not assert that H002 is profitable. It defines how every prospective H002 signal will be observed so subsequent results cannot be improved by discretionary entry, exit, stock selection or fill reconstruction.

## Trading calendar

MarketLab does not infer NSE trading sessions from weekdays. H002-X001 consumes a versioned explicit NSE cash-market session calendar with timezone-aware open and close timestamps.

The exact ordered session list is hashed. Every paper observation retains both the calendar version and its SHA-256, so changing a holiday or special-session assumption changes provenance rather than silently changing dates.

For a filing published on local exchange date `D`:

1. the event date itself is never an entry date,
2. the first trading session strictly after `D` is skipped,
3. the second trading session strictly after `D` is the paper-entry session,
4. entry uses that session's exact open,
5. entry session counts as holding session 1,
6. exit uses the close of holding session 20.

A weekday omitted from the versioned calendar is not silently recreated.

## Paper observation direction

Every H002 bucket other than `NO_SIGNAL` is observed as a long paper position. This includes `POSITIVE`, `ZERO` and `NEGATIVE`.

That does **not** mean negative UE is a buy recommendation. Keeping all buckets on the same return convention lets the experiment test group separation without adding an asymmetric short-selling rule.

`NO_SIGNAL` is always `SKIPPED`.

## Point-in-time evaluation

Every reconstruction receives a timezone-aware `evaluation_as_of_utc` timestamp.

The engine is deliberately unable to use information that was unavailable at that timestamp:

- before entry open: `PENDING / entry_not_due`,
- after entry open but before the entry session is final, missing/unavailable entry data remains `PENDING`,
- after entry-session close, missing or unverified entry becomes `SKIPPED`,
- before scheduled exit close: `PENDING / exit_not_due`, even if a caller supplies a future exit bar,
- after exit close, unavailable/missing/non-tradable exit becomes `UNRESOLVED_EXIT`,
- exact comparable entry and exit data produce `COMPLETED`.

A market-data record whose source timestamp is later than `evaluation_as_of_utc` is treated as **unavailable**, not as evidence. This allows the same immutable market-data archive to reconstruct what the system knew at different historical as-of timestamps without future leakage.

A source record is invalid if it claims to contain an opening price before the session opened, or a closing price before the session closed.

## Signal timing

The H002 signal decision must exist strictly before the scheduled entry open. If scoring occurs at or after that open, the observation is `SKIPPED / signal_not_available_before_entry_open`. MarketLab never backfills a paper trade from a signal generated too late.

## No fabricated fills

The engine never infers an entry or exit from daily high, low, VWAP or a nearby price.

Entry requires:

- exact entry-session open,
- `tradable_at_open == true`,
- timestamped source data available by the evaluation timestamp,
- explicit corporate-action version.

Exit requires:

- exact exit-session close,
- `tradable_at_close == true`,
- timestamped source data available by the evaluation timestamp,
- a corporate-action version comparable with entry.

A printed closing price therefore does not become an executable paper exit when the stock is locked with no executable liquidity.

## Market-data provenance

Entry and exit source identifiers and source timestamps are retained separately. A later vendor or source change cannot be hidden behind one generic `price_source` field.

Duplicate bars for the same instrument/session are rejected rather than resolved by list order.

## Corporate actions

Entry and exit stock records require a corporate-action version. H002-X001 rejects a completed return when the entry and exit records use different versions because price comparability has not been established.

A future normalization system may support a version change across the holding window, but that requires its own explicit comparable-price transformation and tests. H002-X001 does not guess.

## Benchmarks

Required benchmark windows use the same entry-session open and exit-session close:

- `nifty_50`
- `nifty_200_momentum_30`

A sector-matched benchmark is optional only when a deterministic mapping was registered before the observation.

Benchmark entry/exit sources and source timestamps are preserved separately. Missing or not-yet-available benchmark data is reported as `MISSING`; it is never filled using another index or adjacent session.

## Costs

The frozen paper report records gross return and exactly these round-trip sensitivity scenarios:

- 0 bps
- 25 bps
- 50 bps

Callers cannot substitute optimized cost scenarios into H002-X001. These are sensitivity scenarios, not claims about a particular broker's all-in costs.

## Frozen rule

The canonical rule lives at:

`registry/h002_execution_rule.yaml`

Canonical SHA-256:

`e33296d2aa8132e40258bf45036d504b624955701d9c20fe3c3612ca25c1a6f8`

The hash is validated in tests and `make validate`. A change to timing, holding period, fill semantics, as-of handling, benchmark windows, tradability requirements or cost convention requires a new execution-rule version once prospective observations begin.

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

Those features answer different hypotheses and cannot be silently added to the H002 prospective test.
