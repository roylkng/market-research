# AE001 D003 NSE Corporate-Announcement Source Audit v1

Status: FROZEN BEFORE FIRST D003 SOURCE QUERY
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Determine whether NSE's official corporate-announcement API can support a
broad, point-in-time historical event feature family without silent range
truncation or symbol-scope inconsistencies.

D003 is a source-quality audit only. It opens no market-return outcomes and
tests no alpha.

## Official source

NSE corporate announcement endpoint:

    /api/corporate-announcements

Parameters:

- index = equities;
- from_date;
- to_date;
- optional symbol.

Exact HTTP response bytes are retained content-addressed in the workflow
artifact.

## Frozen audit window

2026-09-15 through 2026-09-21 inclusive.

This window was selected before the first D003 query.

## Frozen source queries

### A. Whole-window, whole-market

One query with no symbol for the full frozen seven-calendar-day window.

### B. Daily whole-market reconstruction

Seven no-symbol queries, one per calendar date from 2026-09-15 through
2026-09-21 inclusive.

### C. Symbol-scoped reconciliation

The exact same seven-day range is queried separately for these ten symbols:

- RELIANCE
- TCS
- INFY
- LT
- HDFCBANK
- ICICIBANK
- SBIN
- BHARTIARTL
- ITC
- MARUTI

The sample is frozen before source access and is not selected from observed
announcement activity.

## Canonical announcement identity

For comparison, one NSE row is identified by a canonical hash of:

- symbol;
- seq_id;
- official exchange dissemination timestamp;
- desc;
- attchmntText;
- attchmntFile.

The official timestamp parser accepts the same NSE fields already used by H003:

- exchdisstime;
- an_dt;
- sort_date;
- dt.

Rows missing symbol, seq_id, or an official timestamp fail closed.

## Primary completeness gates

D003 passes only if all are true:

1. the full-window whole-market response parses;
2. all seven daily whole-market responses parse;
3. there are no duplicate canonical identities within any query;
4. full-window identity set exactly equals the union of daily identity sets;
5. for each frozen sample symbol, the symbol-scoped identity set exactly equals
   the subset of the whole-window identity set for that symbol;
6. no same canonical identity has conflicting semantic fields;
7. all observed official timestamps fall inside the requested date range in
   Asia/Kolkata calendar time.

No approximate equality is allowed.

## Response-cap diagnostics

The audit records, but does not pre-assume:

- full-window row count;
- daily row counts;
- maximum daily row count;
- distinct symbols;
- maximum rows for one symbol;
- whether observed counts exceed common round-number thresholds
  100 / 200 / 500 / 1000.

These diagnostics inform the historical acquisition design.

## Promotion rule

If D003 passes, T007 may use daily whole-market queries as its historical
announcement source for a separately frozen feature/model trial.

If D003 fails, T007 historical modeling is blocked until a new source strategy
is frozen. Failure may not be repaired by dropping discrepant rows after
looking at returns.

## Non-goals

- no attachment-body extraction;
- no LLM classification;
- no return labels;
- no investment ranking;
- no prospective claim;
- no live capital.
