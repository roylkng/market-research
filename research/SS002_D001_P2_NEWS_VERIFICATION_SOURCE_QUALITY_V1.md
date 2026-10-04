# SS002-D001 P2 News-Verification Source-Quality Amendment v1

Status: **FROZEN AFTER P1 SOURCE-ONLY MATERIALIZATION, BEFORE P2 MATERIALIZATION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P2 exists

P1 correctly separated generic SAST disclosures from live offer/control events and
created 1,666 current-primary events, but seven lacked official NSE attachment URLs.

A source-only audit found that all seven are exchange-generated `News Verification`
requests asking issuers to clarify media reports. They are not issuer transaction
documents.

For every one of those seven cases, the frozen announcement corpus also contains a
separate issuer response with an official NSE attachment.

P1 remains failed.

## Frozen input

Use exactly:

- P1 run: `37201373926`;
- artifact: `11302573796`;
- P1 census SHA-256:
  `2d0f39e218cdb1784d390a45685f0e787cff9edb4443a2c395d8806219213e2c`.

P2 performs no new announcement acquisition.

## Frozen routing amendment

A P1 `CURRENT_ACTIONABLE_PRIMARY` row becomes
`CURRENT_UNCONFIRMED_NEWS_QUERY` when:

1. `desc` equals `News Verification` case-insensitively; and
2. `attchmntFile` is absent, `-`, or not an official NSE archive URL.

Such a row remains in the event corpus but is excluded from attachment acquisition and
cannot supply transaction terms.

A `News Verification` row with an official NSE attachment remains
`CURRENT_ACTIONABLE_PRIMARY`. It represents the issuer's attached clarification
evidence and is eligible for document underwriting.

No title-text inference can promote an unconfirmed query.

## P2 feasibility gates

P2 passes only if:

1. exact P1 census hash matches;
2. all 6,435 P1 events are accounted for exactly once;
3. every remaining CURRENT_ACTIONABLE_PRIMARY event is an exact current-identity match;
4. every remaining CURRENT_ACTIONABLE_PRIMARY event has an official NSE attachment;
5. every event demoted to CURRENT_UNCONFIRMED_NEWS_QUERY has `desc=News Verification`;
6. no return outcomes or model fitting are opened.

## Promotion

Passing P2 authorizes SS002-D002 attachment acquisition for the remaining
CURRENT_ACTIONABLE_PRIMARY queue.

The unconfirmed-news rows remain available for linkage to later issuer responses but
cannot independently create an investment thesis.

## Scientific boundary

No return, price, valuation or subsequent transaction-success outcome was used to derive
P2.
