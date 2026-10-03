# Entry timing decision contract v1

Status: PROPOSED REPORTING AND EXPERIMENT SPECIFICATION.
Created: 2026-09-10.
Live capital allowed: false.
Implementation status: documentation only. This document does not implement, train, validate or activate a timing model.

## Objective

Select both promising businesses and acceptable entry conditions. A positive business thesis must not be presented as an executable buy-now recommendation. The relevant question is not merely whether a stock eventually rises, but whether entering now has better net expected outcomes than waiting or holding the benchmark over the same evaluation period.

The immediate motivation is the user's challenge to the Transrail Lighting and Genus Power shortlist. These two names are observed development cases, not untouched validation evidence.

## Existing work is preserved

H004-R001 already contains a Stage 2 price/volume/relative-strength trigger, next-session execution assumptions and maximum-adverse-excursion reporting. This contract does not replace or modify H004, H018, H019, any frozen thresholds, or any previously reported failure. Its purpose is to prevent a narrative shortlist from bypassing execution and validation gates.

Reference inspected: registry/h004_signal_rule.yaml on research/h019-fundamental-inflection-source-audit-20260909, blob 9aae5b845ed421fdef921ea79f9d60cd34c3044d.

No successful backtest or calibrated probability is established by this document. An unvalidated timing overlay cannot rehabilitate a rejected stock-selection hypothesis.

## External-method review, 2026-09-10

This section records methodological ideas observed in current and standard public research. It does not treat any external recommendation as evidence that a stock will rise.

### Fundamental analysts

CFA Institute's current equity-valuation material describes the fundamental process as understanding the business, forecasting company performance, selecting a valuation model, converting forecasts to valuation, then making a recommendation. Fundamental analysis uses macroeconomic, industry and company information. Discounted-cash-flow and relative-multiple methods are standard approaches.

Sources:
- https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/equity-valuation-concepts-basic-tools
- https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/company-analysis-forecasting
- https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/free-cash-flow-valuation
- https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/market-based-valuation-price-and-enterprise-value-multiples

Implication for MarketLab: forecast the operating drivers, cash conversion and valuation independently of the entry-timing signal. A technically strong stock with implausible valuation must not become a long-horizon selection solely because price is rising.

### Current Indian technical recommendations

Public broker/expert columns reviewed on September 10 repeatedly use:
- breakouts from consolidation or resistance,
- higher highs and higher lows,
- price relative to moving averages,
- RSI and MACD momentum,
- volume expansion,
- broad/sector-relative trend,
- explicit entry zone, stop and target.

Examples:
- https://www.moneycontrol.com/news/business/markets/trade-spotlight-how-should-you-trade-urban-company-inox-wind-cg-power-apollo-hospitals-enterprise-adani-ports-and-others-on-september-10-14026632.html
- https://www.moneycontrol.com/news/business/markets/trade-spotlight-how-should-you-trade-marico-narayana-hrudayalaya-granules-laurus-labs-caplin-point-tata-technologies-and-others-on-september-9-14025670.html
- https://www.moneycontrol.com/news/business/markets/trade-spotlight-how-should-you-trade-ifci-balaji-amines-acme-solar-holdings-indraprastha-gas-tata-communications-and-others-on-september-7-14023879.html
- https://www.livemint.com/market/stock-market-news/breakout-stocks-to-buy-or-sell-sumeet-bagadia-recommends-five-shares-to-buy-today-9-september-2026-11788915118182.html

Implication for MarketLab: these ideas are useful as candidate observable features, but several are transformations of the same price series and must not be counted as independent evidence without testing. Named chart patterns and Fibonacci/time-cycle labels should not receive privileged status unless they beat simpler price/volume baselines out of sample.

### Quantitative evidence

Public academic summaries support testing momentum, volatility, volume and regime features rather than assuming a single chart indicator is sufficient. The equity momentum literature documents predictive persistence over multi-month horizons, while a broad factor-timing study found past factor returns and volatility among the strongest individual timing predictors. A separate volatility study found combinations of returns and volume can improve forecasts, though statistical forecast accuracy does not automatically imply trading profitability.

Sources:
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3217368
- https://papers.ssrn.com/sol3/Delivery.cfm/4376898.pdf?abstractid=4376898&mirid=1&type=2
- https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2369925_code148992.pdf?abstractid=1438041

Implication for MarketLab: the first timing benchmark should be deliberately simple, for example price trend, relative momentum and volatility. RSI, MACD, Bollinger Bands and named candlestick patterns should enter only as challenger features. Complexity must demonstrate incremental out-of-sample value.

## Separate outputs, not one blended score

Every company card must show:

