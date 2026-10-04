# EI001-D001 P1 Separate Prior-Year Q1 Filing Amendment v1

Status: **FROZEN AFTER D001 SOURCE FAILURE, BEFORE P1 SOURCE RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P1 exists

EI001-D001 proved that current Q1 FY27 NSE Integrated Filing XBRL does not embed a
non-dimensional prior-year Q1 duration context. The 47 usable current filings all expose
the current 2026-04-01 through 2026-06-30 quarter, while the frozen
2025-06-30 embedded-context search produced zero comparable facts.

No stock returns, valuation outputs, later earnings outcomes or LLM judgments were
opened.

Source-only inspection of the already-captured NSE discovery bytes shows 43/48 frozen
sample symbols have an exact 2025-06-30 official filing on the same accounting basis as
their selected 2026-06-30 filing.

## P1 source repair

P1 compares two exact official Q1 filings instead of requiring prior-year facts inside
the current filing.

### Current filing

Exact period end:

`2026-06-30`

Use the same FA001 selection rule already frozen in D001.

### Prior-year filing

Exact period end:

`2025-06-30`

Require exactly the same accounting basis selected for the current filing.

Select the earliest official NSE Integrated Filing - Financials source at that period
end and basis using the existing exact FA001 candidate semantics.

No legacy/non-integrated source, alternate basis, reconstructed quarter or fuzzy issuer
mapping is introduced.

## Frozen quarter context inside each filing

Within each source independently require:

- non-dimensional duration context;
- endDate equal to that filing's exact period end;
- duration 80-100 calendar days.

Thus:

- current Q1 context ends 2026-06-30;
- prior Q1 context ends 2025-06-30.

## Frozen fact families

Unchanged from D001:

- revenue;
- PAT;
- PBT;
- finance costs;
- depreciation/amortisation;
- basic EPS.

Alias precedence remains exactly the FA001 frozen order.

## Comparable readiness

A family is COMPARABLE_READY only when:

1. the current source has one deterministic numeric quarter fact;
2. the prior-year source has one deterministic numeric quarter fact;
3. both have non-empty unitRef;
4. unitRef strings match exactly;
5. both source URLs and exact bytes are retained with SHA-256.

No currency/unit conversion is allowed in P1.

## Frozen feasibility gates

The D001 numeric gates remain unchanged in spirit and become source-pair gates:

1. at least 40/48 sample symbols have usable current Q1 XBRL;
2. at least 40/48 have an exact same-basis prior-year Q1 filing candidate;
3. among symbols with both sources, >=75% have COMPARABLE_READY revenue;
4. >=75% have COMPARABLE_READY PAT;
5. >=70% have both revenue and PAT COMPARABLE_READY;
6. >=60% have revenue, PAT and PBT COMPARABLE_READY.

Thresholds may not be lowered after P1 output is opened.

## Scientific boundary

P1 remains source feasibility only. It does not calculate growth, margin change,
earnings acceleration, valuation or expected return.
