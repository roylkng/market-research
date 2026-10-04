# EI001-D002 Full-Market Same-Quarter Comparative Fact Plane v1

Status: **FROZEN BEFORE FULL-MARKET PRIOR-YEAR SOURCE ACQUISITION**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Objective

Materialize exact Q1 FY27 versus Q1 FY26 same-basis comparable financial facts across the
2,319-name SS001 universe.

D002 is a comparative fact plane only. It does not calculate an earnings-inflection score.

## Frozen current source

Use exactly FA001-D002-v1:

- run `37213394690`;
- artifact `11306919543`;
- panel SHA-256
  `cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124`.

Current period end: `2026-06-30`.

For each symbol use the exact current-quarter accounting basis and READY fact values already
sealed in FA001-D002. Current filing bytes are not reinterpreted in EI001-D002.

## Frozen prior-year source

Prior period end: `2025-06-30`.

For each symbol with a READY FA001 current quarter:

1. acquire official NSE Integrated Filing - Financials discovery for the symbol;
2. require exactly the same accounting basis as the current FA001 source;
3. select the earliest official exact-period filing under the existing FA001 candidate
   semantics;
4. fetch exact official XBRL bytes;
5. parse one 80-100 day non-dimensional quarter context using the EI001-P1 parser.

No alternate basis or reconstructed quarter is allowed.

## Frozen comparable families

Exactly:

- revenue;
- PAT;
- PBT;
- finance costs;
- depreciation/amortisation;
- basic EPS.

A family is COMPARABLE_READY only when current and prior values are deterministic and
unitRef strings match exactly.

D002 retains raw current/prior values. It does **not** calculate percentage growth.

## Deterministic shards

Exactly six shards:

`int(SHA256(symbol),16) mod 6`.

Every frozen identity appears exactly once after merge.

## Frozen feasibility gates

D002 passes only if all are true:

1. exactly 2,319 identities are accounted for;
2. >=80% have a READY FA001 current Q1 source;
3. >=65% have a same-basis exact prior-year Q1 candidate;
4. >=60% have COMPARABLE_READY revenue + PAT;
5. >=55% have COMPARABLE_READY revenue + PAT + PBT;
6. every READY prior source is bound to official bytes and SHA-256;
7. no analyst estimate, stock return, LLM output or valuation enters source selection.

Thresholds may not be lowered after D002 output is opened.

## Promotion

Passing D002 permits a separately frozen EI001-S001 inflection candidate screen using
deterministic YoY growth, margin and earnings-direction transforms.

D002 does not authorize portfolio eligibility or live capital.
