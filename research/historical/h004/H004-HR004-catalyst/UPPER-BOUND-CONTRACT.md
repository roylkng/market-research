# H004-HR004 catalyst upper-bound falsification

Status: **FROZEN BEFORE RETURN JOIN**

Purpose: determine whether detailed semantic Grade-3/4 catalyst review is worth doing.

This test is deliberately maximally favourable to the catalyst hypothesis: **every candidate retained by the already-frozen return-blind source filter is temporarily treated as if it were a valid H004 Grade-3/4 catalyst**. This is an upper bound, not a real signal.

Rules:

- candidate source timestamp comes from NSE exchange disclosure time,
- H004 decision timestamp is 20:00 Asia/Kolkata; disclosures after 20:00 are first eligible at the next trading-day decision snapshot,
- pre-momentum and primary-liquidity rules are the already-frozen H004 rules,
- each qualifying candidate remains eligible for Stage-2 recognition for 10 symbol trading sessions, matching the earnings-replay operational convention,
- Stage-2 uses the same daily-data subset available in HR002: at least two of +2% to +8% one-day recognition, volume >=2x prior-20 median, and close within 5% of prior-60-session high; prior-5-session return must stay <15%; flat positive circuit proxy is non-executable,
- entry proxy is next-session open after Stage-2,
- precision label is max high over next 20 symbol sessions >=25% from entry,
- full-market episode recall uses the already-frozen HR003 primary episode ledger; an episode is recalled if a candidate-derived Stage-2 signal for the same symbol produces an entry after the candidate and before the episode's +25% hit date,
- duplicate candidate-derived Stage-2 entries for the same symbol/date collapse to one signal.

Report:
- filtered candidate count,
- candidates satisfying primary liquidity and pre-momentum,
- candidate-derived Stage-2 signal count,
- Stage-2 precision and lead time,
- HR003 episode recall,
- quarter stability,
- comparison to the frozen momentum baseline at the closest predeclared signal budget.

Interpretation:

Because every retained candidate is assumed material, actual semantically graded catalyst performance can only be equal or worse. If this upper bound is clearly insufficient to make H004 viable, do not spend effort grading all candidates and do not weaken the filter after observing returns.
