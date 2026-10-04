# EI001-D002 Full-Market Same-Quarter Comparative Fact Plane v1

Status: **FROZEN BEFORE FULL-MARKET PRIOR-Q1 ACQUISITION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Build a full-market current-vs-prior-year Q1 fact plane using exact official NSE filings.

D002 is a source/fact plane only. It does not calculate YoY growth, rank companies, or
define an earnings-inflection score.

## Frozen identity universe

Use exactly the 2,319 SS001-D001 current NSE EQ identities already carried by the passed
FA001-D002 panel.

Authoritative current source:

- FA001-D002-v1;
- panel SHA-256:
  `cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124`;
- workflow run: `37213394690`;
- merged artifact ID: `11306919543`.

D002 may not substitute a later current-quarter fact panel.

## Frozen current Q1 facts

Current Q1 FY27 period end:

`2026-06-30`

Reuse only FA001-D002 quarter facts that are already READY under the exact selected
candidate/accounting basis.

Fact families:

- revenue;
- PAT;
- PBT;
- finance costs;
- depreciation/amortisation;
- basic EPS.

No current filing refetch is required.

## Frozen prior-year source

Prior-year Q1 FY26 period end:

`2025-06-30`

For each symbol with an exact FA001 current-quarter candidate:

1. call official NSE Integrated Filing - Financials discovery for that symbol;
2. require exact symbol;
3. require exact 2025-06-30 period end;
4. require the same accounting basis as the current FA001 candidate;
5. select the earliest official source using the frozen FA001 candidate rules;
6. fail closed on same-timestamp multi-URL ambiguity.

Acquire only the selected official prior-year XBRL bytes.

No alternate provider, legacy financial-results source, basis switching or reconstructed
quarter is permitted.

## Frozen prior-year quarter context

Within the prior filing require:

- non-dimensional duration context;
- endDate = 2025-06-30;
- duration 80-100 calendar days.

Use exact EI001-D001-P1 fact aliases and unit semantics.

## Comparable readiness

A family is COMPARABLE_READY only when:

1. the FA001 current fact is READY;
2. the prior-year fact is READY;
3. both unitRef values are non-empty;
4. unitRef strings match exactly.

Retain raw current/prior values, selected concepts, unitRef and exact source provenance.

No growth arithmetic is performed in D002.

## Frozen sharding

Full-market acquisition uses exactly six deterministic shards:

`shard = int(SHA256(upper(symbol)), 16) mod 6`

Each current identity appears in exactly one shard.

The final merger rejects:

- missing shards;
- duplicate symbols;
- wrong-shard symbols;
- fewer or more than 2,319 identities.

Only the merged panel may determine feasibility.

## Frozen feasibility gates

D002 passes only if all are true:

1. exactly 2,319 current identities are accounted for;
2. at least 75% have an exact current Q1 FA001 source candidate;
3. at least 70% have an exact same-basis prior-year Q1 candidate;
4. at least 65% have COMPARABLE_READY revenue and PAT;
5. at least 60% have COMPARABLE_READY revenue, PAT and PBT;
6. no comparable value is reconstructed from arithmetic or external data.

Thresholds may not be lowered after D002 output is opened.

## Promotion

Passing D002 permits a separately frozen EI001-S001 deterministic earnings-inflection
candidate screen.

## Explicit exclusions

D002 does not:

- calculate revenue growth;
- calculate PAT growth;
- calculate margin change;
- calculate acceleration;
- compare to market price;
- use consensus estimates;
- use an LLM;
- assign expected return;
- create ADO/PF001/live-capital eligibility.
