# OPEN011 — October 27 FY27 Q2 earnings falsification, reviewed October 29

**Scope:** independent, post-hoc NSE investment diligence on **ACUTAAS, INDIAMART, CENTENKA**. Results were first published Oct 27, and Century Enka's investor explanation was published Oct 28. **NOT pre-15-Oct HG009 features, NOT prospective H002/H003 evidence or an OOS alpha win.** No source-independent valuation, probability model, official Oct29 auction price, or buy authorization.

All computations use the checked source inputs in `OPEN011_Q2FY27_EVIDENCE_INPUT_20261029.json` and reproducible deterministic CLI `scripts/open011_q2fy27_cash_valuation_audit.py`, with fail-closed tests for ISIN, source dates, accounting units, minority, unverified first-seen custody, and capital. Quote values at **29-Oct ~15:29 IST** are delayed vendor snapshots, **not verified official NSE close/executable bid/ask**; IndiaMART vendor values disagree. Later October 27 company filings cannot be used in the original sealed HG009 Oct15 experiment.

## ACUTAAS (INE00FF01025) — business growth does NOT equal valuation upside

Original signed NSE company press filing (27-Oct, issuer name legacy AMIORG):
https://nsearchives.nseindia.com/corporate/AMIORG_27102026125648_PressrealeaseSigned.pdf

Issuer consolidated interim filing reproduced from a signed company copy:
https://cdn.financialreports.eu/financialreports/media/filings/59015/2026/RNS/59015_rns_2026-10-27_038afa6b-5271-4686-8eba-06b5ed27f3c2.pdf

Relevant original PDF visual review: consolidated H1 cash table PDF **zero-index page 9**; capital investment and subsidiary notes **page 10**. Cash statement figures in **INR lakh** divided by 100 for crore, while Q2 press figures are **INR million** divided by 10 for crore. No unit substitution.

| Consolidated H1 cash (₹ crore) | FY26 | FY27 |
|---|---:|---:|
| Cash from operations after tax | 136.5049 | **215.9190** |
| Gross PPE/CWIP/intangible cash payments | 141.1538 | **123.9204** |
| Simple cash after these investments | **−4.6489** | **+91.9986** |

This represents a genuine **58.18% YoY operating cash increase** and an improvement in investment cash conversion. It is **NOT** sustainable parent FCFE: higher cash may reflect working capital, project capex, foreign subsidiary claims and minority cash. Inventory adjustment in cash bridge **−₹48.9574cr** this half, requiring follow-up on utilization/aging rather than assuming all EPS growth is cash.

Q2 issuer-reported revenue: ₹436.9cr vs ₹306.2cr prior Q2 (**+42.68%**), EBITDA ₹176cr vs ₹95.3cr (**+84.68%**). Consolidated H1 PAT **₹198.1352cr** splits into **₹199.4293cr parent PAT** plus **−₹1.2941cr noncontrolling loss**; minority profit need not be positive. Do not confuse this with parent distributable cash.

**Korea exposure:** ~₹200cr invested in **75%-owned Indichem**, still **trial runs** as of Sep 30. The October 17 10,000-share Enchem legal transfer was *existing owned stepdown to parent*, not a sizeable independent acquisition. Industrial future earnings cannot be 100% allocated to ACUTAAS shareholders.

**Cost of the growth:** At delayed ~₹3,940 Oct29 provider quote, original reported paid-up share capital ₹4,093.56 lakh / ₹5 FV = approximately **81,871,200 shares**, implied equity value **₹32,257.2528cr**. FY27 H1 diluted EPS ₹24.28 (twice annualized purely as sensitivity ₹48.56), quoted price is **81.14× that simple annualization**. External trailing 12-month provider P/E was roughly 74×, a different period/method and not directly interchangeable.

A transparent **reverse-expectations thought experiment**: ignore dividends, fees, dilution and future cash distributions; assume a terminal P/E of **30×** at year 10 and require a hypothetical **12% annual nominal gross shareholder return** from ₹3,940. Terminal EPS must reach **~₹407.90**, requiring **~23.72% annual EPS compound growth** from the annualized current H1 EPS proxy ₹48.56. This is not a price prediction or calibrated probability; it shows why even excellent company execution may not deliver exceptional shareholder returns at this observed valuation. A 30× terminal multiple, sustained 12% shareholder discount requirement and current half-year annualization are unverified **stress assumptions**. Include current Korean commercialization and maintenance reinvestment before future true scenario value.

**Decision: STRONG_OPERATING_COMPANY / VALUATION_GATE_FAILED / NO BUY.**

## INDIAMART (INE933S01016) — falling paying-supplier economics despite group liquidity

Original 27-Oct issuer-signed Q2 earnings presentation reproduced from signed attachment:
https://cdn.financialreports.eu/financialreports/media/filings/62605/2026/RNS/62605_rns_2026-10-27_4db594d7-acae-4533-b4f5-5ccaae557ebb.pdf
Key table **PDF zero-index page 3** was visually checked. The Q2 company press includes **rounded** paying-subscriber labels; independently indexed Q2 analyst call text https://stockanalysis.com/quote/nse/INDIAMART/transcripts/711039-q2-26-27/ reports exact sequential supplier contraction **−615**. This exact change MUST NOT be calculated from 217,000 minus 218,000, two rounded numbers (which would misleadingly give −1000).

