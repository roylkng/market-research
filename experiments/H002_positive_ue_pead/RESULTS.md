# EXP-2026-09-06-H002 — Results

## Verdict

`INCONCLUSIVE`

## Ranked unexpected earnings

| Metric | Result |
|---|---:|
| Pearson(UE, excess vs Nifty) | 0.214 |
| Pearson p-value | 0.315 |
| Spearman(UE, excess vs Nifty) | 0.230 |
| Spearman p-value | 0.281 |
| Highest-UE quintile excess | -2.58 pp |
| Lowest-UE quintile excess | -1.80 pp |

The ranked 20-session implementation did not replicate a clean PEAD effect.

## Positive versus negative UE

| Metric | Positive UE | Negative UE |
|---|---:|---:|
| Observations | 16 | 8 |
| Mean excess vs Nifty | +1.99 pp | -1.17 pp |
| Beat Nifty | 62.5% | 37.5% |

Positive-minus-negative mean spread: **+3.16 pp**.

- spread p-value: **0.233**
- bootstrap 95% CI: **-1.67 pp to +7.96 pp**

The direction is economically interesting but statistically insecure and sensitive to large winners/losers.

## Stress tests

- Remove Maruti and Eicher: positive-minus-negative spread falls to roughly **+0.86 pp**.
- Remove several large negative-tail observations: spread similarly falls toward **+0.87 pp**.
- The whole cohort's apparent excess return also collapses when its largest winners are removed.

## Decision

No live capital. Proceed only to a prospectively frozen paper test using original point-in-time filings and a pre-defined unexpected-earnings/SUE rule. Do not optimize this pilot into significance.
