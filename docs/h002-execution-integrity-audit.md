# H002 execution-integrity audit, 6 September 2026

## Scope

This patch closes residual implementation gaps around the already-frozen `H002-X001`
paper-execution contract. It does not change the H002 economic signal, entry delay,
holding period, benchmark set, cost scenarios, universe or live-capital prohibition.

The goal is narrower: make the executable observation path prove that it is using the
frozen rule rather than merely accepting caller-provided labels that look compatible.

## Defects addressed

### 1. `price_day_minus_2` was not proved against the NSE calendar

`H002-R001` names its denominator `price_day_minus_2`, but the signal scorer could only
prove that the supplied price was before the filing. A caller could therefore label any
older trading-day close as `price_day_minus_2` and still obtain a valid signal.

H002-X001 now requires the exact `PriceReference` used to score every non-`NO_SIGNAL`
observation. The execution engine independently derives the second explicit NSE session
strictly before the filing's Asia/Kolkata publication date and requires:

- the reference trading date to equal that session,
- the reference timestamp to equal that session's registered close,
- the reference value to equal the value embedded in the scored signal,
- a non-empty source and corporate-action version.

The reference session date is retained in the paper-position artifact.

### 2. Frozen cost scenarios were runtime-mutable

The registry freezes round-trip sensitivity scenarios at 0, 25 and 50 basis points.
The implementation previously accepted any non-negative tuple at runtime. That allowed
post-outcome cost assumptions to be optimized without changing the frozen rule file.

The executable path now accepts exactly `(0, 25, 50)` and rejects every alternate set.
The parameter remains present only for explicit contract checking and backward API
compatibility.

### 3. Sector benchmarks were not actually pre-registered

The frozen rule permits a sector-matched benchmark only when a deterministic mapping
exists before the observation. Previously, passing any `sector_benchmark_id` was enough.

A sector benchmark now requires all of:

- a non-empty mapping version,
- a 64-character mapping SHA-256,
- an assignment timestamp strictly before filing publication,
- a sector benchmark id distinct from the two required benchmarks.

The mapping version, digest and assignment timestamp are retained in the position.

## Additional provenance hardening

The same patch records entry and exit market-data source timestamps separately and
records benchmark entry/exit source names and source timestamps. It also rejects market
bars whose session date is absent from the explicit versioned calendar.

`PaperPosition` advances to schema version 3. Earlier schema versions remain historical
artifacts and must not be silently rewritten.

## What remains deliberately unresolved

This patch does not claim that source labels are cryptographic provenance. The market
price source and `PriceReference` still need an immutable raw-source capture layer with
content hashes if the project is to prove later that the observed bytes existed in the
claimed form. The same principle applies to the pre-filing expectation ledger described
in the H002 signal-integrity audit.

Corporate-action comparability is still only accepted when the entry and exit records
share the same explicit normalization version. A future transformation across a split,
bonus or similar action requires its own versioned rule rather than an implicit ratio
adjustment.

No new H002 return observation, profitability result or investment recommendation is
introduced here. `live_capital` remains false.
