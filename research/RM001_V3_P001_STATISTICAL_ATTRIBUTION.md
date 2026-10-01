# RM001-v3 P001 Historical Statistical-Risk Attribution

Status: FROZEN BEFORE MATERIALIZATION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Materialize RM001-v3 on the established AE001/RM001-v2 historical evidence
plane and quantify what the frozen five-PC statistical layer changes in risk
decomposition.

P001 is a structural risk-model attribution study.

It is NOT an out-of-sample risk-forecast validation and it does NOT test alpha.

## Frozen historical source window

    2025-09-01 through 2026-09-25

## Frozen comparison session

    2026-08-31

This is the existing sealed I002/I003 decision date.

No post-31-Aug portfolio return outcome is opened by P001.

## Parent reconstruction

Rebuild RM001-v2 using the merged frozen contracts:

- same official NSE market panel;
- same corporate-action-safe feature plane;
- same D007 Security File size panel;
- same RM001-v2 factor definitions;
- same 60-session v2 factor covariance;
- same 60-session v2 idiosyncratic risk.

Required parent artifacts:

- RM001-v2 exposure panel;
- RM001-v2 factor history;
- RM001-v2 risk state as of 2026-08-31.

## Challenger

Build RM001-v3 from the exact rebuilt v2 risk state + v2 factor history.

Frozen effective v3 contract:

- 120-session residual-PCA basis;
- 5 statistical PCs;
- minimum 500 complete current identities;
- deterministic component signs;
- singular-value non-degeneracy gate;
- 60-session combined factor covariance;
- 60-session post-PC idiosyncratic variance;
- incomplete statistical histories retain exact v2 idiosyncratic variance and
  zero statistical exposures.

## Materialization integrity gates

P001 fails closed unless:

1. v2 and v3 as-of sessions are both 2026-08-31;
2. v3 parent v2 risk-state SHA equals the rebuilt v2 state SHA;
3. v3 parent v2 factor-history SHA equals the rebuilt v2 history SHA;
4. v2 and v3 current symbol+ISIN identity sets are exactly identical;
5. v3 security count equals v2 security count;
6. complete statistical identity count >= 500;
7. five statistical factors exist;
8. every frozen adjacent singular-value relative gap passes v3 P1;
9. covariance matrix is finite and 11x11;
10. all current v3 statistical exposures are finite;
11. every non-stat-complete current identity preserves the exact v2
    idiosyncratic variance.

## Structural attribution

For identities with complete 120-session statistical history report:

- count and coverage of current v2 universe;
- v2 median idiosyncratic variance;
- v3 median post-PC idiosyncratic variance;
- median variance change;
- v2 mean idiosyncratic variance;
- v3 mean post-PC idiosyncratic variance;
- first-five statistical explained-variance ratios;
- cumulative five-PC explained-variance ratio;
- singular values and adjacent relative gaps.

This in-sample residual reduction is descriptive only.

It is NOT a v3 promotion criterion.

## Portfolio attribution

Use the exact sealed I002 integrated study artifact:

    research/po001-i003/inputs/i002-integrated-control-v1.json.gz

Frozen preserved portfolios:

1. equal_weight_top_decile
2. positive_alpha_proportional_top_decile

These are used because their exact complete position vectors are preserved in
the sealed artifact.

For each exact portfolio compare v2 and v3:

- factor variance;
- idiosyncratic variance;
- total daily variance;
- annualized volatility;
- named-factor exposures;
- v3 statistical-factor exposures;
- v3 statistical-factor variance contributions;
- total statistical contribution;
- total-risk delta.

Named-factor portfolio exposures must be identical between v2 and v3 within
1e-12 because v3 inherits them unchanged.

## Interpretation

P001 can establish:

- the statistical layer materializes deterministically on real data;
- the latent factors absorb common covariance previously left in residual risk;
- the effect on exact historical portfolio risk decomposition.

P001 cannot establish:

- superior out-of-sample risk forecasting;
- better realized VaR;
- alpha improvement;
- sector equivalence;
- prospective readiness;
- live-capital readiness.

## Next gate

A separately frozen RM001-v3 P002 walk-forward OOS risk-calibration study is
required before v3 may replace v2 as the preferred historical risk model.

No live-capital implication.
