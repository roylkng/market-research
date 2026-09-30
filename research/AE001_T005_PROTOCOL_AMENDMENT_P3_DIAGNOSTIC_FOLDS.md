# AE001 T005 Protocol Amendment P3: Restore Omitted Diagnostic Fold Dates

Frozen: 2026-09-30
Status: FROZEN AFTER FAIL-CLOSED PRE-MODEL RUN; BEFORE ANY T005 MODEL FIT OR OUTCOME METRIC
Live capital: DISABLED

## Trigger

The first T005 materialization attempt, workflow run 36692550419, reproduced all
frozen upstream AE001 sources and successfully built the stock-futures feature
panel.

It then failed before either base or augmented model fitting because the
TRIAL_REGISTERED event accidentally omitted the 20-session diagnostic fold dates
from its nested diagnostic payload.

The diagnostic folds were already frozen before the run in BOTH:

- research/AE001_T005_STOCK_FUTURES_POSITIONING_V1.md
- registry/ae001_t005_stock_futures.yaml

No T005 prediction, rank IC, spread, return metric, or model comparison was
computed before this amendment.

## Frozen restoration

The diagnostic 20-session folds are copied verbatim from the already-frozen
protocol and registry:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-08-27

Horizon:

20 completed NSE sessions.

Paired Newey-West lag:

19.

The diagnostic cannot rescue a failed 5-session primary endpoint.

## Runtime rule

The T005 runner must obtain diagnostic folds from this P3 amendment rather than
assuming the omitted field exists in the registration event.

Primary and secondary folds continue to come from the original registration
event and remain unchanged.

## Non-changes

P3 changes no:

- source;
- feature;
- base/augmented feature count;
- model family;
- ridge l2;
- primary folds;
- secondary folds;
- primary success criterion;
- source-quality rule;
- outcome.

No prospective or live-capital claim.
