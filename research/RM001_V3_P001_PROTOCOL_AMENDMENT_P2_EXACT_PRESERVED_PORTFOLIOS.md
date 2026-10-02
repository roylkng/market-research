# RM001-v3 P001 Protocol Amendment P2: Exact Preserved I002 Portfolios

Frozen: 2026-10-02
Status: FROZEN AFTER FAIL-CLOSED MATERIALIZATION, BEFORE ANY P001 ATTRIBUTION RESULT
Live capital: DISABLED

## Trigger

The first real RM001-v3 P001 materialization, workflow run 36958406605,
successfully completed:

- official NSE market reconstruction;
- corporate-action-safe AE001 feature reconstruction;
- all D007-bound historical SIZE inputs;
- RM001-v2 parent risk state and factor history;
- RM001-v3 statistical risk state.

The real RM001-v3 state passed the frozen model gates:

- 1,307 current identities;
- 995 identities with complete 120-session statistical history;
- 312 conservative RM001-v2 fallbacks;
- five finite, non-degenerate statistical components;
- 11-factor finite covariance;
- statistical explained residual-variance ratio total
  = 0.10786735768098399.

The run then failed closed before emitting any P001 attribution report because the
sealed I002 artifact does not persist full position vectors for:

- risk_aware_zero_cost;
- full_po001_observable_cost_floor.

This is the same immutable-evidence limitation already documented by
RM001-v2 P001-P1.

## Evidence constraint

The missing optimizer target vectors cannot be recovered from their artifact
hashes or compact summaries.

A fresh PO001-v1 solve cannot be described as the exact sealed I002 portfolio.
Prior I003 work demonstrated numerical optimizer sensitivity on locally flat
PO001-v1 solution surfaces.

Therefore RM001-v3 P001 must not reconstruct, approximate or re-optimize the
missing controls.

## Exact preserved I002 portfolios

The sealed I002 artifact retains complete position vectors for exactly:

1. equal_weight_top_decile
2. positive_alpha_proportional_top_decile

P001-P2 narrows portfolio attribution to these two immutable historical controls.

## Unchanged RM001-v3 treatment

P2 does NOT change:

- RM001-v2 parent state/history;
- 120-session residual-PCA basis;
- five statistical components;
- 60-session covariance clock;
- 60-session idiosyncratic-risk clock;
- singular-value gates;
- complete-history threshold;
- any v3 exposure, covariance or idiosyncratic variance.

The real v3 state materialized before this amendment remains valid risk-model
evidence because the failure occurred only when loading unavailable portfolio
weight vectors.

## Required P001 outputs after P2

Universe-level attribution remains unchanged:

- complete/fallback identity counts;
- singular values and relative gaps;
- explained residual variance;
- v2/v3 idiosyncratic variance distribution;
- lower/higher/unchanged idiosyncratic counts;
- v2/v3 factor variances.

Portfolio attribution is required for BOTH exact preserved controls:

- equal_weight_top_decile;
- positive_alpha_proportional_top_decile.

For each report:

- v2/v3 annualized volatility;
- total/factor/idiosyncratic variance delta;
- named-factor exposure delta;
- statistical-factor exposures;
- statistical-factor variance contributions.

## Interpretation

P001 may make risk-attribution claims only for those two exact preserved
portfolios.

P001 may NOT claim RM001-v3 attribution for the unavailable optimized I002
portfolio vectors.

## Outcome boundary

No stock-return outcome was opened by the failed run.

No alpha model was fitted.

No portfolio was re-optimized.

No prospective or live-capital claim is created.
