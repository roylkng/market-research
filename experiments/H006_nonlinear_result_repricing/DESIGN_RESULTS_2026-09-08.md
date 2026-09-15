# H006 design result

Recorded: 2026-09-08

Status: **REJECTED AT DESIGN GATE. HOLDOUT UNOPENED. LIVE CAPITAL DISABLED.**

H006 used exactly the frozen H005-B information set with the preregistered fixed low-capacity histogram gradient-boosting classifier. No hyperparameter search or feature additions were performed after outcomes were observed.

On 2,298 purged chronological out-of-fold design observations, H006 produced average precision 0.0874 and ROC AUC 0.6339.

Primary top-10% result:

- selected: 230
- true +25%/20-session maximum-excursion movers: 135
- hits: 22
- recall: **16.30%**
- precision: **9.57%**
- prevalence lift: **1.63x**
- median Nifty 500 20-session excess: **-0.41 percentage points**

The preregistered continuation gate required at least 25% recall, 12% precision, 2.0x lift, positive median market-relative return, and improvement over H005-B in both recall and precision. H006 fails every condition.

The untouched 2024-10-01 through 2025-06-30 holdout remains unopened.

## Interpretation

The nonlinear interaction hypothesis did not rescue the +25% maximum-excursion target. More importantly, both H005 and H006 can identify some stocks that touch large future highs while their selected groups still have negative median 20-session market-relative returns. The target itself is therefore poorly aligned with a fixed, reproducible investment outcome.

Any next hypothesis should change the scientific objective to an executable fixed-exit return or market-relative return rather than continue optimizing a path-dependent intraday maximum. That change is a new hypothesis, not an H006 tuning variant.
