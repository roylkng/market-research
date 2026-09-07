# H002-HR001 historical transport result, partial as of 2026-09-07

## Status

This is supporting historical evidence for H002. It is not prospective evidence and it does not authorize live capital.

The Phase-A signal manifest remains frozen at:

`2062e21ee1b1cbcd86d758ae3cf9ef9aeb43664c629ca5eb7a22cd885068ef98`

Phase A contains 178 executable historical signals from 200 planned company-quarter observations:

- 140 POSITIVE UE
- 38 NEGATIVE UE
- 2 NO_SIGNAL
- 9 SKIPPED
- 11 UNCOVERED
- 0 ERROR

The first Phase-B reconstruction completed 163 of those 178 signals. Fifteen FY27-Q1 observations have scheduled 20-session exits on or after 2026-09-07 and therefore are not yet fully matured. A runner defect initially attempted to download those future bhavcopies and classified the resulting 404s as errors. The sharded runner now treats same-day/future exits as `PENDING` and does not inspect corporate actions or outcome archives beyond the fully elapsed reconstruction horizon.

## Matured sample

The 163 completed observations contain:

- 127 POSITIVE UE
- 36 NEGATIVE UE
- 94 unique companies
- 84 completed FY26-Q4 observations
- 79 completed FY27-Q1 observations

The same company can occur in both quarters. Therefore observation-level p-values are reported for comparability, but the company-cluster bootstrap and leave-one-company-out tests are more important.

## Nifty 50 benchmark

Across all 163 matured observations:

- POSITIVE UE mean 20-session excess return: **+1.80 percentage points**
- NEGATIVE UE mean 20-session excess return: **-0.51 percentage points**
- POSITIVE minus NEGATIVE spread: **+2.31 percentage points**
- Welch p-value: **0.0313**
- Fisher beat-rate p-value: **0.0378**
- company-clustered 95% spread interval: **+0.24 to +4.35 percentage points**
- leave-one-company-out spread range: **+1.96 to +2.85 percentage points**
- Pearson correlation between UE and excess return: **0.168**, p = **0.0324**
- Spearman correlation: **0.151**, p = **0.0540**

The POSITIVE group beat Nifty 50 in 59.1% of completed observations. The NEGATIVE group beat Nifty 50 in 38.9%.

### Quarter split

FY26-Q4 does not show convincing separation:

- POSITIVE mean excess: +1.20%
- NEGATIVE mean excess: +0.60%
- spread: +0.60 percentage points
- clustered 95% interval: -2.87 to +3.82
- Welch p-value: 0.725

FY27-Q1 is much stronger:

- POSITIVE mean excess: +2.42%
- NEGATIVE mean excess: -1.76%
- spread: +4.18 percentage points
- clustered 95% interval: +2.03 to +6.48
- Welch p-value: 0.000665
- Spearman UE/excess-return correlation: 0.279, p = 0.0128

This quarter instability is a major reason not to promote the current historical result to validation-grade evidence.

## Nifty 200 Momentum 30 benchmark

Across all 163 matured observations:

- POSITIVE UE mean excess return: **+0.13 percentage points**
- NEGATIVE UE mean excess return: **-1.93 percentage points**
- spread: **+2.05 percentage points**
- Welch p-value: 0.0684
- company-clustered 95% spread interval: **-0.10 to +4.20 percentage points**
- leave-one-company-out spread range: +1.62 to +2.62 percentage points
- Pearson UE/excess correlation: 0.155, p = 0.0489
- Spearman correlation: 0.144, p = 0.0671

The POSITIVE group itself does not beat the momentum benchmark on average. Most of the binary separation comes from the NEGATIVE-UE group underperforming momentum materially.

FY27-Q1 again shows strong separation, +4.17 percentage points, while FY26-Q4 is essentially flat at +0.17 percentage points.

## Winner dependence

Against Nifty 50, removing the two largest POSITIVE-UE winners reduces the POSITIVE group mean excess return from +1.80% to +1.47%, which remains positive.

Against Momentum 30, removing the two largest POSITIVE-UE winners changes the POSITIVE group mean excess return from +0.13% to -0.20%. This reinforces that H002 is currently better supported as a negative-surprise avoidance signal than as a standalone positive-surprise alpha signal versus momentum.

## Transaction-cost stress

The POSITIVE-UE stocks have mean raw 20-session stock return of +1.11%. Applying the frozen round-trip cost stresses gives approximately:

- 0 bps: +1.11%
- 25 bps: +0.86%
- 50 bps: +0.61%

The NEGATIVE-UE group has mean raw stock return of -1.08%, declining to -1.33% and -1.58% at 25 and 50 bps respectively.

Because the same round-trip cost is applied to both signal groups, the POSITIVE-minus-NEGATIVE spread itself is unchanged by symmetric cost stress. The economically relevant question for a long-only implementation is whether the POSITIVE group continues to beat the chosen benchmark after costs.

## Interpretation

Current evidence supports three conclusions, in descending confidence:

1. **Negative UE is useful as a risk/avoidance feature.** Negative-surprise companies materially underperformed both broad-market and momentum benchmarks in FY27-Q1 and in the pooled sample.
2. **Positive UE has some broad-market alpha evidence but weak incremental evidence over momentum.** It beats Nifty 50 in the pooled sample, but its mean excess return versus Momentum 30 is near zero.
3. **The effect is not stable enough across quarters to use H002 alone as the high-upside stock picker.** FY26-Q4 is nearly flat while FY27-Q1 is strong.

Therefore H002 should currently be treated as one layer in a multi-signal company-selection system. It is more defensible as a filter that removes likely laggards, while H003 management delivery credibility, quality/growth features, valuation and other independently frozen signals are used to identify asymmetric upside among the survivors.

## Remaining validity gaps

- 15 of 178 executable observations are still pending their frozen 20-session exit horizon.
- HR001 uses the September-2026 U001 cohort retrospectively and is therefore survivorship-sensitive.
- Only two historical target quarters are represented.
- The prospective FY27-Q2 H002 test remains the authoritative out-of-sample experiment.

Next evidence upgrades are:

1. finish the 15 pending HR001 exits as they mature without changing Phase A;
2. extend historical reconstruction to additional quarters using only point-in-time-available filings;
3. replace the fixed 2026 cohort with point-in-time historical Nifty-200 membership for validation-quality replays;
4. combine H002 with H003 only after each signal's standalone historical behavior is measured.