1. Identity: exchange, symbol, ISIN where verified and corporate-action basis.
2. Evidence cutoff: latest completed market session, filing publication timestamps and source retrieval dates. Do not use intraday future information relative to the decision cutoff.
3. Business thesis: horizon, demand drivers, capacity, execution, margins, cash conversion, debt and valuation assumptions.
4. Price state: falling trend, candidate base, improving trend, pullback or extended advance. Unknown data is not a neutral trend.
5. Action state: WAIT_FALLING, WAIT_BASE, WAIT_PULLBACK, PAPER_ENTRY_ELIGIBLE, AVOID_THESIS_INVALIDATED or BLOCKED_DATA.
6. Entry condition: exact observable condition, earliest executable time and expiry. Observation levels are not automatic order prices.
7. Invalidation: what price or business evidence cancels the entry thesis. A planned stop is not a guaranteed maximum loss.
8. Exit/review: profit-taking, trailing invalidation and time-based review, specified independently from the long-term investment thesis.
9. Forecast: outcome definition, horizon, calibration status, sample size and uncertainty. Unsupported probability and reversal-date fields must remain null with a reason.
10. Provenance: source URLs, vendor/exchange, original-file hash when actually retained, adjusted-price method and explicit unresolved conflicts.

The output must distinguish a research watchlist from a portfolio and a paper signal from authorization to deploy live capital.

## Local extrema and prediction

A local minimum or maximum requires a specified time window. A price that is the lowest observation in the previous 20 sessions is not known to be the lowest price in the next 20 sessions.

The model may estimate the chance of a reversal or a return distribution. It must not label a future-dependent swing low as if that label was available on the low's date. A pivot requiring k later bars becomes usable only after those k bars have completed. Centered moving averages and retrospectively repainted zigzag extrema are forbidden as contemporaneous features.

The trading objective is an advantageous entry distribution with an explicit failure condition, not perfect bottom/top capture. Waiting for confirmation trades a worse nominal entry price and possible missed V-shaped recovery for less exposure to an unconfirmed decline. Neither trade-off is assumed superior before testing.

## Candidate timing features

Price structure: trailing lows/highs, confirmed higher lows, closes above prior resistance, trailing 20/50/200-session averages and their slopes.

Participation: volume and traded-value ratios against prior sessions, liquidity and spread. Volume does not identify buyer intent or institutional accumulation by itself.

Relative performance: stock versus a frozen broad benchmark and sector benchmark. Several transformations of the same closing-price series are correlated, not independent confirmations.

Risk: ATR or realized volatility, adverse excursion, gap risk, distance to invalidation and remaining upside under explicit scenarios.

Catalysts: publication-dated order conversion, commissioning, execution recovery, margin changes, cash collections, debt changes and forecast revisions. Known news is not automatically a positive surprise.

Regime: broad/sector trend and breadth, interest rates, funding conditions, commodity/input and FX exposures specific to the company.

Missing or conflicting price/volume history blocks automatic entry classification. Indicator snippets from different vendors, exchanges, timestamps or adjustment methods must not be combined into an apparently precise technical signal.

## Feature hierarchy for the first timing experiment

Tier 0, required baselines:
- 20-session and 60-session total return,
- stock minus Nifty 500 return over the same windows,
- stock minus sector return over the same windows,
- realized volatility and maximum drawdown,
- distance from trailing 20/60-session high and low.

Tier 1, interpretable price-state challengers:
- 20/50/200-session moving-average ordering and slope,
- confirmed higher-high/higher-low or lower-high/lower-low state without future leakage,
- range breakout/retest state,
- volume or traded-value ratio versus prior 20 sessions.

Tier 2, common technical indicators:
- RSI,
- MACD,
- Bollinger Band position/width,
- ATR-normalized distance from support/resistance.

Tier 3, exploratory only:
- named candlestick formations,
- Fibonacci retracements/extensions,
- Elliott-wave or time-cycle labels,
- sentiment/news embeddings.

Promotion rule: a higher tier is retained only if it adds stable walk-forward performance after costs over the simpler lower-tier model. Multiple indicators derived from the same underlying prices must be assessed for incremental information rather than voted as independent confirmations.

## Candidate experiment design, not a promoted strategy

Compare four policies on the same point-in-time eligible company pool:

A. Enter at the first eligible next-session executable price after the business signal.
B. Apply one simple preregistered trend filter.
C. Apply a separately preregistered early-reversal/pullback filter.
D. Apply a small multivariate timing model using only Tier 0 and Tier 1 inputs. Tier 2 and Tier 3 features are challenger variants, not defaults.

All policies use the same initial capital, calendar start and terminal evaluation dates, cost treatment, position limits and exit assumptions. Uninvested capital remains in a consistently defined cash instrument. Waiting policies must include signals they never enter and the opportunity cost of missed winners.

Use 20- and 60-session outcomes. Report net return, benchmark excess return, maximum drawdown, maximum adverse excursion, time under water, time to first profitable exit, turnover, skipped events and calendar-time capital utilization. Win rate alone is insufficient.

For a future first-passage probability, specify both return barriers and the deadline, for example an upside of 2R before a downside of 1R within 20 sessions. R is defined from an executable entry and ex-ante stop before evaluating the outcome. This is a label example, not a current forecast or a frozen trading rule. If both barriers occur in one daily bar and sequencing cannot be resolved, record ambiguity and use a conservative sensitivity analysis, never assume the favorable order.

