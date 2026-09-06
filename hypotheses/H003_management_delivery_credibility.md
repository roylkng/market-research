# H003 — Prior management delivery credibility

Status: **FROZEN**  
Live capital: **NO**

## Question

Do liquid Indian non-financial companies with a stronger pre-existing record of management delivering measurable operating commitments outperform over the next 120 trading sessions?

## Mechanism

Execution credibility may persist. Markets may not fully distinguish management teams that repeatedly deliver earlier capacity, volume, margin, deleveraging, order-conversion, product-launch, customer-ramp and project-completion commitments from teams that repeatedly miss or delay them.

The hypothesis is intentionally independent of H002. H002 tests post-earnings-announcement drift over 20 sessions. H003 tests medium-term company selection from **prior** delivery evidence.

## Frozen signal v1

At the timestamp of the frozen U001 cohort snapshot:

```text
prior_management_delivery_met_rate_v1
    = MET / (MET + PARTIAL + MISSED + LATE)
```

Rules:

- only claims with `source_date <= decision_date` exist in the information set,
- only outcomes with `observed_date <= decision_date` may affect the feature,
- the latest outcome known by the decision date is used for each claim,
- `UNRESOLVED` and claims without outcomes are reported but excluded from the denominator,
- at least **3 resolved claims** are required,
- fewer than 3 resolved claims produces `NO_SIGNAL`, not a neutral value,
- no weights by claim type,
- no weights for PARTIAL/MISSED/LATE beyond all being non-MET in the primary v1 feature,
- the current reconstructed lifecycle status of a claim is not used as a feature.

## Universe

U001: top 100 non-financial Nifty 200 constituents by NSE free-float market capitalization, frozen for the cohort before outcomes are observed.

## Decision and horizon

- decision information set: U001 snapshot timestamp,
- paper entry convention: next eligible trading-session open,
- primary holding horizon: 120 trading sessions.

## Benchmarks

- Nifty 200,
- deterministic sector-matched benchmark where available,
- Nifty 200 Momentum 30 / investable equivalent.

## Historical reconstruction versus prospective evidence

We may reconstruct older claims and outcomes to build the **pre-existing history** available at launch. That does not make old return windows untouched out-of-sample evidence.

The strongest test begins when the feature values are frozen for a cohort and subsequent 120-session returns have not yet occurred.

## Research prior

Management-forecast literature documents persistence in prior forecast accuracy and credibility, and evidence that predictable forecast bias can be incompletely priced. This motivates H003 but does not establish that the broader operational-commitment formulation works in India.

References:

- Preussner (2022), *The Accuracy and Informativeness of Management Earnings Forecasts: A Review and Unifying Framework*, Accounting Perspectives: https://doi.org/10.1111/1911-3838.12294
- Kitagawa & Shuto, *Credibility of Management Earnings Forecasts and Future Returns*: https://www.rieb.kobe-u.ac.jp/academic/ra/dp/English/dp2013-30.html

## Rejection discipline

Do not rescue H003 by retrospectively adding claim-type weights, changing the three-claim minimum, changing the primary horizon, or combining it with H002/momentum after seeing returns. Any such variant receives a new hypothesis/version and future observations.
