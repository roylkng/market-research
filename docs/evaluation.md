# Evaluation standard

## What counts as evidence

A strategy is not evaluated by whether selected examples made money. It is evaluated over every eligible observation using frozen rules.

Primary outputs should include:

- mean and median return
- mean and median benchmark-relative return
- hit rate against benchmark
- Pearson and Spearman relationships where applicable
- confidence interval / bootstrap distribution
- winner concentration
- maximum favourable and adverse excursion when executable intraday data exists
- turnover and transaction-cost sensitivity
- performance by regime and market-cap segment

## Baselines

At minimum compare against:

1. broad-market exposure
2. sector-matched exposure when practical
3. simple momentum exposure
4. a naive recent-volatility / trend baseline for index forecasts

Complexity has to earn its place.

## Probability forecasts

Directional probabilities are evaluated across a series, not one observation. Use proper scoring rules such as Brier score and calibration buckets when sample size permits.

## Multiple testing

Every explored variant counts. Do not report only the best Sharpe or spread. Maintain the experiment registry and use deflated / multiple-testing-aware interpretation as the project grows.

## Rejection

A negative experiment is successful research if it prevents deployment of a false edge.

Current examples:

- H001 raw earnings acceleration: rejected
- H002 ranked unexpected-earnings magnitude at a 20-session horizon: rejected in the feasibility pilot
- H002 positive-vs-negative UE sign: inconclusive, prospective paper test required
