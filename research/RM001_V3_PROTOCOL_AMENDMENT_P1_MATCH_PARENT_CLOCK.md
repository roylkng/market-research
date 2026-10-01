# RM001-v3 Protocol Amendment P1: Match Parent Risk Estimation Clock

Frozen: 2026-10-02
Status: FROZEN BEFORE FIRST REAL-DATA RM001-v3 MATERIALIZATION
Live capital: DISABLED

## Trigger

The initial RM001-v3 foundation froze a 120-session residual-PCA estimation
window and also used that same 120-session window for combined factor covariance
and post-statistical idiosyncratic variance.

Before any real-data RM001-v3 state was materialized, review identified a
treatment confound:

- RM001-v2 factor covariance uses 60 realized sessions;
- RM001-v2 idiosyncratic variance uses up to 60 residual sessions;
- changing those clocks to 120 in v3 would mix window-length effects with the
  incremental statistical-factor treatment.

No real RM001-v3 result existed when P1 was frozen.

## Frozen correction

### Statistical basis estimation

Unchanged:

    latest 120 realized RM001-v2 residual sessions

The five statistical PC loadings and factor-return histories are learned on the
full 120-session residual matrix.

### Combined factor covariance

Changed to match RM001-v2:

    latest 60 realized sessions

Use the final 60 rows of:

- six RM001-v2 named factor returns;
- five RM001-v3 statistical factor returns generated from the frozen 120-session
  basis.

Estimator remains sample covariance, ddof=1, no shrinkage.

This preserves named/statistical cross-covariance while keeping the parent
risk-estimation clock fixed.

### Post-statistical idiosyncratic variance

Changed to match RM001-v2:

    latest 60 post-PC residual sessions

Estimator remains sample variance, ddof=1.

The PCA basis still comes from 120 sessions. Only the risk-estimation window is
matched to the parent.

### Incomplete-history identities

Unchanged:

- zero statistical exposures;
- exact RM001-v2 idiosyncratic variance retained;
- no imputation.

## Scientific interpretation

After P1, the v2-v3 treatment difference is:

    ADD FIVE STATISTICAL RESIDUAL FACTORS

while preserving the parent's:

- 60-session factor covariance clock;
- 60-session idiosyncratic-risk clock.

This amendment changes no alpha, portfolio outcome, or return-label handling.

No live-capital implication.