| Management reporting, ₹ crore | Q1 FY27 | Q2 FY27 |
|---|---:|---:|
| Company-reported operating cash | 163 | **135** |
| Consolidated marked cash and investments | 3,553 | **3,234** |
| Standalone parent marked cash and investments | 3,316 | **2,970** |
| Deferred revenue | 2,014 | **2,029** |
| Paying suppliers, rounded | 218,000 | **217,000** |

Q2 sales **₹429cr vs ₹391cr year ago (+9.72%)**, EBITDA ₹159cr and reported PAT ₹91cr. Operating cash declined **17.18% QoQ**; aggregate marked financial assets declined **₹319cr QoQ**. That does **not** prove operating cash burn or impairment: dividends, investment purchases, taxes, market moves and corporate uses must be reconciled before causal interpretation.

The **exact audited H1 FY27 operating cash total and latest fully diluted shares are not admitted**, because only rounded quarter company disclosures were verified here. Do not invent an audited ₹298cr consolidated H1 CFO from ₹163cr + ₹135cr rounded press numbers. The ₹2029cr deferred service obligations are not all refunds; they must be matched to future fulfillment cost. FY26 original consolidated after-tax CFO ~₹694.2cr included **₹287.6cr contract liability operating inflow**, and original parent CFO ~₹668.5cr (OPEN005). Current quarter supplier **−615** while inquiry volumes also weaken does not justify assuming high recurring customer acquisition economics. Company disclosed ~10% ARPU growth on its call, but retention vs pricing power must be separated.

At October 29 delayed price vendor ₹1,534.60, a second provider reported ~₹1,559.70. **Neither is independently sourced official NSE closing auction.** No target price derived from either. Most visible parent investments are not necessarily free distributable cash; the new finance subsidiary has not been proven to own a material customer credit book.

**Decision: FOLLOW_SUBSCRIBER_RETENTION / NO BUY**, not automatically a better value than BLS or Just Dial merely because it owns treasury assets.

## CENTURY ENKA (INE485A01015) — low P/B was masking margin uncertainty

Company Oct 27 Q2 signed financial/result reproduction:
https://bazaarwatch.com/announcement/245485/century-enka-ltd-unaudited-financial-results-for-the-quarter-and-half-year-ended-30th-september-2026

Issuer's 28-Oct investor presentation and explanation:
https://bazaarwatch.com/announcement/249851/century-enka-ltd-earnings-conference-call-presentation-q2-h1-fy27-attached

| Consolidated Q2 versus Q1 FY27 | Q1 | Q2 |
|---|---:|---:|
| Revenue (₹ crore) | 554.29 | **558.23** |
| EBITDA (₹ crore) | 85.70 | **32.80** |
| EBITDA margin | 15.46% | **5.88%** |
| Net PAT (₹ crore) | 61.70 | **18.49** |

**Profit fell 70.03% QoQ even as sales rose**. Management explained that Q1 benefitted from low-cost opening inventory as input prices changed. Q2's EBITDA margin **5.88%** was below the issuer-indicated normal **7–10%** range. This source contradicts the tempting idea of extrapolating its Q1 reported margin into durable double-digit ROE.

At the delayed October 29 price **₹468** with previously reported ~2.185 crore shares, market cap estimate ~₹1,022.58cr vs reported Sep consolidated book equity **₹1,552.9cr** → **0.6585× P/B**. But the estimate is based on an earlier share denominator and needs an exact latest diluted register. Earning multiple is extremely sensitive to period choice: at annualized Q2 PAT (18.49×4) **13.83×**; at annualized H1 PAT ((61.70+18.49)×2) **6.38×**. **Neither is a normalized PE or intrinsically justified discount.** The same evidence explains why price/book appears low despite weak cyclical earning power. FY27 planned ₹120cr capex against FY26 CFO ~₹125cr remains a cash-reinvestment drag; **current H1 cashflow was not independently verified**, so null.

**Decision: SOURCE-BACKED_INVENTORY_CYCLE_HOLD / NO BUY.** Need caprolactam cost pass-through, nylon tyre-cord sales contracts, final legal anti-dumping decision, actual spend/returns and recurring 7–10% EBITDA before valuation.

## Cross-case decision and next trigger

These three reports are a **falsification of superficial ranking**, not discovery of confirmed stock alpha. ACUTAAS has outstanding earnings growth but needs exceptional *future* growth to justify a high entry multiple; INDIAMART offers parent balance-sheet liquidity but persistent paying-supplier churn and declining collections; CENTENKA is asset-rich and modestly rated but earnings turned lower with reversal of an input-cost advantage. **Zero portfolio-ready companies.**

**Next source checks:** on **Friday 30-Oct** Crizac releases Q2/H1 FY27 UK-destination exposed revenue/cash, while the MEA Canada BLS consular tender was scheduled **Monday 2-Nov**, with no independently verified award. The original H002/H003/HG009 prospective experiment remains frozen, with source release dates and delayed provider price caveats retained.

Inputs and negative/adversarial tests: `OPEN011_Q2FY27_EVIDENCE_INPUT_20261029.json`, `scripts/open011_q2fy27_cash_valuation_audit.py`, `tests/test_open011_q2fy27_cash_valuation_audit.py`. No data falsely declared original raw SHA/UTC archived or no-legacy-system investment approval.
