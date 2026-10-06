# HG006-S001 Historical Calibration Cohort v1

Status: **FROZEN BEFORE HISTORICAL TERMINAL LABELS OR L001 OUTPUT**  
Frozen: 2026-10-05  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Select a finite, deterministic historical calibration cohort for the first HG006
stage-conditioned base-rate run.

The cohort is chosen before any historical terminal labels or L001 model outputs are
opened.

## Frozen upstream source

Use exactly:

- HG006-D001-v1;
- workflow run: `37347148756`;
- artifact ID: `11361421023`;
- census SHA-256:
  `a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5`.

## Families

Select only:

- SCHEME_REORGANISATION;
- PREFERENTIAL_WARRANT.

Rationale is current-case relevance frozen before historical outcomes:

- ANANTRAJ depends on scheme/de-merger effectiveness;
- SAMBHV depends on preferential-warrant/allotment progression.

No historical outcome was used to select these families.

## Sample size

Select exactly 150 D001 symbol-family chronologies per family.

Total selected chronologies: 300.

If a family contains fewer than 150 chronologies, S001 fails rather than changing the
target sample size.

## Deterministic selection order

For every eligible chronology compute:

`selection_key = SHA256("HG006-S001-v1|" + chronology_id)`

Sort ascending by selection_key and take the first 150 within each family.

chronology_id is already source-defined before terminal labeling.

No symbol, date, event count, attachment state, liquidity, valuation or later outcome
enters selection order.

## Retained fields

For each selected chronology retain:

- chronology_id;
- symbol;
- family;
- first_observed_at_utc;
- last_observed_at_utc;
- first_initiation_window_at_utc;
- event_count;
- initiation_window_event_count;
- followup_event_count;
- has_approved_attachment;
- announcement_ids;
- deterministic selection_key.

## Scientific boundary

S001 does not:

- prefer chronologies with terminal language;
- require successful document extraction;
- drop censored cases;
- use stock returns;
- group transaction episodes;
- label success/failure;
- assign completion probability;
- create expected return or portfolio eligibility.

Source-unavailable chronologies remain selected and may later become explicit
DOCUMENT_UNAVAILABLE states.

## Promotion

S001 permits HG006-L001 historical stage/anchor extraction and D003 episode threading
only for the fixed 300-chronology calibration cohort.

A later full-population expansion requires a separately frozen version.
