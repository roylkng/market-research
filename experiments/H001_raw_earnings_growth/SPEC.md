# EXP-2026-09-06-H001 — Frozen specification

## Hypothesis

Raw quarterly accounting acceleration predicts post-result outperformance.

## Universe

Preselected 25-company cohort of liquid non-financial Indian equities reporting in late July 2025. Selection was frozen before inspecting the post-event holding-period returns.

## Signal

```text
raw_growth_score = sales_yoy_pct + op_profit_yoy_pct + 5 * opm_change_pp
```

## Execution convention

- Ignore result day and first subsequent trading session.
- Enter at open of second trading session after result.
- Hold 20 trading sessions inclusive of entry day.
- Exit at close.
- Observation is excluded when exact entry or exit cannot be independently verified.

## Benchmarks

- Nifty 50 exposure over the same entry/exit window.
- Nifty 200 Momentum 30 exposure over the same entry/exit window.

## Primary test

Continuous relationship between frozen score and subsequent benchmark-relative return using Pearson and Spearman correlation.

## Promotion criterion

A positive relationship must be economically meaningful, statistically credible, robust to winner removal, and superior to simple benchmarks. A feasibility pilot can only justify deeper testing, never live capital.
