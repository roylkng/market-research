# SS002-D001 P1 Current-Actionable Taxonomy and Identity Amendment v1

Status: **FROZEN AFTER D001 SOURCE CENSUS, BEFORE P1 MATERIALIZATION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P1 exists

SS002-D001 successfully acquired every frozen calendar-day announcement source and built
6,435 canonical candidate events, but failed the frozen >=90% current-identity mapping
gate at 83.99%.

D001 remains failed.

A source-only diagnosis of the D001 event corpus found two deterministic semantic issues:

1. 424 of 662 insolvency events and 12 of 21 delisting events refer to symbols that are
   no longer current Oct-1 EQ identities. Their non-mapping is economically meaningful,
   not evidence that the announcement source is incomplete.
2. D001's `OPEN_OFFER_CONTROL` bucket included the generic phrase
   `substantial acquisition of shares`. Of 4,268 events in that bucket, 4,165 contain
   only that generic SAST phrase, while 103 contain `open offer`, `takeover offer`,
   or `change of control`.

No return or price outcomes were used in this diagnosis.

## Frozen input

Use exactly the failed D001 census:

- run: `37200055447`;
- artifact: `11302657330`;
- census SHA-256:
  `0e831d4ce29d03e6916d4e244d177f2ee1451ce98d35c0a37e50e0e79b12fa54`.

P1 performs no new announcement acquisition.

## P1 taxonomy

All D001 categories except `OPEN_OFFER_CONTROL` retain their original frozen tokens.

D001 `OPEN_OFFER_CONTROL` events are reclassified from their already-retained
`desc + attchmntText` only.

### LIVE_OPEN_OFFER_CONTROL

At least one exact case-insensitive token:

- `open offer`;
- `takeover offer`;
- `change of control`.

### SAST_DISCLOSURE

Token:

- `substantial acquisition of shares`.

An event may be both LIVE_OPEN_OFFER_CONTROL and SAST_DISCLOSURE when both semantics are
present.

`SAST_DISCLOSURE` is ownership/control context, not a primary special-situation
attachment queue by itself.

## Frozen current-actionability states

### CURRENT_ACTIONABLE_PRIMARY

All are true:

- D001 mapping state is `CURRENT_IDENTITY_MAPPED`;
- event has at least one primary P1 category.

Primary categories are:

- BUYBACK;
- LIVE_OPEN_OFFER_CONTROL;
- DELISTING;
- SCHEME_REORGANISATION;
- RIGHTS_ISSUE;
- PREFERENTIAL_WARRANT;
- ASSET_SALE_DIVESTMENT;
- INSOLVENCY_RESOLUTION;
- CAPITAL_REDUCTION;
- OFFER_FOR_SALE;
- TENDER_OFFER.

### CURRENT_CONTEXT_ONLY

Current identity is mapped, but the event has no primary category after P1. In v1 this
is primarily generic SAST disclosure context.

### HISTORICAL_OR_NONCURRENT

D001 mapping state is `CURRENT_IDENTITY_UNMAPPED`.

These rows remain in the corpus for historical research and future identity-history work.
They are not counted as failures of the current opportunity queue.

No fuzzy symbol/name mapping is introduced.

## P1 feasibility gates

P1 passes only when all are true:

1. input D001 census hash matches exactly;
2. all 6,435 D001 candidate events are reclassified exactly once;
3. every D001 OPEN_OFFER_CONTROL event is fully accounted for by
   LIVE_OPEN_OFFER_CONTROL and/or SAST_DISCLOSURE;
4. every CURRENT_ACTIONABLE_PRIMARY event remains an exact D001 current-identity match;
5. every CURRENT_ACTIONABLE_PRIMARY event has an official NSE attachment URL;
6. no return outcomes or model fitting are opened.

There is intentionally no minimum current-mapping percentage in P1. Current mapping is
a routing property, while the historical/non-current corpus remains legitimate source
evidence.

## Promotion

Passing P1 authorizes a separately frozen SS002-D002 attachment acquisition layer for
CURRENT_ACTIONABLE_PRIMARY events.

The attachment layer may deduplicate repeated filings and identify canonical transaction
documents before LLM extraction.

It does not authorize an investment ranking.

## Scientific boundary

P1 does not:

- use future returns;
- estimate spreads or intrinsic value;
- infer transaction terms from announcement titles;
- use LLM judgment;
- drop historical/non-current events;
- create ADO/PF001 eligibility;
- permit live capital.
