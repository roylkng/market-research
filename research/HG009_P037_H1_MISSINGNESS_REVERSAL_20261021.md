# HG009 P037: October 15 H1 original-source missing-price falsification

**Analysis date:** October 21, 2026. **Observation date:** October 15, 2026. **Status:** POSTHOC source sensitivity, not preregistered alpha. **Live capital:** disabled.

## Why another audit matters

HG009's predeclared 100-company "selected" group underperformed the one-signal and zero-signal comparison groups on the first real NSE day. That is informative negative evidence, but **two securities lacked original NSE EQ quotations**. The earlier H1 study correctly left missing stock returns as null and compared only available stocks.

An observed-only group mean of 99 names cannot be called the actual equal-weight return of the original 100-stock arm. Nor may a missing security's return be assumed to be zero or its absence be quietly ignored as a delisting-free survivor sample.

## Original evidence and exact population

Immutable original HG009 P006 H1 document: research/hg009/price-diagnostics/HG009-P006-H1-20261015-v1.json. Original Git blob SHA: 2cca82f5598504ee280320e2d757d7a75c581d7b. Original document SHA-256: 811fbb1e18481b43ab5b4c6f9bda827b3bb83709c2388b2c7f55038a856ed2b3.

| Frozen original arm | Source-priced EQ companies | Missing original NSE EQ | Mean unadjusted 15 Oct open-to-close price change |
|---|---:|---|---:|
| Selected | 99/100 | RETAIL | -1.410336% |
| One-signal comparator | 99/100 | MOREPENLAB | -1.268997% |
| Zero-signal comparator | 100/100 | None | -1.076299% |

The observed-only selected-minus-one mean is **-0.141339 percentage points**, and selected-minus-zero is **-0.334037 percentage points**. These are one-market-day unadjusted source-price differences, not brokerage-net portfolio P&L.

## No guess: algebraic reversal hurdles for the two unknown stocks

For an original fixed 100-name equally weighted study, a *counterfactual* arm mean, if the missing stock's unknown one-day return were \(u\%\), would be:

    full_mean_pct = (sum_of_99_observed_percent_returns + u) / 100

The true full-100 mean remains **unknown**, since neither missing stock has an original validated EQ entry. Do not substitute a different series or ISIN.

To reverse the selected-versus-one-signal sign:

    (unknown_RET​AIL_percent - unknown_MOREPENLAB_percent)
       must exceed approximately 13.992525 percentage points.

To reverse selected-versus-zero (where there is no missing control):

    unknown_RETAIL_percent must exceed approximately +31.993342%.

These are **arithmetic thresholds**, not claims that either return happened or could have happened under an exchange price band. They do not predict tomorrow.

### Explicit stress illustration, not a confidence interval

Allow each unknown one-day price movement hypothetically anywhere from **-20% to +20%**. This interval is arbitrary, *not* a verified NSE circuit band for either issuer and not a statistical interval.

- Within this hypothetical bound the selected-versus-one sign **can flip**, depending on two missing returns.
- Within this same hypothetical bound the selected-versus-zero mean remains negative, but the actual unbounded missing return is still unknown.
- The program must report **fixed 100-company population, 99/99/100 price coverage, null missing stock returns** and never claim a complete 100-name return series.

The source-derived JSON includes the full sharp interval for each arm and gap and independently recomputes the 99 company sums from the original 300-company retained source. No security changes identity, no source timestamp is backdated, and no prior cohort membership is altered.

## Meaning for the research strategy

The October 15 selected screen did **not** outperform either observed-only source control on its first market day. Equally importantly, one common trading event does not produce 300 independent observations, and cross-section size does not replace independent dates and risk/sector/style control.

HG009 P025's growth balancing was selected after seeing the H1 outcome and cannot rescue that prospective result. H5 includes the same October 15 first trading session and cannot be called independent replication. H5 is still unmatured until the **October 22 NSE close** and receipt of every official required trading-session source.

Separately, P033 authenticated only **142/300** company industry records, and P036's observed complete one-level-industry-plus-liquidity pool supports at most **18 matched triplets (54 companies)**. This is not enough to declare the next 300-company industry-matched alpha study. The missing 158 full-identity industry records, four-tier accounting regime, market size, beta, corporate actions, realistic bid/ask/impact and independent future freezes remain prerequisites.

**Investment consequence:** there is still no statistically or economically validated repeatable NSE alpha, and no selected 2027 winner, buy recommendation, share-price target, guaranteed annual return or capital approval can be derived from P037.

Reproducible artifact: research/hg009/hg009-p037-h1-missingness-bounds-v1.json. Generator: scripts/materialize_hg009_p037.py. Regression: tests/test_hg009_p037_missingness.py. The method explicitly dates its posthoc development October 21.
