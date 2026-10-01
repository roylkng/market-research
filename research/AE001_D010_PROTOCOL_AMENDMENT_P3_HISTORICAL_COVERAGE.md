# AE001 D010 Protocol Amendment P3: Full Historical Coverage and Identity Audit

Frozen: 2026-10-01
Status: FROZEN AFTER P2 ROUTE VALIDATION, BEFORE P3 FULL-WINDOW AUDIT
Live capital: DISABLED

## Upstream evidence

D010-P1 resolved the exact official NSE CM Short Selling archive route.

D010-P2 workflow run 36877415573 established that the exact official NSE SLB
Daily Open Positions route is READY on all three frozen source-probe sessions
with one stable schema.

P2 report SHA-256:

    bff086e64a6a015b3b4f4058b726f0ca84f77a8dad0bc04ee55accd595cb9f84

P3 opens no stock-return labels.

## Objective

Audit both positioning sources over the standard AE001 historical-development
window:

    2025-09-01 through 2026-09-25

P3 establishes whether the files are complete enough, stable enough and
identity-safe enough to support a future feature-family trial.

## Trading-session denominator

Completed NSE cash-market sessions are identified only from the official
CM-UDiFF Common Bhavcopy Final.

Calendar days without a valid UDiFF EQ panel are not source-coverage failures.

The UDiFF panel is used only for same-session symbol+ISIN identity. P3 computes
no stock returns.

## Frozen source routes

### CM Short Selling

    https://nsearchives.nseindia.com/archives/equities/shortSelling/
    shortselling_DDMMYYYY.csv

Expected frozen schema:

- Security Name
- Symbol Name
- Trade Date
- Quantity

### SLB Daily Open Positions

    https://nsearchives.nseindia.com/archives/slbs/open_pos/
    slb_openpos_DDMMYYYY.csv

Expected frozen schema:

- Sr no
- Security
- Series
- Outstanding Quantity at the end of the day

## Row contracts

### CM Short Selling

- Symbol Name is normalized by trim + uppercase.
- Trade Date must parse and equal the source session date.
- Quantity must be finite and non-negative.
- Every source row is preserved individually.
- Duplicate source symbols are counted and are NOT silently aggregated.

### SLB Daily Open Positions

- Security is normalized by trim + uppercase.
- Series is retained exactly after trim + uppercase.
- Outstanding quantity must be finite and non-negative.
- Every source row is preserved individually.
- Duplicate symbols and duplicate symbol+series rows are counted and are NOT
  silently aggregated.

## Identity contract

For both families, the normalized source symbol is rebound to the exact
same-session UDiFF EQ symbol+ISIN map.

Symbol carry-forward across sessions is prohibited.

Unmatched rows are retained as unmatched diagnostics and cannot enter a future
stock feature.

## Frozen promotion gates

Each family independently passes historical source viability only when:

1. official file READY coverage >= 95% of completed NSE sessions;
2. exactly one READY-file schema is observed across the window;
3. CM Short Selling has zero parsed Trade Date mismatches;
4. exact same-session UDiFF identity mapping >= 95% of parsed source rows;
5. no parser/data-integrity error is hidden as a zero signal.

Overall P3 promotes only if BOTH families pass.

## Sparse-row semantics

P3 does NOT interpret a source-row absence as numeric zero.

A successful session file proves only that the file was captured. Future feature
semantics require a separately frozen P4 rule deciding whether:

- absence means zero;
- absence means no reported position/activity;
- missingness must remain explicit.

## Duplicate semantics

If duplicate symbols or symbol+series rows are observed, P3 reports their
frequency and examples.

No summation/max/last-row rule is chosen under P3.

Any required aggregation is frozen under P4 before return outcomes are opened.

## P3 outputs

- exact raw source bytes retained in the Actions evidence artifact;
- normalized source-only panel with same-session mapped identities;
- per-session coverage/row/mapping diagnostics;
- aggregate source-viability report;
- exact artifact hashes.

## Promotion

If both families pass:

    AE001-D010-P4-FEATURE-SEMANTICS

P4 remains source/feature-definition work. No return labels may be opened until
the feature semantics and prospective source-timing boundary are separately
frozen.

Historical archive availability does not prove publication time.

No live-capital implication.
