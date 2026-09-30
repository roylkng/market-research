# AE001 T008-D003 Legacy Financial Results Baseline Feasibility v1

Status: FROZEN BEFORE LEGACY SOURCE ACCESS
Frozen: 2026-09-30
Live capital: DISABLED

## Objective

Test whether the official NSE legacy Financial Results catalog can supply the
missing 2024 same-quarter baselines for the two T008-D002 periods that failed
under Integrated Filing alone.

D003 is source/parser feasibility only.

It opens no stock-return labels and fits no predictive model.

## Motivation

T008-D002 was frozen across four period pairs and failed only because the
Integrated Filing discovery source did not provide usable 2024 baselines for:

1. target 2025-09-30 / baseline 2024-09-30;
2. target 2025-12-31 / baseline 2024-12-31.

The later pairs already passed:

- 2026-03-31 / 2025-03-31: 86 complete rows;
- 2026-06-30 / 2025-06-30: 94 complete rows.

D003 does not alter D002 and does not lower any D002 threshold.

## Frozen universe

Use the same 100-member U001 snapshot:

research/prospective/universes/FY27-Q2-2026-09-06.json

Expected SHA-256:

cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb

## Frozen source roles

### Target filing source

Official NSE Integrated Filing - Financials discovery:

/api/integrated-filing-results

Target selection reuses T008-D001/D002 exactly:

- target period must match;
- exact symbol must match;
- same accounting basis required;
- earliest official target-period publication for that basis;
- same-timestamp multi-URL ambiguity fails closed;
- later revisions never replace the first target event.

### Baseline filing source

Official NSE legacy Financial Results discovery:

/api/corporates-financial-results?index=equities&symbol=<SYMBOL>&period=Quarterly

The baseline candidate must:

- match the frozen symbol;
- have toDate equal to the frozen 2024 baseline period;
- expose an official XBRL URL;
- have accounting basis normalized to Consolidated or Standalone;
- have official broadcast/filing time strictly earlier than the selected target
  publication time.

Among valid same-basis baseline candidates, select the latest already-public
baseline. Same-timestamp multi-URL ambiguity fails closed.

D003 does not use a legacy-source 2025 target even when one exists. This isolates
the diagnostic to the missing baseline source.

## Frozen accounting-basis normalization for legacy rows

Case-insensitive values are normalized as:

- Consolidated -> Consolidated;
- Standalone -> Standalone;
- Non-Consolidated / Non Consolidated / NonConsolidated -> Standalone.

Unknown basis fails closed for that row.

## Frozen period pairs

1. target 2025-09-30, baseline 2024-09-30;
2. target 2025-12-31, baseline 2024-12-31.

No period may be added or removed after source evidence is opened.

## Frozen parser policy

Use the currently merged MarketLab filing parser unchanged.

- Integrated targets use the existing T008 parser path.
- Legacy baseline XBRL/HTML bytes are passed through the same
  parse_historical_filing -> parse_indas_document path.
- No concept alias, context-selection rule, monetary normalization rule, or
  parser fallback may be changed after D003 source evidence is opened.

If legacy filing bytes are discoverable but the current parser cannot parse them
at sufficient coverage, D003 fails and a separately frozen parser diagnostic is
required.

## Frozen feature set

Exactly the six T008-D001 features:

- revenue_yoy
- pbt_change_to_prior_revenue
- total_profit_change_to_prior_revenue
- pbt_margin
- pbt_margin_delta_yoy
- total_profit_margin_delta_yoy

No new fundamental feature is allowed in D003.

## Monetary normalization

Reuse T008-D001 exactly:

- XBRL numeric facts are actual INR amounts and are not multiplied by
  presentation-rounding metadata;
- legacy HTML/table values require explicit recognized rounding metadata;
- non-INR or unknown required rounding fails closed.

## Exact evidence

Retain content-addressed:

- Integrated target discovery bytes;
- legacy baseline discovery bytes;
- selected target filing bytes;
- selected baseline filing bytes.

Each successful row binds both discovery hashes, both discovery-row hashes, both
filing hashes, both publication timestamps, parser versions, accounting basis
and all six features.

## Frozen feasibility thresholds

D003 passes only when BOTH conditions hold:

1. each target period has at least 60 complete six-feature rows;
2. total complete rows across the two periods is at least 120.

These are the unchanged per-period D002 threshold applied to the two missing
periods.

## Promotion

If D003 passes, the next allowed step is a separately frozen D004 combined-source
four-period panel that:

- retains D002's 2026-03 and 2026-06 rows unchanged;
- uses D003 rows for 2025-09 and 2025-12;
- requires all four periods >=60 complete rows;
- requires total complete rows >=280;
- opens no returns.

Only after D004 passes may a T008 alpha protocol be frozen.

## Failure path

If D003 fails because:

- legacy discovery coverage is insufficient -> abandon or freeze another official
  source diagnostic;
- legacy XBRL is discoverable but parser coverage is insufficient -> freeze a
  parser-specific diagnostic before changing parsing logic.

Do not lower thresholds post hoc.

## Outcome boundary

D003 may not:

- fetch stock returns;
- fetch benchmark returns;
- build return labels;
- fit a predictive model;
- rank features by future performance;
- tune the parser after evidence is opened.

Live capital remains disabled.
