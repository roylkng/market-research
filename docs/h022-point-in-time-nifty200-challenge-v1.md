# H022 point-in-time Nifty 200 universe challenge

Status: **INCONCLUSIVE_POINT_IN_TIME_CHALLENGER**

Live capital: **DISABLED**

## Purpose

The original H022 historical replay was PROMISING on the Sep-2026 U001 survivor panel. H022-UX001 tests whether that result survives a materially less survivor-biased universe: reconstructed event-date Nifty 200 base membership across the challenge period.

This is not an exact reconstruction of historical U001. The challenger uses the full historical Nifty 200 base membership, including financials, because a reproducible official source for historical U001 top-100 non-financial free-float ranking was not established. Therefore attenuation in this test cannot be attributed to survivorship alone; universe composition also changes.

## Frozen inputs

- H022 feature formula: unchanged `H022-R001`;
- execution/evaluation rule: unchanged `H022-X001`;
- challenger rule: `H022-UX001`;
- expanded outcome-free feature panel SHA-256: `f07dd7b9c7925b53b10bca1926b40a086832df3bbe6dbdb42caea43164d617fa`;
- challenge signals: **753**;
- historical Nifty 200 membership reconstruction SHA-256: `dee26ffc683781202da21e789cc45f480d625772e8510f3beb1f65aa4a6ba144`;
- primary horizon: **60 sessions**;
- market-data cutoff: **2026-09-11**;
- benchmark: official NIFTY 500 price index over the identical executable interval;
- classification thresholds: unchanged from the original preregistration.

No H022 feature, threshold, horizon or classification gate was changed after the expanded outcomes were opened.

## Evidence coverage

- challenge symbols: **196**;
- corporate-action audits: **196/196 READY**;
- unresolved corporate-action audits: **0**;
- official NIFTY 500 session artifacts: **235**;
- official NSE CM UDiFF session artifacts: **205**;
- requested stock bars: **2,323**;
- observed stock bars: **2,323**;
- missing stock bars: **0**.

At the primary 60-session horizon:

- mature signals: **565**;
- complete outcomes: **559**;
- complete share of mature: **98.94%**;
- corporate-action blocked: **6**;
- not mature by cutoff: **188**.

The primary result is therefore not explained by missing-price coverage.

## Primary result: 60 sessions

- Spearman H022 signal vs future excess: **0.1147**;
- Spearman p-value: **0.0066**;
- top-quintile mean excess: **+3.37 pp**;
- bottom-quintile mean excess: **+1.10 pp**;
- top-minus-bottom mean spread: **+2.28 pp**;
- top-quintile median excess: **+2.74 pp**;
- top-quintile benchmark beat rate: **53.15%**;
- symbol-cluster bootstrap 95% CI for spread: **[-1.66 pp, +6.15 pp]**.

Frozen classification: **INCONCLUSIVE**.

The broader replay preserves a positive rank relationship and clears the PROMISING spread and median conditions, but it fails the frozen **55% top-quintile benchmark-beat requirement**. The cluster-bootstrap interval also crosses zero.

## Comparison with the original survivor-panel replay

| Metric | Original current-U001 replay | Point-in-time Nifty 200 challenger |
| --- | ---: | ---: |
| Challenge signals | 398 | 753 |
| Complete 60-session outcomes | 295 | 559 |
| Spearman | 0.1381 | 0.1147 |
| Top-quintile mean excess | +5.56 pp | +3.37 pp |
| Bottom-quintile mean excess | +2.37 pp | +1.10 pp |
| Top-minus-bottom spread | +3.19 pp | +2.28 pp |
| Top-quintile median excess | +5.75 pp | +2.74 pp |
| Top-quintile beat rate | 55.93% | 53.15% |
| Bootstrap 95% CI | [-2.45, +9.13] pp | [-1.66, +6.15] pp |
| Frozen classification | PROMISING | INCONCLUSIVE |

