# L001 P017 | Three falsification cases after the October 19 NSE close

**Cutoff:** October 19, 2026, after the original NSE daily market archive was published and sealed. **Scientific use:** retrospective research, not a pre-October 15 HG009 signal or a price-target recommendation.

## Why the October 19 price matters, and why it is not enough

The original full-market NSE UDiFF source for October 19 was captured after the session closed. Its unadjusted symbol+ISIN close is reliable *as a dated price*, but cannot be treated as an executed investor fill or corporate-action-adjusted total return. All cash, NAV, ownership and financing inputs below are independently labeled with their older dates.

| Issuer | Oct 15 original NSE close | Oct 19 original NSE close | Close-to-close *price-only* movement |
|---|---:|---:|---:|
| GESHIP | ₹1,484.10 | **₹1,519.30** | +2.37% |
| ZUARIIND | ₹267.55 | **₹259.10** | -3.16% |
| DATAMATICS | ₹793.00 | **₹777.75** | -1.92% |

The price movements do not establish that any company became a bargain. The underlying financial evidence must move on the same accounting clock.

## 1. GESHIP: genuine asset-owner actions, but the discount is cycle-sensitive

Original first-party Q1 FY27 presentation as analyzed in the pinned L001 P009 source reports *June 30* consolidated NAV about ₹1,886/share and net cash ₹8,056 crore. Dividing net cash by **rounded historical** basic shares of 14.2767 crore gives approximately ₹564/share of stale net cash, with approximately ₹1,322/share residual fleet/offshore NAV.

The old June 30 issuer NAV was **21.31% above the October 15 share price in discount terms**, shrinking to **19.44% discount** at the October 19 ₹1,519.30 close. A markdown of only approximately **27.74% to the noncash residual NAV** erases the entire apparent October 19 discount if June cash is held fixed. That is a *downside stress*, not a probability forecast, and stale June fleet appraisals may already have changed.

The [issuer's original 2026 buyback register](https://greatship.com/buyback-2026.html) lists **2,901,660 shares purchased** through October 16. Its legally extinguished first September lot is **1,858,941**. Do not assume every purchased share was legally extinguished by the October 19 reference date, or that the buyback maximum ₹1,530 is a share-price floor. Buyback cash spending, outstanding shares, debt and ship asset values require a dated original source bridge.

**Falsification:** independently appraisal-stress older tanker/offshore fleet values at trough/median charter conditions and recompute fully diluted shares after legally effective buybacks, debt, shipping replacement capex and dividend funding. An unadjusted NAV price discount is not a conservative margin of safety.

## 2. ZUARIIND: holding-asset repricing cannot be rolled forward from October 15

The P012 original exchange source repriced the five held listed company stakes from old June marks to October 15 original NSE closes. Its historically held aggregate was **₹3,820.124826 crore** versus June's ₹4,223 crore. Subtracting **March 31** net consolidated borrowings of ₹2,519.4245 crore produces only a *cross-dated hypothetical* ₹1,300.7003 crore residual, compared with about ₹796.80 crore basic capitalization **on October 15**. A further **13.19% asset markdown** erases that simplistic gap.

The Zuari October 19 close declined to ₹259.10, but the original October 19 market packet for the **300 HG009 experiment companies does not contain all five underlying group holdings**. The exact October 19 contemporaneous listed-stake valuation therefore remains **null**. Updating only Zuari's share price while carrying stale October 15 holdings marks is a **false improvement** in valuation.

**Falsification:** same-date source on all five holdings, legal parent/subsidiary ownership after September transfers, Chambal pledged-share cash waterfall, actual remaining Dubai repatriation after August, and current debt/working-capital collateral. Do not subtract pledge face value again if debt is already subtracted.

## 3. DATAMATICS: requires durable owner cash, not an acquisition-cash illusion

October 19 NSE close ₹777.75 multiplied by March 2026 basic shares of 59,106,389 produces an *approximate cross-date* ₹4,597.00 crore capitalization, **not** October 19 verified fully diluted equity value.

FY26 audited original source CFO minus selected PPE was ₹284.42 crore. At an arbitrary 16× owner-cash valuation multiple and no net-cash/dilution adjustment, parity to this old-basic-capitalization requires **₹287.31 crore/year** of real owner cash. A hypothetical +50% gross value change at unchanged 16× requires **₹430.97 crore/year**, or **51.53% more** than the raw FY26 CFO-minus-PPE proxy. None of these equals a cashflow forecast or fair value.

The original audited March 2026 balance sheet contained ₹209.69 crore of acquisition consideration payable. It is not yet independently determined how that amount maps into June net cash/investment KPI, acquisition settlements, restricted investments and minority cash. Incorrectly subtracting it twice or fully ignoring it both distort the equity bridge.

**Falsification:** independently reconcile current acquisition claims, June/September unrestricted net assets, segment recurring cash, and the actual diluted share denominator. A historical reported EBITDA or one-year CFO proxy cannot establish a margin of safety.

## Decision and next step

These three cases are **not buy recommendations**, and the date-differing numbers must not be used as if all assets, debt, capital and quoted prices shared an October 19 valuation instant. GESHIP is a worthwhile *first original-source diligence priority* because a verifiable capital-allocation event and explicit NAV stress provide falsifiable claims. Zuari is potentially more complex and levered. Datamatics owner-earnings remain subject to acquisition-balance restrictions. This ordering concerns **proof acquisition**, not expected stock returns.

The transparent accompanying calculation is source-pinned to the existing original October 15 and October 19 300-company NSE price packets, audited FY26 Datamatics P049 and L001 P009/P012/P016 research. Every resulting field is marked research-only, and normalized owner cash, future expected return, fair value, current dilution and actual fill remain unverified/null.

Canonical research record: research/l001/l001-p017-three-reverse-value-gates-v1.json. Reproduce with python scripts/materialize_l001_p017.py --check and pytest -q tests/test_l001_p017_reverse_falsification.py. No changed original HG009 cohorts or prospective T012 experiments.

## October 20, 2026 external timing verification

NSE's official 2026 equity holiday calendar explicitly lists **Tuesday October 20, 2026** as a Dussehra trading holiday. There is **no October 20 official NSE EQ close** to insert between October 19 and October 21. The October 15 and October 19 original price observations above remain the newest fully pinned source dates used in this report. This publication-day clarification neither changes historical source prices nor retroactively repairs the experiment.

Original exchange calendar: https://www.nseindia.com/resources/exchange-communication-holidays

**External issuer-evidence caution:** Zuari Industries' 2026 annual-report shareholding/security notes identify multiple pledged Chambal Fertilisers, Paradeep and Gillette-related investment claims securing different debts. A listed-stake NAV haircut cannot be interpreted as unencumbered cash realizable by parent common shareholders. Actual pledge release, entity-level debt waterfall, and cross-company ownership still require issuer-controlled original evidence, rather than deducting the pledge's face value a second time. The P017 13.19% haircut remains a purely illustrative break-even sensitivity, not a verified conservative liquidation discount.
