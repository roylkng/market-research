# HG006-P001 Survivor-Conditioned Current Transaction Base-Rate Mapping v1

Status: **FROZEN BEFORE CURRENT-CASE PROBABILITY OUTPUT IS OPENED**  
Frozen: 2026-10-07  
Return outcomes opened: no  
Expected returns calculated: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Map the frozen HG006-D004 historical transaction base-rate evidence onto the exact
current HG004 payoff lanes that have a compatible historical transaction family/stage.

P001 produces empirical current-case completion base-rate surfaces only.

It does not calculate expected return and does not assert that a historical base rate
is the true probability of a specific current transaction.

## Frozen historical inputs

### HG006-D004

- estimator: `HG006-D004-P1-v1`;
- run: `37657805872`;
- artifact: `11498384831`;
- base-rate panel SHA-256:
  `08eddc18599b7dcd86c4a688ef46fc6161a1a52cb49b72cf6695ffbc43ce3084`.

### HG006-D002-P1 terminal labels

- run: `37654933457`;
- artifact: `11497928291`;
- label panel SHA-256:
  `545532620b409135bd867f633de708cfd441e2c532a5b790afeacef9c7de9874`.

The terminal-label panel is required because current cases must be conditioned on how
long they have already survived unresolved after the matched stage.

## Frozen current evidence

### HG004-D001 selection

- run: `37283860083`;
- artifact: `11333720723`;
- selection SHA-256:
  `9b82b337b02d5aa2c58164bf888f76ce50fcd34680077f87f13b0ff5cfc7c102`.

### HG004-L001 evidence-bound extraction

- run: `37296227681`;
- artifact: `11338148751`;
- run SHA-256:
  `a402b39a8890cd2fac3218bb94673f8b9c00b1f325315f9ec93863c22d9a1d12`.

### HG004-L002 payoff-lane synthesis

- run: `37297528769`;
- artifact: `11339427625`;
- synthesis SHA-256:
  `6bd1a43d29460fc18389dfdcb7241c95d1de0acb80b769a728946ef81c031683`.

Current evidence cutoff is exactly:

`2026-10-04`

No filing after this date may advance a current stage under P001-v1.

## Eligible current payoff lanes

Only HG004-L002 lanes with a readiness state beginning with `READY_` may be considered.

Frozen economic-family mapping:

### DEMERGER_ENTITLEMENT

Historical family:

`SCHEME_REORGANISATION`

Historical track:

`transaction_completion`

### DILUTION_FINANCING

Historical family:

`PREFERENTIAL_WARRANT`

Two separate historical tracks:

- `issuance_completion`;
- `full_economic_exercise`.

No other HG004 economic family receives an HG006 probability under P001-v1.

In particular, P001 does not map:

- CAPITAL_DEPLOYMENT_MONITOR;
- ACQUISITION_ECONOMICS;
- RIGHTS_TERMS;
- INTERNAL_REORGANISATION;
- operating or valuation scenarios.

## Evidence-bound family confirmation

For every eligible lane:

1. use only the lane's exact HG004-L002 evidence_document_ids;
2. join those document IDs to validated HG004-L001 outputs;
3. require `economic_relevance = DIRECT_LISTED_SECURITY`;
4. require the mapped HG006 transaction family to appear explicitly in the L001
   `transaction_families` list;
5. require the document to map to an exact HG004-D001 event link and official exchange
   timestamp.

A lane without an exact family-confirming document is:

`NO_EXACT_HISTORICAL_FAMILY_MATCH`

and receives no probability.

## Frozen current stage order

Eligible stage progression is fixed as:

1. PUBLIC_ANNOUNCEMENT;
2. BOARD_APPROVED;
3. SHAREHOLDER_APPROVED;
4. REGULATORY_OR_COURT_APPROVED;
5. RECORD_DATE_FIXED;
6. OFFER_OPEN;
7. OFFER_CLOSED;
8. ALLOTMENT_COMPLETED.

The current stage is the highest-ranked explicitly observed stage in the lane's
family-confirming documents.

Within the selected stage, current_stage_observed_date is the earliest UTC calendar
date on which that stage was officially observed.

PROCEDURAL_UPDATE and UNKNOWN do not advance stage.

## Explicit current terminal states

