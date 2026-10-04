# SS002-D001 P1 Special-Situation Taxonomy Precision Amendment v1

Status: **FROZEN AFTER D001 SOURCE DIAGNOSTIC, BEFORE P1 RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P1 exists

SS002-D001 acquired all 187 frozen calendar-day announcement sources and preserved
104,001 canonical NSE announcements, but failed its frozen current-identity mapping gate.

The dominant D001 candidate bucket was `OPEN_OFFER_CONTROL` with 4,268 events.

Source-only inspection of the frozen taxonomy identified one overly broad phrase:

`substantial acquisition of shares`

That phrase is standard title/regulatory language for routine disclosures under the
SEBI Substantial Acquisition of Shares and Takeovers framework. Its presence does not
by itself mean an open offer, takeover offer or change-of-control transaction.

No stock returns, valuation outcomes or company-quality outcomes were opened.

## P1 change

The `OPEN_OFFER_CONTROL` token set becomes exactly:

- `open offer`;
- `change of control`;
- `takeover offer`.

Remove:

- `substantial acquisition of shares`.

All other D001 category tokens remain unchanged.

## Frozen source and identity rules

P1 reuses exactly:

- SS001-D001 census SHA:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- announcement window 2026-04-01 through 2026-10-04;
- daily whole-market source acquisition;
- canonical announcement identity;
- exact current-symbol mapping only.

The original minimum current-identity mapping ratio remains **90%**.

It may not be lowered after D001 failure.

## Feasibility gates

P1 passes only when the original D001 gates all pass, including:

- complete daily source coverage;
- unique canonical announcement identities;
- exact symbol mapping only;
- candidate-event current-identity mapping ratio >= 90%.

## Promotion

Passing P1 permits SS002-D002 attachment acquisition and LLM term extraction under a
separately frozen contract.

## Scientific boundary

P1 does not:

- add LLM classification;
- infer transaction terms;
- estimate event probability;
- estimate returns;
- change the mapping threshold;
- authorize portfolio or live-capital use.
