# H002-HR003 survivorship-clean historical result

Date: 2026-09-07

## Status

H002-HR003 is the point-in-time Nifty 200, non-financial historical transport test of H002-R001. It removes the principal survivorship defect of HR001/HR002 by using the Nifty 200 membership that actually existed at each historical freeze.

This is historical reconstruction evidence. It is not prospective evidence and it does not authorize live capital.

Frozen Phase-A identity:

`77104e3f675578c6b756c950a96a3e13e64fe133c25b48249df68484f25fa3d9`

Frozen Phase-B identity:

`061727c95569ad7724e43f117189dca90e6a5fc0f54002b3d7685ce15712f4b2`

The exact pre-existing HR002 actionability thresholds were applied without changes after HR003 outcomes became visible.

## Coverage

Phase A contains 919 point-in-time company-quarter observations across six historical freezes:

- 568 executable H002 signals
- 388 POSITIVE
- 177 NEGATIVE
- 3 ZERO
- 6 NO_SIGNAL
- 298 SKIPPED
- 47 UNCOVERED
- 0 ERROR

At the 2026-09-07 reconstruction cutoff, Phase B contains:

- 534 COMPLETED 20-session outcomes
- 31 PENDING outcomes whose frozen exit horizon has not fully elapsed
- 3 SKIPPED_PRICE_BASIS observations
- 0 ERROR
- 0 MISSING_BENCHMARK

The completed binary sample contains 366 POSITIVE and 166 NEGATIVE observations across 164 stable company identity clusters.

## Primary broad-market result

Against Nifty 50 across the 534 completed observations:

- POSITIVE UE mean excess return: **+1.3619%**
- NEGATIVE UE mean excess return: **+0.2599%**
- POSITIVE minus NEGATIVE spread: **+1.1021 percentage points**
- company-clustered 95% spread interval: **-0.3187 to +2.4787 percentage points**
- leave-one-company-out minimum spread: **+0.9295 percentage points**
- leave-one-company-out maximum spread: +1.3364 percentage points
- POSITIVE beat rate: 57.1%
- NEGATIVE beat rate: 44.0%

The pooled spread is economically positive and is not dependent on one company, but the pre-registered company-cluster confidence interval still crosses zero. Therefore WATCHLIST_FILTER does not pass.

### Quarter behavior versus Nifty 50

Binary POSITIVE-minus-NEGATIVE spread:

- FY25-Q4: +9.1362pp, but only five completed observations and therefore not independently informative
- FY26-Q1: +0.4460pp
- FY26-Q2: insufficient NEGATIVE observations for a binary quarter evaluation
- FY26-Q3: +1.8942pp
- FY26-Q4: -0.4576pp
- FY27-Q1: +3.3073pp

Four evaluable quarters have positive separation and one has negative separation.

Every leave-one-quarter-out pooled Nifty-50 spread remains positive:

- omit FY25-Q4: +1.0141pp
- omit FY26-Q1: +1.3125pp
- omit FY26-Q2: +1.2781pp
- omit FY26-Q3: +0.8333pp
- omit FY26-Q4: +1.5834pp
- omit FY27-Q1: +0.5930pp

This is meaningful stability evidence. It says the pooled positive separation is not created solely by any one quarter, even though the cluster-level uncertainty remains too wide for promotion.

## Momentum factor control

Against Nifty 200 Momentum 30:

- POSITIVE UE mean excess return: **+0.0275%**
- NEGATIVE UE mean excess return: **-1.0941%**
- POSITIVE minus NEGATIVE spread: **+1.1216 percentage points**
- company-clustered 95% spread interval: **-0.3172 to +2.5210 percentage points**
- leave-one-company-out minimum spread: **+0.9639 percentage points**

After the frozen 50-bp round-trip cost stress, the POSITIVE group has **-0.4725%** mean excess return versus Momentum 30. Therefore H002 does not demonstrate incremental long alpha over a strong momentum factor.

The NEGATIVE group underperforms Momentum 30 on average, but does so in only three sufficiently represented quarters; the frozen ACTIONABLE_AVOIDANCE gate requires at least four.

## Long-only economics

For POSITIVE UE versus Nifty 50 after the frozen 50-bp cost stress:

- pooled mean excess return: **+0.8619%**
- positive in five of six represented quarters
- after removing the two largest POSITIVE-group winners, the Nifty-50 excess-return mean remains **+1.2369%** before the explicit cost adjustment used by the gate

So the broad-market long economics are encouraging and are not simply a two-winner artifact. They are nevertheless insufficient for LONG_ALPHA_CANDIDATE because the same POSITIVE group fails to beat Momentum 30 after costs.

## Frozen verdict

The unchanged HR002 actionability gate returns:

`EXPLORATORY_ONLY`

- WATCHLIST_FILTER: FAIL
- ACTIONABLE_AVOIDANCE: FAIL
- LONG_ALPHA_CANDIDATE: FAIL
- CAPITAL_READY: FAIL

The material failures are:

1. the pooled company-cluster confidence interval crosses zero against both Nifty 50 and Momentum 30;
2. NEGATIVE UE underperforms Momentum 30 in only three represented quarters rather than the required four;
3. POSITIVE UE does not beat Momentum 30 after the 50-bp cost stress;
4. the prospective FY27-Q2 H002 experiment has not yet completed.

## Research conclusion

H002 contains useful information, but historical evidence does not support using it as a standalone buy, sell or short rule.

The appropriate role of H002 in the next system is frozen conceptually as follows:

- **NEGATIVE UE:** fundamental/event deterioration penalty. It can reduce a company's rank or exclude a marginal candidate when corroborated by other signals. It is not an automatic sell/short trigger.
- **POSITIVE UE:** supportive evidence that can raise confidence in an already strong company. It is not sufficient by itself to identify a high-upside stock.
- **ZERO/NO_SIGNAL:** no directional contribution.

No H002 threshold, sign definition or horizon should now be tuned on HR003 to manufacture promotion.

## Next experiment

The next high-value hypothesis is not a more optimized H002. It is whether H002 improves an independently constructed company-quality/catalyst ranker.

The combined research system should be assembled from independently motivated components:

1. H003 management delivery credibility;
2. fundamental growth and quality/capital-efficiency features;
3. valuation and expectation-risk features;
4. market momentum/relative-strength control;
5. H002 as a corroborating event/fundamental direction feature.

Combination weights and promotion criteria must be frozen before evaluating the combined historical outcomes. H002's role above must not be changed in response to the combined result.

The prospective FY27-Q2 H002 experiment remains the authoritative out-of-sample confirmation before any H002-dependent rule can become capital-ready.