### SCHEME_REORGANISATION

If a family-confirming current extraction explicitly has:

- TRANSACTION_COMPLETED: current transaction state is deterministically COMPLETED;
- CANCELLED_OR_WITHDRAWN: current transaction state is deterministically
  FAILED_OR_WITHDRAWN.

No historical probability is substituted for an already observed terminal fact.

### PREFERENTIAL_WARRANT / issuance_completion

ALLOTMENT_COMPLETED is the frozen issuance terminal state.

When current evidence explicitly reaches ALLOTMENT_COMPLETED:

- issuance state = CURRENT_TERMINAL_COMPLETED;
- no issuance probability is estimated.

CANCELLED_OR_WITHDRAWN is deterministic failure when explicit.

### PREFERENTIAL_WARRANT / full_economic_exercise

ALLOTMENT_COMPLETED remains an intermediate stage.

P001-v1 does not infer full exercise from allotment.

## Exact-stage publication requirement

For a non-terminal current case, the exact family/track/current-stage surface must have:

`publication_state = PUBLISHABLE_HISTORICAL_BASE_RATE`

in the exact HG006-D004 artifact.

P001 does not:

- search another stage for a more favorable rate;
- fall back from an unsupported current stage to the family-level rate;
- pool unrelated families.

If the exact stage surface is unpublished:

`NO_PUBLISHABLE_EXACT_STAGE_BASE_RATE`

and no current probability is emitted.

## Survivor conditioning

A current case that remains unresolved for X days after its stage is not comparable to
historical cases that already completed/failed/censored before X days.

Define:

`elapsed_days = current_evidence_cutoff - current_stage_observed_date`

Reconstruct the exact D004 historical stage risk set from D002-P1 labels using the frozen
D004-P1 rules.

A historical episode enters the survivor-conditioned risk set only when:

`historical_stage_duration_days > elapsed_days`

This represents an episode that remained event-free with observable follow-up beyond the
current case's elapsed time.

For each retained historical episode:

`residual_duration = historical_stage_duration_days - elapsed_days`

Terminal/censoring cause is unchanged.

This is a left-truncated empirical risk set; no parametric survival model is fitted.

## Conditional publication gate

A survivor-conditioned current probability surface is publishable only when:

- survivor-conditioned support >= 30 episodes;
- future completed + failed terminal outcomes >= 10.

Otherwise:

`INSUFFICIENT_SURVIVOR_CONDITIONED_SUPPORT`

and no point probability is emitted.

The threshold is frozen before current P001 output is opened.

## Future probability horizons

When publishable, estimate competing-risk cumulative incidence from the current evidence
cutoff over exactly:

- next 90 days;
- next 180 days;
- next 365 days;
- next 730 days, only when residual follow-up supports it.

Use the same frozen estimator as D004:

- Aalen-Johansen competing risks;
- 2,000 episode-level bootstrap resamples;
- RNG seed 606001;
- percentile 95% intervals.

A horizon without residual follow-up is:

`INSUFFICIENT_FOLLOW_UP`.

## Output semantics

Published values are named:

`survivor_conditioned_historical_completion_base_rate`

not "true probability".

Every current case retains:

- symbol;
- HG004 economic lane;
- historical family;
- historical track;
- evidence document IDs;
- current stage;
- current stage observed date;
- elapsed days;
- D004 exact-stage publication state;
- survivor-conditioned support / terminal counts;
- future completion/failure CIF + uncertainty when publishable;
- explicit unresolved reason otherwise.

## No case-specific discretionary adjustment

P001-v1 applies **zero** subjective probability adjustment for:

- management quality;
- promoter quality;
- valuation;
- price momentum;
- market sentiment;
- narrative confidence.

Governance and payoff evidence may be displayed alongside P001 later, but cannot modify
the probability without a separately frozen protocol.

## Scientific boundary

P001 does not:

- use stock returns;
- calculate expected return;
- convert historical base rates into target prices;
- assign probability to operating scenarios;
- force a probability when support is insufficient;
- create buy/sell/hold;
- create portfolio eligibility;
- authorize live capital.

Passing P001 permits a later probability-weighted payoff layer only for cases with both:

1. a valid payoff framework; and
2. a publishable P001 transaction probability surface or an explicit current terminal
   state.
