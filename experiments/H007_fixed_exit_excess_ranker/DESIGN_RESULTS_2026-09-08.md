# H007 design result

Recorded: 2026-09-08

Status: **REJECTED AT DESIGN GATE. HOLDOUT UNOPENED. LIVE CAPITAL DISABLED.**

H007 changed the target from future maximum excursion to the directly investable proxy of stock session-20 close return minus Nifty 500 return over the identical entry/exit dates. It used the preregistered fixed histogram gradient-boosting regressor and no feature or hyperparameter search.

On 2,298 purged chronological out-of-fold design events:

- Spearman predicted-versus-realized excess: 0.0794
- mean absolute error: 8.12 percentage points

Primary top-10% selection:

- selected: 230
- median Nifty 500 excess: **-0.05 percentage points**
- mean Nifty 500 excess: **+0.70 percentage points**
- Nifty 500 beat rate: **49.57%**
- median raw stock return: **-0.61%**
- excess >= +5 percentage points: 20.87%

Matched top-10% baselines also fail to produce a positive median excess. Momentum median excess is -1.25 pp, first-session tape -0.66 pp, and accounting-growth ranking -1.85 pp.

H007 therefore fails its preregistered continuation gate and the untouched 2024-10-01 through 2025-06-30 holdout remains unopened.

## Research implication

Three independent formulations now point in the same direction: 20-session post-result stock selection using only result accounting, pre-event state and one reaction session is too noisy for the intended edge. H005's linear maximum-excursion classifier, H006's nonlinear maximum-excursion classifier, and H007's fixed-exit excess-return regressor all fail before holdout.

The next research step should move to a longer horizon and a broader company-selection question rather than continue tuning a short-horizon earnings-event engine. That is a change in mechanism and objective, so it requires a new hypothesis.
