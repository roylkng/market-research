# AE001 T008-D004 Combined Four-Period Fundamental Panel v1

Status: FROZEN BEFORE COMBINATION MATERIALIZATION
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Construct one outcome-blind four-period T008 event panel from the exact sealed
D002 and D003 source-feasibility artifacts.

D004 does not fetch new filings, open stock returns, or fit a model.

## Frozen input artifacts

### T008-D002

Workflow run: 36742740631
Artifact ID: 11111600748
Artifact name: ae001-t008-d002-36742740631
Panel SHA-256:

6426dbe7fc47faa8ce440e599d3566ce98fe8d675efc5abb61145c940d6bfd64

D004 may use D002 records only for:

- target 2026-03-31 / baseline 2025-03-31;
- target 2026-06-30 / baseline 2025-06-30.

### T008-D003

Workflow run: 36746275777
Artifact ID: 11113075870
Artifact name: ae001-t008-d003-36746275777
Panel SHA-256:

69fdda1d51b7a070849556a53794f224d054270974958ae45eab6555fbaa1e35

D004 may use D003 records only for:

- target 2025-09-30 / baseline 2024-09-30;
- target 2025-12-31 / baseline 2024-12-31.

No alternative source panel may be substituted after D004 materialization begins.

## Frozen universe

All source panels must bind the same frozen U001 universe SHA:

cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb

## Frozen feature set

Exactly six T008-D001 features:

- revenue_yoy
- pbt_change_to_prior_revenue
- total_profit_change_to_prior_revenue
- pbt_margin
- pbt_margin_delta_yoy
- total_profit_margin_delta_yoy

D004 admits only source records with all_six_features_complete=true.

No imputation, winsorization, feature repair, source replacement, or new feature
is permitted.

## Frozen period ownership

Each target period is owned by exactly one source diagnostic:

- 2025-09-30 -> D003;
- 2025-12-31 -> D003;
- 2026-03-31 -> D002;
- 2026-06-30 -> D002.

A duplicate (target_period_end, symbol) key fails closed.

## Frozen feasibility thresholds

Reuse D002 exactly:

1. every target period must have at least 60 complete rows;
2. total complete rows across all four periods must be at least 280.

Thresholds may not be lowered after materialization.

## Combined record provenance

Every D004 row retains the complete source record and additionally binds:

- source diagnostic ID;
- source panel SHA-256;
- source workflow run ID;
- source workflow artifact ID.

D004 assigns a new combined record hash without changing source feature values.

## Outcome boundary

D004 may not:

- fetch stock returns;
- fetch benchmark returns;
- create entry/exit labels;
- fit a predictive model;
- rank features by future performance;
- alter a source record.

## Promotion

If D004 passes, the next allowed step is to freeze the T008 alpha protocol before
opening any return outcomes.

That protocol must predefine:

- exact decision timestamp from target filing publication;
- execution rule;
- primary and secondary horizons;
- feature cross-sectional/event transforms;
- chronological train/validation/test mechanics;
- multiple-testing accounting;
- success criteria.

D004 itself establishes source/event-panel feasibility only.

Live capital remains disabled.
