# RTA001 Global Research Trial Accounting v1

Status: GOVERNANCE FOUNDATION
Created: 2026-10-03
Live capital: DISABLED

## Objective

Maintain one global, explicit accounting surface for MarketLab research so the
repository cannot accumulate many frozen trials while remembering only the
successful ones.

RTA001 does not modify any prior scientific result.

It answers:

1. how many research trials/results have been run;
2. which trials used return outcomes;
3. which trials belong to the same multiple-testing family;
4. which reported primary successes survive family-level multiplicity controls;
5. which prospective trials remain unresolved.

## Global categories

Every registered study belongs to exactly one category.

### ALPHA_FEATURE_DISCOVERY

A historical or prospective test whose primary scientific question is whether a
new stock-level information family adds return-predictive information.

This is the primary false-discovery family in RTA001-v1.

### ALPHA_COMBINATION_DIAGNOSTIC

Tests combining or comparing already-discovered alpha families after their
underlying outcomes were known.

These are counted globally but are not pooled with independent feature-discovery
p-values.

### PORTFOLIO_CONTEXT

Outcome-bearing portfolio overlays such as regime/risk scaling.

Counted separately because the estimand is portfolio utility/risk rather than
new stock-level alpha.

### PORTFOLIO_INTEGRATION

Outcome-blind portfolio construction, capacity or risk-treatment studies.

### RISK_MODEL

Risk-model estimation, attribution or forecast-calibration studies.

### SOURCE_FEASIBILITY

Source/timestamp/schema/coverage studies that do not open alpha/return outcomes.

### SOLVER_STABILITY

Numerical reproducibility and optimization implementation studies.

## Primary endpoint rule

RTA001 records only the preregistered/frozen PRIMARY endpoint for multiplicity.

Secondary or diagnostic endpoints may never convert a failed primary into an
RTA001 primary success.

For primary hypotheses requiring multiple component tests simultaneously, RTA001
uses the intersection-union p-value:

    p_composite = max(required_component_p_values)

This exactly represents the frozen rule "all required components must pass".

If a primary endpoint uses a bootstrap/gate design with no valid scalar p-value,
RTA001 records:

    p_value_status = NO_SINGLE_P_VALUE_GATE_BASED

For conservative family accounting, such a completed failed trial receives
fdr_accounting_p_value = 1.0.

RTA001-v1 does not manufacture a p-value for a gate-based success.

## FDR family v1

Family ID:

    ALPHA_FEATURE_DISCOVERY_V1

Completed members currently include the AE001 stock-level feature-family
discovery lineage.

Retrospective seed/scaffolding trials are counted and conservatively assigned
p=1 when no valid frozen primary p-value exists.

Pending prospective trials are counted in registered/pending totals but do not
enter completed-test p-value adjustment until their primary result is sealed.

## Multiplicity methods

For every family with scalar accounting p-values, RTA001 reports:

1. Benjamini-Hochberg adjusted q-value;
2. Benjamini-Yekutieli adjusted q-value;
3. Holm adjusted p-value;
4. Bonferroni adjusted p-value.

Threshold:

    alpha = 0.05

Interpretation:

- BH controls FDR under independence / suitable positive dependence;
- BY controls FDR under arbitrary dependence and is more conservative;
- Holm controls family-wise error under arbitrary dependence;
- Bonferroni is reported as a simple upper-bound reference.

Because MarketLab feature trials often share dates, stocks and baselines, RTA001
must NOT describe BH alone as definitive.

## Result semantics

Each entry preserves:

- reported_primary_supported;
- nominal_primary_p_value when one exists;
- fdr_accounting_p_value;
- BH/BY/Holm/Bonferroni adjusted values;
- family-level significance flags.

A prior result is never rewritten from supported to rejected.

Instead RTA001 may state:

    NOMINALLY_SUPPORTED_NOT_MULTIPLICITY_ROBUST

or:

    NOMINALLY_AND_MULTIPLICITY_SUPPORTED

## Manifest discipline

The trial manifest is explicit and reviewed.

Automatic filesystem discovery is prohibited for statistical classification,
because source feasibility, risk-model, alpha, portfolio and solver studies have
different scientific semantics.

New outcome-bearing trials must be added to the global manifest before their
result is opened whenever operationally possible.

Any trial omitted initially must be backfilled with:

    registration_mode = RETROSPECTIVE_ACCOUNTING_BACKFILL

Omission does not erase the trial from the research budget.

## Promotion

No historical alpha family may be described as robust research evidence solely
because nominal p < 0.05 when its RTA001 family-adjusted diagnostics are
materially weaker.

Prospective evidence remains the preferred promotion path.

RTA001 does not authorize live capital.
