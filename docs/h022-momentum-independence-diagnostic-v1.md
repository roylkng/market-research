# H022-D001 — Prior-momentum independence diagnostic

Status: **SUPPORTIVE_INDEPENDENCE (POST-OUTCOME DIAGNOSTIC)**

Live capital: **DISABLED**

## Purpose

H022's preregistered historical-development challenge was promising at 60 sessions, but that result could still be a disguised momentum effect: management may simply become more concrete when a stock/business is already doing well.

H022-D001 tests that alternative explanation using only price information available **before** each H022 entry.

This diagnostic was designed after H022 outcomes were opened. It therefore cannot upgrade H022 to validation and cannot change H022-R001 or H022-X001.

## Frozen control

For each H022 60-session `COMPLETE` outcome:

```text
prior_60_session_stock_return
  = stock_close(session - 60) -> stock_close(session - 1)

prior_60_session_nifty500_return
  = NIFTY500_close(session - 60) -> NIFTY500_close(session - 1)

prior_relative_momentum
  = stock_return - NIFTY500_return
```

The end session is always the exchange session immediately before the H022 entry. No same-day or later price enters the control.

Data sources:

- stock closes: official NSE CM UDiFF;
- benchmark closes: official NSE daily NIFTY 500 price-index snapshots;
- corporate actions: exact NSE corporate-action endpoint responses.

Share-changing actions inside the control window block the observation rather than invoking an inferred adjustment factor.

Frozen diagnostic rule: `registry/h022_momentum_independence_diagnostic_v1.yaml` (`H022-D001`).

## Coverage

Starting H022 primary outcomes: **295**

Momentum controls:

- READY: **285**
- CONTROL_BLOCKED by share-changing action: **8**
- missing required historical stock bar: **2**
- action audits: **94/94 READY**
- unresolved action audits: **0**
- benchmark source files: **129**
- UDiFF source files: **129**
- stock bars requested: **573**
- stock bars observed: **571**

Control-panel SHA-256:

`943abc9e1aef6728892b2892bef5118d81807ff92d550b233c4a98f86a45f4af`

Diagnostic-summary SHA-256:

`9d93cf803f76ff0f6e7921733a06b34b92b2631a7f5282327b4838ed0c9dd7cc`

Raw official evidence is preserved in Actions artifact `10322681489`, digest:

`sha256:606b522192318063c7853eb031aba19eff6b93c53692f800812e9b7239c7e792`

## Result

### Is H022 merely prior momentum?

No evidence of that in this diagnostic.

Spearman H022 signal vs prior relative momentum:

- rho: **-0.0213**
- p-value: **0.7201**

So the H022 information-delta score is essentially uncorrelated with the preceding 60-session stock-vs-Nifty move in this sample.

### Does prior momentum itself explain the later H022 return window?

Spearman prior relative momentum vs future 60-session excess:

- rho: **-0.0128**
- p-value: **0.8295**

Prior 60-session relative momentum has essentially no rank relationship with the subsequent H022 60-session excess window in these rows.

### Multivariate result

OLS specification:

```text
future_60d_excess
  ~ intercept
  + standardized_H022_signal
  + standardized_prior_relative_momentum
```

Estimated coefficients:

- standardized H022 coefficient: **+2.1212 pp**
- standardized prior-momentum coefficient: **-0.2762 pp**

Company-cluster bootstrap, 10,000 iterations:

- H022 coefficient 95% CI: **[+0.3891 pp, +4.1020 pp]**

The bootstrap interval remains above zero after controlling for prior relative momentum.

### Residualized H022 signal

After removing the linear relationship between H022 and prior momentum:

- Spearman residual-H022 vs future excess: **0.1465**
- p-value: **0.0133**

The rank relationship therefore survives momentum residualization.

### Interaction clue

Median prior relative momentum: **+2.2841 pp**

H022 top-minus-bottom spread calculated separately inside the two prior-momentum halves:

- lower prior-momentum half: **+0.7755 pp**
- higher prior-momentum half: **+5.5441 pp**

This is not part of H022's preregistered promotion rule. It is a post-outcome clue that H022 may be more useful **with** positive price recognition than in weak-price states.

Any `H022 × momentum` combination must therefore be a separately frozen challenger. It must not be retrofitted into H022-R001.

## Frozen interpretation

H022-D001 was frozen before the momentum-control data were opened:

`SUPPORTIVE_INDEPENDENCE` requires:

1. standardized H022 OLS coefficient > 0;
2. company-cluster bootstrap 95% lower bound > 0;
3. residualized H022 Spearman > 0.

All three conditions are satisfied.

Classification:

**SUPPORTIVE_INDEPENDENCE**

This means prior 60-session relative momentum does not explain away the observed H022 historical-development relation.

It does **not** mean H022 is validated alpha.

## What this changes

The leading concern for H022 is no longer simple prior price momentum.

The next important falsification gates are:

1. survivor bias / historical point-in-time universe membership;
2. sector exposure;
3. point-in-time quality/value characteristics;
4. overlapping-return dependence and repeated-company effects;
5. independent prospective confirmation.

The next historical work should prioritize point-in-time universe reconstruction and sector/factor attribution rather than adding richer transcript features.
