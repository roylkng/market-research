# HG008-P001: Preregistered, Falsifiable NSE Transaction Forecast Baselines

Frozen **13 October 2026**, *before* the first eligible future stage
publication after 00:00 UTC on **14 October 2026**.

Status: **historical stage base rate + prospective forecasting protocol,
NOT stock return alpha, NOT a current-case completion probability**.

## What can actually be predicted

The historical HG006 source has **333 source-threaded transaction episodes**,
with explicit conflicting episodes excluded and right-censored cases retained.
It contains **four published stage/track combinations**, plus an additional
180-day horizon for court-approved reorganizations.

The following are frozen historical competing-risk cumulative incidence
forecasts *for a new incident at the specified stage*, NOT for a transaction
which already survived part of the horizon:

| Family / stage | Clearly defined resolution target | Original historical 90/180-day frequency | Historical interval |
| --- | --- | ---: | --- |
| Warrant / board approved | Allotment completed within 90d | 70.66% | 59.15% to 81.13% |
| Warrant / board approved | FULL economic exercise within 90d | 30.88% | 20.59% to 42.65% |
| Warrant / allotment completed | FULL economic exercise within 90d | 59.14% | 48.39% to 68.82% |
| Scheme / court or regulator approved | Transaction legally completed within 90d | 24.30% | 16.09% to 33.44% |
| Scheme / court or regulator approved | Transaction legally completed within 180d | 25.63% | 17.24% to 34.90% |

Probability entries and intervals are copied exactly from original
research/hg006-d004-result-v1.json under pinned Git blob; they are
**not invented accuracy scores**. These are population frequency
estimates from the training/estimation data. **Out-of-sample calibration,
historical regime stability and investable stock returns are unverified**.

### Why resolved-only percentages are misleading

For court-approved reorganizations, the historical completed/resolved
fraction may look about 92%, while only around 24% completed by 90 days.
Right-censored cases and waiting time are material. Ignoring them makes
"90% chance of completion soon" a false inference.

### Existing October cases: abstain

The older HG006-P001 episodes have already survived for months. Their
sample after conditioning on survival at the as-of stage is insufficient.
The new-entrant frequency above **cannot** be applied unchanged to:

- ANANTRAJ court/reorganization timing;
- DEVX exercise (issuance completion does not prove full exercise);
- INOXGREEN court-approved transaction, or **its separately verified
  October 9 Vibhav equity conversion**;
- SAMBHV warrant issuance/exercise.

The source also has changes after HG006's 4 October cutoff, so these
current cases need a separately staged and calibrated successor. This
protocol preserves **NULL company-specific probabilities** until supported.

## Prospective first-seen event contract

Only a *new* independently source-reviewed exchange disclosure with a
stage first published **14 October 2026 UTC or later** qualifies.

Required at freeze time:

- Exact issuer symbol and ISIN, unique episode identity;
- exact original official NSE/BSE PDF URL plus the original PDF bytes
  and matching SHA-256;
- independent stage source-page semantic-review receipt;
- public publication timestamp, original family/track/stage;
- frozen 90d horizon, or source-supported court 180d;
- forecast creation **within eight hours of the original publication**,
  and before a documented terminal outcome;
- a real Git commit/publication strictly before outcome resolution,
  recorded separately. Local JSON creation alone is insufficient.

Previous-event survivor episodes may not be relabelled "new" to import
first-seen probabilities. Unresolved source stage, unknown original PDF,
blocked official data, late first observation or unsupported family
means **ABSTAIN**, not probability 0 or 50%.

## Frozen outcomes and calibration

Forecasts predict one discrete milestone within 90/180 calendar days
from original stage publication. The target is NOT share-price return,
EPS improvement, new revenues or equity value. Different tracks of one
episode are statistically dependent.

The separate scoring runner:

- refuses evaluation before the actual deadline;
- requires evidence of the original Git precommit before a terminal event;
- requires original exchange source SHA, URL and independent terminal review;
- marks absence of announcement as **RIGHT CENSORED** unless independently
  verified full official-window coverage supports a negative label;
- computes precommitted Brier and 0.50-probability control for matured,
  labelled original-source cases;
- groups by family/track/stage/horizon and requires **at least 30
  independent matured episodes** before even an independent descriptive
  calibration review;
- forbids retroactive revision/refit of predicted probabilities.

Even 30 episodes alone does not establish predictive superiority over
simpler reference models, profitable stock selection or 50% CAGR.
First unseen cohorts and coverage failures must be reported.

## Reproducibility

- Source and prospective forecast contract:
  src/marketlab/hg008_event_forecast.py
- Outcome resolver with maturity and censor gates:
  src/marketlab/hg008_event_score.py
- Baseline maker:
  scripts/build_hg008_event_baselines.py
- New *future* event forecast freezer:
  scripts/freeze_hg008_new_event_forecast.py
- Independently reviewed outcome scorer:
  scripts/score_hg008_mature_event.py
- Regression:
  tests/test_hg008_event_forecast.py
- Workflow:
  .github/workflows/hg008-event-baselines.yml

Source-pinned five stage cards are permanently retained after merging at
research/hg008/hg008-p001-first-seen-stage-baselines-v1.json.

These stage probabilities can drive intelligent research resource routing:
for new warrant announcements, distinguish securities issuance from
FULL economic exercise; for new court-approved transactions, focus on
effective-date evidence rather than the approval headline alone.

They **must not** be multiplied by arbitrary EBITDA or market caps to
publish company-specific expected returns without separate
survivor-conditioned model, financial accounting, diluted-share and
execution calibration.

Portfolio eligibility and live capital remain DISABLED.
