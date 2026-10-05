# HG006-D001 Historical Discrete-Event Base-Rate Source Census v1

Status: **FROZEN BEFORE HISTORICAL SOURCE ACQUISITION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Completion probabilities assigned: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Build a historical, outcome-auditable source corpus for discrete special-situation stage
transitions before assigning any completion probability to current HG005/HG006 cases.

D001 is source census only. It does not estimate a base rate.

## Why this stage exists

HG005-D003 now exposes payoff hurdles for the current five-name underwriting set, but
expected value cannot be calculated responsibly without separating:

1. discrete-event completion probability; and
2. operating/economic scenario probability.

HG006-D001 addresses only the first category.

It must not be used to assign probabilities to EBITDA, utilization, margin, valuation
multiple or capital-deployment success.

## Historical initiation cohort

Freeze event initiations to:

- start: 2023-01-01;
- end: 2025-12-31 inclusive.

Current 2026 hidden-gem candidates therefore cannot enter the historical initiation
cohort.

## Follow-up observation window

Acquire complete whole-market NSE announcement evidence through:

- 2026-09-30 inclusive.

Thus an initiation in 2025 may have up to nine months of 2026 follow-up evidence.

Events without a resolved terminal stage by the observation cutoff remain right-censored.
They are not counted as failures.

## Official source

Use the exact NSE whole-market corporate-announcement discovery endpoint already audited
for SS002:

`/api/corporate-announcements?index=equities&from_date=<DD-MM-YYYY>&to_date=<DD-MM-YYYY>`

Acquire exactly one calendar day per request from 2023-01-01 through 2026-09-30.

Retain exact raw source bytes and SHA-256 for every day.

No search engine, news article or secondary database may replace a failed NSE day.

## Canonical announcement identity

Reuse:

`marketlab.alpha_announcements.normalize_announcement_payload`

Every canonical announcement identity must be unique across the full daily union.

A duplicated or conflicting canonical identity fails closed.

## Frozen event taxonomy

Reuse the precise SS002-P1 taxonomy semantics from current `main`.

HG006-D001 retains only discrete event families with a reasonably definable terminal
transaction state:

- BUYBACK;
- OPEN_OFFER_CONTROL;
- DELISTING;
- SCHEME_REORGANISATION;
- RIGHTS_ISSUE;
- PREFERENTIAL_WARRANT;
- CAPITAL_REDUCTION;
- OFFER_FOR_SALE;
- TENDER_OFFER.

Explicitly exclude from completion-base-rate construction:

- ASSET_SALE_DIVESTMENT;
- INSOLVENCY_RESOLUTION.

Those families require separate outcome definitions.

## Candidate chronology

For every retained candidate announcement retain:

- canonical announcement_id;
- symbol;
- seq_id;
- exchange publication timestamp;
- source day;
- category or categories;
- desc;
- attchmntText;
- exact official attachment URL when approved;
- daily raw SHA-256.

D001 does not infer initiation vs follow-up stage.

## Initiation eligibility

For source-feasibility counting only, a symbol-family chronology is considered a
historical candidate chronology when:

- at least one retained family announcement exists during 2023-01-01 through 2025-12-31.

All later family announcements through 2026-09-30 remain attached to that chronology as
possible follow-up evidence.

D001 does not yet decide which announcement is the formal transaction initiation.

## Frozen source-feasibility gates

D001 passes only if all are true:

1. every calendar day from 2023-01-01 through 2026-09-30 is acquired;
2. canonical announcement identities are globally unique across daily sources;
3. every retained row belongs to one of the frozen discrete families;
4. at least 30 historical symbol-family chronologies exist for SCHEME_REORGANISATION;
5. at least 30 historical symbol-family chronologies exist for PREFERENTIAL_WARRANT;
6. at least 150 historical symbol-family chronologies exist across all frozen families;
7. at least 90% of historical candidate chronologies have at least one approved official
   attachment URL somewhere in their observed chronology.

Thresholds may not be lowered after D001 output is opened.

## D001 output

Produce:

- total canonical source rows;
- retained discrete-event rows;
- retained symbols;
- historical symbol-family chronology count;
- counts by family;
- initiation-cohort counts by family;
- approved-attachment chronology coverage;
- daily source hashes;
- exact retained announcement rows;
- explicit right-censoring boundary metadata.

## Promotion

Passing D001 permits:

- HG006-D002 document acquisition / reuse against the historical chronology set;
- HG006-L001 evidence-bound transaction stage extraction;
- HG006-D003 deterministic chronology synthesis;
- only then, a separately frozen historical completion/base-rate estimator.

## Probability boundary

D001 does **not**:

- define completion;
- assign terminal success/failure;
- estimate a completion probability;
- assume unresolved events failed;
- use current HG005 company outcomes;
- weight HG005 payoff surfaces;
- calculate expected return.

## Current HG005 boundary

The following current uncertainties remain outside HG006-D001 base-rate scope:

- DEVX Winston EBITDA realization;
- NPST post-raise EBITDA realization;
- SAMBHV Phase-I utilization / EBITDA per tonne;
- ANANTRAJ separated-business valuation multiple;
- INOXGREEN blocked source gaps.

Only the discrete transaction-stage probability components may eventually consume
HG006 historical base rates.

## Scientific boundary

No D001 output creates:

- target price;
- buy/sell/hold;
- expected return;
- ADO/PF001 eligibility;
- live-capital authorization.
