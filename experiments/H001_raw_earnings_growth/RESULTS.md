# EXP-2026-09-06-H001 — Results

## Verdict

`REJECTED`

24 observations had exact delayed-entry and exit price pairs.

| Metric | Result |
|---|---:|
| Pearson(score, excess vs Nifty) | 0.066 |
| Pearson p-value | 0.758 |
| Spearman(score, excess vs Nifty) | 0.035 |
| Spearman p-value | 0.872 |

The frozen score had essentially no relationship with subsequent excess return.

## Interpretation

The economic flaw is structural: raw sales/profit growth does not measure what investors expected before the result. Strong growth can still be a negative surprise and weak growth can still beat a depressed expectation.

## Follow-up

Do not add discretionary weights or filters to rescue H001. Surprise-based formulations belong to a separate hypothesis, H002 or later variants.