Validation requirements:

- Fit, tune and calibrate chronologically. Purge overlapping forward labels across splits.
- Preserve point-in-time universes, delisted/suspended names, corporate actions and complete traded-price evidence.
- Include fees, taxes on transactions, spread, slippage, circuit limits and missed/gapped entries.
- Test out of sample against both simpler timing policies and the underlying stock-selection policy without an overlay.
- Report calibration curves, Brier score, calibration sample size, base rates and uncertainty before displaying numerical probabilities.
- Log every attempted rule version, including failures. Do not tune on the two illustrative cases below.
- H018/H019 source-integrity blockers remain blockers wherever their data is required.
- Keep all policies paper-only until independent validation and prospective evidence justify promotion.

## Review and exit principles

Use daily completed data for swing-entry review and weekly structure for a multimonth thesis. An intraday candle does not determine a two-year operating forecast.

A breakout failure, loss of the defined higher low, persistent benchmark underperformance or material deterioration in the business can invalidate an entry. A short-term failed entry must not silently become a long-term investment to avoid admitting a loss.

Time-based reviews should test whether the expected catalyst and price response are progressing. They are not predictions that a reversal must happen by a particular date. A fixed percentage take-profit rule and a trailing exit must be tested as different policies rather than selected retrospectively for each winner.

## Development snapshots: 2026-09-09 completed session

These are manually reviewed secondary-source observations, not an exchange-verified OHLCV dataset and not automated model outputs. No September 10 intraday or closing data is used.

### Transrail Lighting, NSE TRANSRAILL

Observed close: INR 424.05 on September 9, 2026.
Reported one-year price return: approximately -46.2%.
Reported 52-week low: INR 416.05.

Sources:
- https://www.kotakneo.com/stocks/transrail-lighting-share-price/
- https://www.etmoney.com/stocks/transrail-lighting-ltd/4970
- https://www.5paisa.com/stocks/transraill-share-price

September 9 vendor snapshots put the stock below their reported 50- and 200-session averages. Exact average levels differ across vendors and may differ by SMA/EMA, timestamp or adjustment basis. No reconciled indicator value is frozen here. INR 416.05 is an observed historical low, not a proven support floor or a recommended buy price.

The latest quarterly summary reports standalone Q1 FY27 revenue of INR 1,700.47 crore, +4.16% YoY, PAT of INR 110.55 crore, +2.25% YoY, and consolidated overseas revenue of INR 604.15 crore, down 44.28% YoY. These distinctions matter more than a generic sector capex runway. Standalone figures must not be mixed with consolidated figures.

Financial source:
- https://www.icicidirect.com/research/equity/rapid-results/transrail-lighting-ltd

Manual action: WAIT_FALLING.
Automated entry state: BLOCKED_DATA, because a complete reconciled current price/volume series and tested classifier have not been established in this review.
Business reassessment: watch execution, overseas delivery, order conversion, collection and margin recovery. This review does not prove which factor caused the historical price decline.
Price reassessment: a base, confirmed higher low and break/hold of actual recent resistance would be evidence to evaluate. No exact bottom date, target or automatic buy threshold is asserted.
Probability of rise in 20/60 sessions: null, not calibrated.

### Genus Power Infrastructures, NSE GENUSPOWER

Observed close: INR 329.00 on September 9, 2026.
One-month price return in the reviewed Kotak snapshot: +7.29%.
One-week price return: -2.13%.

Source:
- https://www.kotakneo.com/stocks/genus-power-infrastructures-share-price/

Manual interpretation: recent volatility and a pullback after a monthly advance, not evidence of the same prolonged decline as Transrail. Full adjusted OHLCV must be reconciled before naming exact support, resistance or a 50/200-session trend classification. One-year return figures differ between vendors and may be affected by corporate-action methodology, so no cross-vendor one-year comparison is used here.

The Q1 FY27 summary reports revenue of INR 1,364.88 crore, +44.83% YoY. Standalone PAT was INR 162.82 crore, while consolidated PAT was INR 196.64 crore. The two bases must not be interchanged when calculating valuation or profit growth.

Financial source:
- https://www.icicidirect.com/research/equity/rapid-results/genus-power-infrastructures-ltd

Manual action: WAIT_PULLBACK_CONFIRMATION, a descriptive subtype of WAIT_PULLBACK.
Automated entry state: BLOCKED_DATA.
Business reassessment: installation execution, working-capital conversion, operating cash flow and earnings quality rather than order-book size alone.
Price reassessment: inspect whether the pullback holds a genuine previously established support zone and then resumes with improving relative performance. A lower nominal price alone is not confirmation.
Probability of rise in 20/60 sessions: null, not calibrated.

## Delivery boundary

This document records the timing requirement and its scientific constraints. It is not a claim that a timing engine has run, the historical experiments have passed, a bottom has been located, or either stock is ready for live capital.
