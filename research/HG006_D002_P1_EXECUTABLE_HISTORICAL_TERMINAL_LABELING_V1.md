# HG006-D002 P1 Executable Historical Terminal Labeling v1

Status: **FROZEN BEFORE HISTORICAL TERMINAL LABELS ARE OPENED**  
Frozen: 2026-10-07  
Current-company probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Make the already-frozen HG006-D002 family outcome ontology executable on the exact
333 historical transaction episodes sealed by HG006-D003-P2.

This stage opens historical transaction terminal states for the first time.

It does **not** use stock returns and does not assign current-company probabilities.

## Frozen inputs

### D003 sealed episode threads

- diagnostic: `HG006-D003-P2-v1`;
- run: `37652989339`;
- artifact: `11496927493`;
- threading SHA-256:
  `4d4a58bf7179305ee134a098bd063436bef060077b785056e499d9c885a8d250`;
- episode count: 333;
- family counts:
  - PREFERENTIAL_WARRANT: 151;
  - SCHEME_REORGANISATION: 182.

### Full historical L001 ingestion

- execution: `HG006-L001-P2-v1`;
- run: `37638982587`;
- artifact: `11491395735`;
- ingestion SHA-256:
  `2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6`;
- validated requests: 1,448 / 1,448.

### Historical evidence pack

- `HG006-S002-v1`;
- run: `37416075608`;
- artifact: `11390794744`;
- pack SHA-256:
  `e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e`.

## Observation cutoff

Historical observation cutoff is exactly:

`2026-09-30`

No filing after this date may influence a historical label.

## Source attribution

A validated L001 extraction may contribute to one sealed episode only when:

1. at least one extraction event_id belongs to the episode;
2. **all** extraction event_ids are contained within the episode event set;
3. extraction document_id is one of the episode document_ids;
4. extraction symbol/family exactly equals episode symbol/family;
5. the document has an exact official chronology timestamp in HG006-S002.

A document spanning event IDs outside the sealed episode is not used for terminal
classification of that episode. This fails conservative rather than spreading one
document's terminal language across ambiguous episode boundaries.

## Official-observation date

For stage and terminal timing, use the Asia-neutral UTC calendar date of the first
official retained document that explicitly establishes the state.

Economic effective dates mentioned inside a document are retained as anchors but do
not backdate when the market could first observe the terminal state.

## Common terminal classes

Exactly one primary state per sealed episode:

- COMPLETED;
- FAILED_OR_WITHDRAWN;
- RIGHT_CENSORED;
- UNRESOLVED_SOURCE_CONFLICT.

RIGHT_CENSORED is never counted as failure.

## Conflict rule

An episode is `UNRESOLVED_SOURCE_CONFLICT` when either:

1. any contributing extraction has
   `CONFLICTING_TERMINAL_LANGUAGE`; or
2. deterministic completion evidence and deterministic failure evidence are both
   present within the same sealed episode.

Chronological order does not automatically resolve the conflict. A separately frozen
lineage rule would be required to treat a failed proposal followed by a later
re-launched transaction as the same episode.

## SCHEME_REORGANISATION

### COMPLETED

Completion evidence exists when any contributing extraction has either:

1. explicit stage `TRANSACTION_COMPLETED`; or
2. `EXPLICIT_COMPLETION_LANGUAGE` **and** an explicit
   `EFFECTIVE_DATE` anchor in that same extraction.

The second rule encodes the frozen ontology requirement that the scheme be stated as
effective/operative.

The following are **not sufficient** by themselves:

- REGULATORY_OR_COURT_APPROVED;
- SHAREHOLDER_APPROVED;
- an NCLT sanction/order;
- an observation letter;
- a board approval.

### FAILED_OR_WITHDRAWN

Failure evidence exists when any contributing extraction has either:

- stage `CANCELLED_OR_WITHDRAWN`; or
- `EXPLICIT_FAILURE_OR_WITHDRAWAL_LANGUAGE`.

## PREFERENTIAL_WARRANT

D002-P1 emits two outcome tracks.

### Primary track: issuance_completion

#### COMPLETED

Only explicit stage `ALLOTMENT_COMPLETED` is sufficient.

Proposal, shareholder approval, exchange in-principle approval or issue pricing is
non-terminal.

#### FAILED_OR_WITHDRAWN

Failure evidence exists when any contributing extraction has either:

- stage `CANCELLED_OR_WITHDRAWN`; or
- `EXPLICIT_FAILURE_OR_WITHDRAWAL_LANGUAGE`.

### Secondary track: full_economic_exercise

#### COMPLETED

Only explicit stage:

`WARRANT_EXERCISE_OR_CONVERSION_COMPLETED`

is sufficient.

A warrant allotment alone does not complete the full-economic-exercise track.

#### FAILED_OR_WITHDRAWN

The same explicit cancellation/withdrawal evidence used above is terminal failure for
the tracked issuance's full-exercise question.

If issuance is completed but no explicit full-exercise terminal state is observed by
the cutoff, the secondary track is RIGHT_CENSORED.

## Terminal date

For COMPLETED or FAILED_OR_WITHDRAWN, terminal_date is the earliest official document
date providing the corresponding deterministic terminal evidence.

Terminal date must satisfy:

`entry_date <= terminal_date <= 2026-09-30`.

For RIGHT_CENSORED and UNRESOLVED_SOURCE_CONFLICT, terminal_date is null.

## Entry date

`entry_date` is the UTC calendar date of the episode's
`earliest_observed_at_utc` from sealed D003 threading.

This is a first-observed point, not a reconstructed unseen proposal date.

## Stage-history output

For every episode retain the first official observed date of each explicitly extracted
frozen stage:

- BOARD_APPROVED;
- SHAREHOLDER_APPROVED;
- REGULATORY_OR_COURT_APPROVED;
- PUBLIC_ANNOUNCEMENT;
- RECORD_DATE_FIXED;
- OFFER_OPEN;
- OFFER_CLOSED;
- ALLOTMENT_COMPLETED;
- WARRANT_EXERCISE_OR_CONVERSION_COMPLETED;
- TRANSACTION_COMPLETED;
- CANCELLED_OR_WITHDRAWN.

Only evidence-bound L001 stage observations count.

## Frozen validation gates

D002-P1 passes only when all are true:

1. exactly 333 sealed D003 episodes are labeled once;
2. every episode identity exactly matches D003;
3. every terminal evidence document belongs to the sealed episode;
4. every completed/failed state has at least one terminal evidence document;
5. RIGHT_CENSORED episodes carry no terminal date;
6. terminal dates lie within the observed risk interval and cutoff;
7. PREFERENTIAL_WARRANT primary and secondary tracks remain distinct;
8. no market-return field or current-company outcome is consumed.

No minimum completed/failed count is imposed here. D004's already-frozen publication
thresholds decide whether a base rate is statistically publishable.

## Promotion

Passing D002-P1 permits execution of the already-frozen HG006-D004 stage-conditioned
base-rate estimator.

## Scientific boundary

D002-P1 does not:

- use absence of later filings as failure;
- use current company status;
- use stock returns;
- calculate completion probabilities;
- assign current-case probability;
- calculate expected return;
- create investment advice or portfolio eligibility.
