# HG006-D004 P1 Executable Stage-Conditioned Base-Rate Bridge v1

Status: **FROZEN BEFORE D004 BASE-RATE OUTPUT IS OPENED**  
Frozen: 2026-10-07  
Current-company probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Make the already-frozen HG006-D004 competing-risk estimator executable on the exact
333 terminal-labeled historical episodes produced by HG006-D002-P1.

This bridge resolves track/stage mechanics only. It does not choose favorable stages,
fit a model, or use current-company outcomes.

## Frozen source

Use exactly:

- labeler: `HG006-D002-P1-v1`;
- run: `37654933457`;
- artifact ID: `11497928291`;
- label panel SHA-256:
  `545532620b409135bd867f633de708cfd441e2c532a5b790afeacef9c7de9874`;
- observation cutoff: `2026-09-30`;
- episode count: 333.

No substitute label panel is permitted under D004-P1.

## Statistical authority

All estimates use the already-frozen rules in:

`research/HG006_D004_STAGE_CONDITIONED_BASE_RATE_ESTIMATOR_V1.md`

including:

- Aalen-Johansen competing-risk cumulative incidence;
- 2,000 episode-level bootstrap resamples;
- RNG seed 606001;
- 95% percentile intervals;
- Wilson 95% interval for descriptive resolved fractions;
- family support threshold >=30;
- stage-conditioned support >=30 and post-stage terminal outcomes >=10.

## Conflict exclusion

Episodes with:

`UNRESOLVED_SOURCE_CONFLICT`

are excluded from every statistical denominator and reported separately.

They are never converted to failure or censoring.

## Outcome tracks

### SCHEME_REORGANISATION

Primary track:

`transaction_completion`

uses:

- primary_terminal_state;
- primary_terminal_date.

### PREFERENTIAL_WARRANT

Primary track:

`issuance_completion`

uses:

- primary_terminal_state;
- primary_terminal_date.

Secondary track:

`full_economic_exercise`

uses:

- full_economic_exercise.terminal_state;
- full_economic_exercise.terminal_date.

The two tracks are estimated independently and may not substitute for one another.

## Family-level time origin

For every family-level track:

`time_zero = entry_date`

Right-censored episodes end at the frozen observation cutoff.

## Frozen eligible stages

The D004 stage vocabulary remains exactly:

- BOARD_APPROVED;
- SHAREHOLDER_APPROVED;
- REGULATORY_OR_COURT_APPROVED;
- PUBLIC_ANNOUNCEMENT;
- RECORD_DATE_FIXED;
- OFFER_OPEN;
- OFFER_CLOSED;
- ALLOTMENT_COMPLETED.

Stage date is the exact first_observed_stage_dates value sealed by D002-P1.

## Track-specific stage eligibility

### SCHEME_REORGANISATION / transaction_completion

All frozen eligible stages may be evaluated.

### PREFERENTIAL_WARRANT / issuance_completion

All frozen eligible stages **except**:

`ALLOTMENT_COMPLETED`

may be evaluated.

Reason: under the frozen D002 ontology, ALLOTMENT_COMPLETED is itself the terminal
completion evidence for issuance_completion. Conditioning the issuance-completion
probability on already observing its terminal event would be outcome leakage.

### PREFERENTIAL_WARRANT / full_economic_exercise

All frozen eligible stages may be evaluated, including ALLOTMENT_COMPLETED.

For full economic exercise, allotment is an intermediate stage, not the terminal state.

## Stage-conditioned risk-set inclusion

An episode enters a stage-conditioned risk set only when:

1. it is not UNRESOLVED_SOURCE_CONFLICT;
2. the exact stage exists in first_observed_stage_dates;
3. the stage date is on or after entry_date;
4. the stage date is on or before the observation cutoff;
5. for COMPLETED/FAILED_OR_WITHDRAWN episodes, stage_date <= terminal_date.

For an included episode:

- new time zero = stage date;
- terminal/censoring state is unchanged for the selected track;
- duration = terminal_date - stage_date for terminal episodes;
- duration = observation_cutoff - stage_date for right-censored episodes.

No episode is backdated to an unobserved stage.

## Supported horizons

The frozen candidate horizons remain:

- 90 days;
- 180 days;
- 365 days;
- 730 days.

A horizon is reported only when:

`max(observed_or_censoring_duration_days in the exact risk set) >= horizon`

Otherwise output state:

`INSUFFICIENT_FOLLOW_UP`

and do not emit a point estimate or interval for that horizon.

This rule applies to family-level and stage-conditioned estimates.

## Publication states

### Family level

A family/track is publishable when:

`valid_nonconflict_support >= 30`

Otherwise:

`INSUFFICIENT_HISTORICAL_SUPPORT`

### Stage conditioned

A family/track/stage is publishable only when both:

- stage risk-set support >=30;
- completed + failed outcomes observed after stage >=10.

Otherwise:

`INSUFFICIENT_HISTORICAL_SUPPORT`

No pooling across families or tracks.

## Output

Retain for every family/track:

- total source episode count;
- conflict-excluded count;
- valid support count;
- completed / failed / right-censored counts;
- descriptive resolved completion fraction + Wilson 95% interval;
- supported-horizon Aalen-Johansen completion/failure CIF + 95% bootstrap interval;
- all frozen stage-conditioned publication states and estimates;
- bootstrap resample count and RNG seed.

## Scientific boundary

D004-P1 does not:

- assign a probability to any current company;
- use stock returns;
- choose a stage after seeing a favorable rate;
- blend scheme and warrant families;
- substitute warrant issuance probability for full exercise;
- calculate expected return;
- create buy/sell/hold;
- create portfolio eligibility;
- authorize live capital.

Passing D004-P1 permits only a separately frozen current-case probability mapping layer.
