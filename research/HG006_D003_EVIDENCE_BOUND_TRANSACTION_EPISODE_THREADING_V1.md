# HG006-D003 Evidence-Bound Historical Transaction Episode Threading v1

Status: **FROZEN BEFORE HISTORICAL TERMINAL LABELS ARE OPENED**  
Frozen: 2026-10-05  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert HG006-D001 symbol-family source chronologies into distinct transaction episodes
without collapsing unrelated transactions by the same issuer.

D001 symbol-family chronologies are source containers, not probability observations.

## Input boundary

D003 may consume only:

- HG006-D001 retained canonical announcement IDs;
- exact official documents acquired from approved NSE archive URLs;
- deterministic text segments;
- evidence-bound LLM extraction under the frozen SS002-L001 contract or a separately
  frozen HG006 historical-stage extension.

No web/news/model-memory facts may create or merge an episode.

## Episode identity

Every retained historical event must be assigned exactly one of:

- EPISODE_ASSIGNED;
- THREAD_AMBIGUOUS;
- DOCUMENT_UNAVAILABLE.

Only EPISODE_ASSIGNED events may contribute to historical base-rate episodes.

## Hard grouping constraints

Events may be grouped only when all are true:

1. same exact NSE symbol;
2. same exact frozen transaction family;
3. evidence contains at least one consistent transaction anchor;
4. no material anchor conflict exists.

No episode may cross symbol or family boundaries.

## Transaction anchors

At least one explicit anchor is required.

### BUYBACK

Preferred anchors:

- board approval date;
- buyback price;
- maximum buyback amount / number of shares;
- record date;
- tender-offer/public-announcement reference.

### OPEN_OFFER_CONTROL

Preferred anchors:

- acquirer;
- target;
- public-announcement date;
- offer price;
- offer size;
- SEBI/open-offer reference.

### DELISTING

Preferred anchors:

- delisting proposal/board date;
- acquirer/promoter;
- floor/discovered price;
- offer reference;
- shareholder approval date.

### SCHEME_REORGANISATION

Preferred anchors:

- scheme name;
- transferor/transferee/resulting entities;
- board approval date;
- appointed/effective date;
- NCLT/tribunal case/order reference;
- exchange ratio.

### RIGHTS_ISSUE

Preferred anchors:

- board approval date;
- record date;
- rights entitlement ratio;
- issue price;
- issue opening/closing dates.

### PREFERENTIAL_WARRANT

Preferred anchors:

- board/shareholder approval date;
- security type;
- number of securities;
- issue price;
- named allottee group;
- exchange in-principle application/reference.

A later warrant exercise/conversion belongs to the same issuance episode only when
evidence explicitly links it to that issuance.

### CAPITAL_REDUCTION

Preferred anchors:

- scheme/proposal name;
- board/shareholder date;
- reduction ratio/terms;
- tribunal/order reference.

### OFFER_FOR_SALE

Preferred anchors:

- seller;
- sale dates;
- base/oversubscription size;
- floor price;
- exchange notice reference.

### TENDER_OFFER

Preferred anchors:

- offeror;
- target/security;
- tender/opening date;
- offer price;
- offer reference.

## Time proximity is insufficient

Time gap may support an already evidenced match but may not be the sole episode anchor.

Two transactions within days remain separate when terms/parties/references differ.

A transaction with long procedural gaps remains one episode when explicit references
remain consistent.

## Evidence-bound LLM role

The model may:

- extract transaction anchors;
- state whether two events explicitly refer to the same transaction;
- cite segment IDs.

The model may not:

- group events merely because they seem related;
- use stock-price behavior;
- infer unseen corporate history;
- assign completion probability.

## Episode manifest

Each episode retains:

- deterministic episode_id;
- symbol;
- family;
- canonical event IDs;
- document IDs;
- anchor facts with evidence references;
- earliest observed event timestamp;
- latest observed event timestamp;
- threading confidence state;
- ambiguity notes.

episode_id is a deterministic hash of the validated symbol, family and sorted canonical
event IDs after threading is sealed.

## Ambiguity

When two plausible episode assignments remain supported:

- state = THREAD_AMBIGUOUS;
- do not choose the assignment with the more favorable outcome;
- exclude the ambiguous set from the base-rate denominator;
- report it separately.

## Scientific boundary

D003 does not:

- assign terminal success/failure;
- calculate completion rates;
- use market returns;
- estimate current-company probability;
- create expected return or investment advice.
