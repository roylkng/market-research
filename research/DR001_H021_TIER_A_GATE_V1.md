# DR001 Tier A H021 revision gate v1

Status: **FROZEN BEFORE THE FIRST VALID H021 28-DAY REVISION COHORT**  
Frozen: 2026-10-04  
Portfolio eligibility: disabled  
Live capital: disabled  
Return outcomes opened: no

## Purpose

This gate connects the sealed DR001 Tier A company dossiers to the already-frozen H021
prospective EPS-revision experiment. It is a research-routing rule only. It does not
change H021, create a return forecast, authorize a position, or modify PF001.

The five frozen Tier A names come from
`research/company-dossiers/2026-10-03/dr001-tier-a-v1.json`.

The H021 comparison remains governed by
`research/H021_COMPARISON_CONTRACT_V1.md`.

## Frozen input requirements

The gate may run only when:

1. the dossier pack remains explicitly non-portfolio and non-live-capital;
2. the dossier pack still names `H021_28D_REVISION` as its common next gate;
3. the H021 comparison is schema v1 and retains `outcomes_opened=false`;
4. the comparison uses the frozen H021 primary signal:
   `28-35 day same-period consensus EPS revision`;
5. every Tier A symbol appears exactly once in the H021 comparison.

Missing or incompatible evidence fails closed.

## Frozen routing states

For each Tier A company:

### STRONG_POSITIVE_PRIMARY

All three conditions must hold:

- the H021 primary signal is eligible;
- `eps_revision_pct > 0`;
- the symbol is inside H021's already-frozen primary top-decile cohort.

Research routing: **advance to valuation and red-team review**.

This is not portfolio eligibility.

### POSITIVE_NOT_PRIMARY

The H021 primary signal is eligible and strictly positive, but the company is outside
the H021 primary top decile.

Research routing: remain WATCH. A positive revision alone does not override the
prospective H021 selection rule.

### FLAT

The H021 primary signal is eligible and exactly zero.

Research routing: thesis challenge, remain WATCH.

### NEGATIVE

The H021 primary signal is eligible and below zero.

Research routing: thesis challenge, remain WATCH.

### RELATIVE_TOP_DECILE_NONPOSITIVE

The company is in the H021 top decile but its absolute EPS revision is zero or negative.

This can occur when the whole cross-section is weak. Relative strength alone is not
treated as fundamental confirmation.

Research routing: thesis challenge, remain WATCH.

### NO_PRIMARY_SIGNAL

The H021 primary signal is unavailable because of fiscal-period, period-end, currency,
source, EPS, or analyst-coverage incompatibility.

Research routing: remain WATCH because the gate has no valid evidence.

## Scientific boundary

The rule was frozen on 2026-10-04, before the earliest valid comparison against the
2026-09-11 anchor on 2026-10-09.

No price return, benchmark return, PF001 result, later company outcome, discretionary
story, valuation judgment, or post-hoc threshold may change the state assignment.

The gate produces research priority only. Every emitted company row retains
`portfolio_eligibility_allowed=false` and `live_capital_allowed=false`.
