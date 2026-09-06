# H002 — Positive unexpected earnings / PEAD

## Status

`INCONCLUSIVE`

## Hypothesis

Positive unexpected earnings may be incorporated into Indian equity prices gradually, producing post-earnings-announcement drift after the immediate result reaction.

## Literature-style signal

```text
UE = (EPS_t - EPS_t-4) / price_day_minus_2
```

This mirrors a simple seasonal unexpected-earnings proxy used in Indian PEAD research.

## Frozen feasibility decision rule

- Universe: preselected liquid non-financial Indian companies in the July 2025 result cohort.
- Do not trade the event day or first subsequent session.
- Enter at the open of the second trading session after the result.
- Hold exactly 20 trading sessions.
- Compare with Nifty 50 and a simple momentum benchmark.

## Feasibility result

24 observations had independently verified delayed-entry/exit prices.

### Ranked UE magnitude

- Pearson correlation with Nifty excess return: **0.214**, p = **0.315**
- Spearman correlation: **0.230**, p = **0.281**
- highest-UE quintile excess return: **-2.58 pp**
- lowest-UE quintile excess return: **-1.80 pp**

The ranked 20-session implementation did not replicate a clean PEAD effect.

### Positive vs negative UE

- Positive UE observations: 16
- Negative UE observations: 8
- Positive UE mean excess: **+1.99 pp**
- Negative UE mean excess: **-1.17 pp**
- Spread: **+3.16 pp**
- Spread p-value: **0.233**
- Bootstrap 95% CI: **-1.67 pp to +7.96 pp**
- Positive UE beat rate: **62.5%**
- Negative UE beat rate: **37.5%**

The sign moves in the economically expected direction, but the sample is small, uncertainty crosses zero, and the result is sensitive to a handful of observations.

## Decision

**No live capital.**

The only justified next step is a prospectively frozen paper test using original point-in-time exchange filings and, where available, timestamped analyst consensus / standardized unexpected earnings.

Do not optimize the current result into significance.
