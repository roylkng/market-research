# AE001 T008-D002 Multi-Quarter Fundamental Panel Feasibility v1

Status: FROZEN BEFORE MULTI-QUARTER SOURCE DIAGNOSTIC
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Extend the successful T008-D001 source diagnostic into a multi-quarter,
outcome-blind event panel large enough to support a later medium-horizon alpha
trial.

D002 opens no stock-return labels and fits no predictive model.

## Frozen universe

Use the same 100-member U001 snapshot:

research/prospective/universes/FY27-Q2-2026-09-06.json

Expected universe SHA-256:

cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb

## Frozen target/baseline period pairs

1. target 2025-09-30, baseline 2024-09-30
2. target 2025-12-31, baseline 2024-12-31
3. target 2026-03-31, baseline 2025-03-31
4. target 2026-06-30, baseline 2025-06-30

No period may be added or removed after D002 source evidence is opened.

## Filing selection

For each symbol and period pair, reuse the frozen T008-D001 rules:

- same accounting basis required;
- Consolidated preferred only when both periods have a usable Consolidated pair;
- otherwise Standalone;
- target = earliest official target-period publication for that basis;
- baseline = latest official baseline-period publication already public strictly
  before the target;
- same-timestamp multi-URL ambiguity fails closed;
- later target revisions never replace the first target event.

## Frozen feature set

Exactly six D001 features:

- revenue_yoy
- pbt_change_to_prior_revenue
- total_profit_change_to_prior_revenue
- pbt_margin
- pbt_margin_delta_yoy
- total_profit_margin_delta_yoy

No new fundamental feature may be added in D002.

## Monetary normalization

Reuse D001 exactly:

- XBRL facts are treated as actual INR values and are not rescaled by
  presentation-rounding metadata;
- legacy HTML/table values require explicit recognized rounding metadata;
- non-INR or unknown required rounding fails closed.

## Evidence retention

Retain exact discovery bytes and exact selected filing bytes content-addressed.

Each panel row binds:

- symbol;
- frozen-universe identity;
- target and baseline period;
- accounting basis;
- target/baseline publication timestamps;
- discovery-row hashes;
- filing hashes;
- parser versions;
- six feature values.

## Feasibility thresholds

D002 passes only when BOTH conditions hold:

1. every one of the four target periods has at least 60 complete six-feature rows;
2. total complete six-feature event rows across all four periods is at least 280.

These thresholds are frozen before the older-period source diagnostic.

## Duplicate/event rules

A symbol may contribute at most one record per target period.

The exact key is:

    (target_period_end, symbol)

Duplicate keys fail closed.

## Outcome boundary

D002 may not:

- fetch stock returns;
- fetch benchmark returns;
- build return labels;
- fit a model;
- rank features by future performance;
- alter the feature set based on coverage.

## Promotion

If D002 passes, a separate T008 alpha protocol may be frozen.

The later alpha trial must define, before opening returns:

- decision-timestamp mapping from filing publication time;
- entry rule;
- primary horizon;
- secondary horizon if any;
- cross-sectional/event normalization;
- train/validation/test mechanics;
- success criteria.

D002 itself creates no alpha claim.

Live capital remains disabled.