The 60-session effect attenuates but does not disappear. That is weaker evidence than the original replay suggested.

## Secondary horizons

### 20 sessions

- complete: **729 / 730 mature**;
- Spearman: **0.0824**, p = **0.0261**;
- top-quintile mean excess: **+0.46 pp**;
- top-minus-bottom spread: **+0.66 pp**;
- top-quintile median excess: **+0.29 pp**;
- top-quintile beat rate: **53.10%**;
- 50-bps cost-stressed top-quintile mean excess: approximately **-0.04 pp**.

This remains economically weak at the short horizon.

### 120 sessions

- complete: **364 / 373 mature**;
- Spearman: **0.0273**, p = **0.6032**;
- top-quintile mean excess: **+4.46 pp**;
- bottom-quintile mean excess: **+4.14 pp**;
- top-minus-bottom spread: **+0.32 pp**;
- top-quintile median excess: **+1.12 pp**;
- top-quintile beat rate: **52.78%**;
- bootstrap 95% CI: **[-5.27 pp, +5.98 pp]**.

The strong 120-session result seen in the original survivor panel does **not** replicate in the broader point-in-time challenger. It should no longer be treated as persuasive supporting evidence.

## Exclusions

There are no missing stock bars. Corporate-action blocking is explicit and limited to observed share-changing events such as ADANIENT rights, HDFCAMC bonus, HINDUNILVR demerger, KOTAKBANK split, VEDL demerger, IRB bonus and LICI bonus, depending on horizon.

The compact ledger is:

`research/historical/h022/expanded-nifty200-challenge-v1/exclusions-summary.json`

## Evidence hashes

- outcome report SHA-256: `310d3709393047db4ec5e2eacb9d333fac2d81b83e86bc65140dc4bc60c6d22f`;
- outcome summary SHA-256: `e02d9510dcb2b8afa4724c0773cac3500c59ffda63774d30adf73f37b763934e`;
- evidence manifest SHA-256: `8bcf22c3f166b75a6f46b835a0091415cfb08d3dd455fe2351b7bb9abf642200`;
- exclusions summary SHA-256: `c4a0a7332c30e5bab93cdb4a88d5e117e8be37267197d0326fcd50a9aad6ad91`;
- raw official-evidence Actions artifact: `10324410168`;
- raw artifact digest: `sha256:4a67e7eff43f13a63d7b586f03e496733d43cc6679c5a4f070135d47bed3b3e2`.

## Interpretation

The correct update is **downgrade, not discard**.

H022 still shows a positive medium-horizon cross-sectional relationship in the broader historical universe, and the 60-session Spearman relationship remains statistically non-zero. But the preregistered promotion rule deliberately requires more than a positive correlation. The broader challenger misses the benchmark-beat gate and remains bootstrap-uncertain.

Therefore:

1. the original `PROMISING_HISTORICAL_DEVELOPMENT` result is not robust enough to generalize to the point-in-time Nifty 200 challenger;
2. current-survivor selection and/or universe composition likely amplified the original effect;
3. simple prior 60-session momentum does not explain the original signal, per H022-D001, but that does not rescue the universe-robustness failure;
4. the original strong-looking 120-session secondary result should be treated as fragile because it collapses in the expanded replay;
5. H022 must remain outside live-capital authorization and should not receive a numerical alpha probability from this evidence.

## Next falsification gates

The useful next work is not to tune H022-R001. Keep it frozen and test why the effect attenuates:

1. **sector/industry attribution** on the expanded point-in-time sample;
2. compare the current-U001 subset versus the additional historical Nifty 200 members as an explicitly post-outcome diagnostic;
3. point-in-time size/value/quality controls where reproducible historical data exist;
4. overlapping-window and repeated-company dependence diagnostics;
5. independent prospective confirmation.

Any H022 × momentum, sector-filtered, semantic, Q&A or 120-session variant must be a separately frozen challenger rather than a rewrite of H022-R001.
