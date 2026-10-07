# HG006-D003 P1 Deterministic Evidence-Anchor Episode Generator v1

Status: **FROZEN AFTER HG006-L001-P2 PASSED, BEFORE HISTORICAL TERMINAL LABELS ARE OPENED**  
Frozen: 2026-10-07  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Make the already-frozen HG006-D003 episode-threading contract executable without allowing
historical completion/failure evidence to influence transaction grouping.

The generator consumes only transaction identity anchors extracted by the validated
HG006-L001 layer. It explicitly ignores:

- stage observations;
- explicit terminal-language state;
- terminal evidence;
- stock prices/returns;
- future company status.

## Frozen inputs

### Full historical LLM ingestion

- execution: `HG006-L001-P2-v1`;
- run: `37638982587`;
- artifact: `11491395735`;
- ingestion SHA-256:
  `2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6`;
- validated requests: 1,448 / 1,448;
- evidence-ready chronologies covered: 298 / 298.

### Deterministic historical evidence pack

- `HG006-S002-v1`;
- run: `37416075608`;
- artifact: `11390794744`;
- pack SHA-256:
  `e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e`.

The validated L001 responses contain exactly 1,564 distinct canonical event IDs.

## Scope

Families:

- PREFERENTIAL_WARRANT;
- SCHEME_REORGANISATION.

No cross-family or cross-symbol episode is possible.

## Event anchor aggregation

For each canonical event ID, aggregate only:

- symbol;
- frozen family;
- exact document IDs;
- exact L001 `transaction_anchors`.

The same event may be referenced by multiple documents.

Anchor values are canonical JSON values. No fuzzy string similarity is used.

## Strong episode-link anchors

Two events may be linked only when they share at least one frozen strong token.

### SCHEME_REORGANISATION

Direct strong anchors:

- SCHEME_OR_TRANSACTION_NAME;
- CASE_ORDER_REFERENCE;
- BOARD_APPROVAL_DATE;
- OTHER_EXPLICIT_TRANSACTION_REFERENCE;
- EFFECTIVE_DATE;
- REGULATORY_OR_COURT_ORDER_DATE.

Composite strong anchors:

- exact TARGET_OR_TRANSFEROR + exact TRANSFEREE_OR_RESULTING_ENTITY;
- exact RECORD_DATE + exact ENTITLEMENT_OR_EXCHANGE_RATIO.

### PREFERENTIAL_WARRANT

Direct strong anchors:

- BOARD_APPROVAL_DATE;
- SHAREHOLDER_APPROVAL_DATE;
- OTHER_EXPLICIT_TRANSACTION_REFERENCE;
- ALLOTTEE_OR_ALLOTTEE_GROUP.

Composite strong anchors:

- exact OFFER_OR_ISSUE_PRICE + exact SECURITY_COUNT;
- exact OFFER_OR_ISSUE_PRICE + exact OFFER_OR_ISSUE_SIZE.

SECURITY_TYPE alone is never sufficient.

Time proximity is never sufficient.

## Graph construction

Within each exact source chronology:

1. create one node per canonical event ID;
2. create an undirected edge only when two nodes share an exact strong token;
3. take connected components;
4. never connect events across source chronologies.

Transitive closure is allowed only inside this strong-anchor graph.

## Hard identity-conflict gate

A connected component is THREAD_AMBIGUOUS when it contains more than one distinct
explicit value for any frozen hard identity field.

### SCHEME_REORGANISATION hard identity fields

- SCHEME_OR_TRANSACTION_NAME;
- CASE_ORDER_REFERENCE;
- BOARD_APPROVAL_DATE.

### PREFERENTIAL_WARRANT hard identity fields

- BOARD_APPROVAL_DATE;
- SHAREHOLDER_APPROVAL_DATE;
- OTHER_EXPLICIT_TRANSACTION_REFERENCE.

A conflict is not resolved by choosing the value associated with a more favorable
transaction outcome.

## Singleton rule

A one-event component is EPISODE_ASSIGNED only when that event contains at least one
frozen strong token.

An event with no frozen strong token is THREAD_AMBIGUOUS.

This is deliberately conservative: insufficient identity evidence is excluded from
base-rate denominators instead of being guessed into a transaction.

## Episode sealing

For every EPISODE_ASSIGNED component:

- pass the raw manifest through the already-frozen
  `validate_episode_manifest` implementation;
- use the deterministic D003 episode hash;
- retain source chronology ID;
- retain exact document IDs;
- retain earliest/latest official chronology timestamps;
- retain the strong token(s) that caused assignment;
- retain existing D003 shared-anchor support.

Timestamp is metadata only and does not create an episode link.

## Event accounting

The final P1 result must account for all 1,564 L001 event IDs exactly once as:

- EPISODE_ASSIGNED; or
- THREAD_AMBIGUOUS.

The two HG006-S002 TEXT_UNAVAILABLE chronologies contain no retained event IDs and remain
reported separately. They do not create synthetic events.

## Frozen feasibility gates

P1 passes only when all are true:

1. exactly 1,564 source event IDs are accounted for once;
2. every assigned episode stays inside one symbol/family/source chronology;
3. every assigned episode has at least one frozen strong token;
4. no assigned episode violates a hard identity conflict;
5. the frozen D003 validator accepts the complete manifest;
6. at least 30 assigned episodes exist in each priority family;
7. no stage observation, terminal-language state or market outcome is used for grouping.

Thresholds may not be lowered after P1 output is opened.

## Promotion

Passing P1 permits HG006-D002 terminal labeling on the sealed episodes.

It does not itself open or assign terminal states.

## Scientific boundary

P1 does not:

- infer transaction completion;
- treat absence of future filing as failure;
- use terminal language to group episodes;
- calculate completion rates;
- use stock returns;
- assign current-company probability;
- create expected return or investment advice.
