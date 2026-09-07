# H002 historical replay phase-A integrity revision r2

This revision changes only the reconstruction compiler. It does not change H002-R001,
H002-X001, or the frozen H002-HR001 replay rule, and it does not use post-filing returns.

## Why r2 was required

The first 200-observation dry run produced 167 signals, 2 no-signals, 10 uncovered
observations, and 21 execution errors. No Phase-A manifest was frozen because the gate
requires zero unresolved errors.

The 21 errors were concentrated in deterministic historical-identity conditions:

- official XBRL ticker spelling differs from the current NSE spelling,
- an issuer has a documented ticker rename,
- historical and current ISINs differ after a share-basis corporate action,
- a predecessor security belongs to a demerger/restructure and is not EPS-comparable,
- raw quarter labels do not establish the frozen H002 same-quarter baseline,
- an official archive URL retained in NSE discovery now returns 404.

None of these conditions justifies inventing evidence.

## r2 handling

### Narrow symbol equivalence

Only explicit, evidence-backed aliases are allowed:

- `BAJAJ-AUTO` and official-filing spelling `BAJAJAUTO`,
- `LTM` and former NSE symbol `LTIM`.

There is no fuzzy ticker matching.

The retained target and baseline events keep their original raw symbols. A
calculation-only copy may use the canonical cohort symbol so the unchanged H002 scorer can
bind the event, expectation, and price reference to one issuer key.

### Corporate restructures are not aliases

`TMPV` is not treated as a rename of `TATAMOTORS`. The Tata Motors demerger/merger
lineage changes the economic perimeter, so the historical prior-year EPS comparison is
`SKIPPED`.

### Historical ISIN changes

The September-2026 cohort ISIN is not used as proof of historical identity. If baseline
and target filing ISINs differ, the comparison is allowed only when the official
corporate-action audit detects a share-basis action that reconciles the EPS basis.
Otherwise the observation is `SKIPPED`.

The UDiFF pre-filing price row is checked against the target filing's historical ISIN,
not the current cohort ISIN.

### Reporting-quarter mismatch

r2 does not rewrite quarter labels. H002-R001 requires the same prior-year reporting
quarter. If the retained target and baseline events do not expose the same quarter label,
the observation is `SKIPPED` rather than coerced into a signal.

This is intentionally conservative. A later parser repair may recover such observations
only if the official source can verify the quarterly context without outcome information.

### Dead official archive URLs

An NSE discovery row whose selected official archive URL returns a verified HTTP 404 is
`UNCOVERED`. Transient acquisition failures remain `ERROR`.

## Leakage boundary

The r2 correction was designed after inspecting only Phase-A acquisition diagnostics and
signal availability. No entry price, exit price, benchmark outcome, realized return, or
winner/loser label had been loaded.

The workflow still refuses to freeze Phase A while any `ERROR` observation remains.
`SKIPPED`, `NO_SIGNAL`, and `UNCOVERED` are valid terminal evidence states and are retained
rather than imputed.
