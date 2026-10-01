# AE001 D006 Stock-Options Row-Level Source Feasibility v1

Status: FROZEN BEFORE SOURCE AUDIT
Frozen: 2026-10-01
Live capital: DISABLED

## Background

AE001-D005-v1 failed its frozen p10 breadth gate:

- READY sessions: 266 / 266;
- median usable symbols: 199.5;
- p10 usable symbols: 13.0;
- low-coverage sessions (<75 symbols): 54.

D005-D1 showed that the low tail was dominated by D005's parser rule that
invalidated an entire ticker when any one STO row for that ticker was malformed
or duplicated.

D005 remains FAILED. D006 is a new source contract.

## Objective

Determine whether the same official NSE FO UDiFF archives support a sufficiently
broad and stable stock-options surface when source defects are isolated to the
smallest defensible unit:

- malformed rows are excluded individually;
- duplicate/ambiguous logical option contracts are excluded at the logical
  contract key;
- valid contracts for the same symbol remain eligible.

D006 is source-only. It does not create labels, fit a model, calculate returns or
open any alpha outcome.

## Historical window

2025-09-01 through 2026-09-25.

The completed NSE session calendar is taken from the existing official cash
market-panel construction.

## Official source

NSE F&O UDiFF Common Bhavcopy Final:

`BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`

Stock-option instrument code:

`STO`

Option types:

`CE / PE`

## Session-level fail-closed rules

The whole source session is parser-rejected if:

- the archive is not a single CSV;
- the required header changes;
- any row reports the wrong trade date, segment or source.

These are structural source-contract failures and are not row-level defects.

## Row-level contract

For an STO row, the row is excluded individually if any required row field is
invalid:

- missing symbol;
- missing financial instrument ID;
- option type not CE/PE;
- invalid actual expiry;
- non-positive strike;
- non-positive settlement price;
- negative previous close;
- invalid optional underlying price when present;
- negative open interest;
- non-finite change in open interest;
- negative traded contracts;
- negative transferred value;
- negative trade count;
- non-positive board lot.

No row defect invalidates other valid contracts for the same symbol.

## Duplicate logical-contract rule

Logical key:

`symbol + actual expiry + strike + option type`

If more than one accepted raw row maps to the same logical key, ALL rows for
that logical key are excluded.

This includes:

- repeated physical instrument rows;
- different financial instrument IDs for the same logical option.

The ambiguity is localized to the logical contract. It does not invalidate the
whole symbol.

## Identity

Remaining option rows are rebound on the same session to the exact CM EQ
symbol+ISIN identity from the official cash panel.

No symbol-only historical identity is accepted beyond the same-session join.

## Frozen option-surface rule

The D005 surface rule is unchanged.

For one symbol/session:

1. retain D006-valid STO contracts;
2. exclude contracts whose actual expiry is <= trade date;
3. select the earliest remaining expiry as front expiry;
4. require both CE and PE rows;
5. require at least three distinct strikes present in BOTH CE and PE;
6. require cash close > 0;
7. require at least one paired strike whose absolute moneyness versus cash close
   is <= 10%.

D006 does not require or compute implied volatility.

## Frozen viability gates

D006 passes only if ALL are true:

- parser-rejected session count = 0;
- READY source sessions >= 200;
- median usable option-surface symbols per READY session >= 100;
- 10th percentile usable option-surface symbols per READY session >= 75.

These thresholds are identical to D005. They are not relaxed.

## Required diagnostics

D006 reports:

- session counts;
- STO row counts;
- accepted contract rows;
- row-level exclusion counts by reason;
- ambiguous logical-contract count;
- distinct option symbols after cleaning;
- exact-EQ mapped symbols;
- usable front-surface symbols;
- surface exclusion reasons;
- per-session usable counts;
- median, p10, p90, min and max usable symbols;
- source hashes.

It also reports the same low-tail (<75) session list used to compare D006
directly with D005.

## Promotion

Only if every D006 viability gate passes may a separately frozen stock-options
feature trial be designed.

Passing D006 would establish source feasibility only, not options alpha.

## Non-goals

- no future-return labels;
- no options alpha features;
- no model fitting;
- no change to D005;
- no prospective claim;
- no live-capital claim.
