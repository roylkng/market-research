# OPEN006 | Century Enka: Price-to-book discount and ROE hurdle

**26 October 2026. Research only. NO BUY, NO price target, no live capital.** Century Enka (NSE CENTENKA, ISIN INE485A01015) was independently identified *after* the historical HG009 original cohort. It cannot be backfilled as an October 15 prospective hit.

## Original signed company evidence

- [Century Enka 21 May 2026 Q4/FY26 signed NSE presentation](https://nsearchives.nseindia.com/corporate/CENTURYENKA_21052026231156_Presentation_SE_signed.pdf), PDF p. 8 and 11 (zero-index p. 8,11): **consolidated** March 2026 equity ₹1,495.9 crore (INR 14,959 million); FY26 attributable/consolidated PAT ₹100.8cr (1,008 million), FY25 ₹66.5cr, FY24 ₹42.8cr; March FY25 equity ₹1,417.6cr, March FY24 ₹1,364.4cr. FY26 revenue ₹1,705.4cr vs FY25 ₹2,001.7cr (−14.8%), despite EBITDA margin expansion 5.73%→8.67%. FY26 EPS ₹46.15.
- Original prior FY25 [NSE annual shareholder distribution](https://nsearchives.nseindia.com/corporate/CENTURYENKA_18072025184803_Notice_Annual_Report_of_AGM_signed1.pdf) shows **21,850,589** ordinary shares. FY26 director report says capital remained ₹21.85 crore and **no new securities issued during FY26**, but fully diluted *October 2026* denominator has not independently been confirmed. Source director report: https://www.goodreturns.in/company/century-enka/director-report.html
- [Century Enka NSE October 23 historical close](https://stockanalysis.com/quote/nse/CENTENKA/history/) **₹505.80** for 37,553 shares. Implied indicative share market value **₹1,105.20cr** at prior historical share count, no executable bid/ask depth assumed.
- March FY26 balance sheet from original signed deck page 11: **₹348.4cr current investments**, ₹6.7cr cash, ₹4.0cr other bank balances, sum **₹359.1cr** *gross cash-like*. Noncurrent investments ₹140.3cr deliberately EXCLUDED. Borrowings ₹19.9cr; lease/other liabilities, taxes, restricted deposits and associates need note-by-note examination. These assets are NOT automatically excess parent cash distributable.
- [CRISIL A+/Stable 25 June 2026 source](https://www.crisil.com/mnt/winshare/Ratings/RatingList/RatingDocs/CenturyEnkaLimited_June%2025_%202026_RR_398916.html) independently confirms strong liquidity and low debt, but notes FY27 planned capex about **₹120cr**, versus FY26 operating cash about ₹125cr, annual future cash accrual forecast **₹130–170cr** (rating agency estimates, not audited realised FY27 cash). Low-priced China nylon imports, radialization shift, caprolactam price volatility and new PTCF ramp risk are structural.
- Signed original issuer FY26 presentation PDF page 6 states March 2026 raw-material input-cost rise was partially monetized using older cheaper inventory and higher stock valuation. DGTR favorable anti-dumping *recommendation* is NOT a final Ministry of Finance enacted duty. No proven Q2 FY27 cash or normalized FY27 return on growth capex is claimed. Board Q2 FY27 results scheduled Oct 27, 2026.

## The falsification

Headline price/book looks low:

| Property | FY26 source + Oct23 reference |
|---|---:|
| Equity market cap at 2.1850589cr March25 shares × ₹505.80 | **₹1,105.20cr** |
| March26 consolidated closing book | **₹1,495.90cr** |
| Price/closing book | **0.7388×** |
| Apparent discount to accounting book | **26.12%** |
| FY24 closing-book return (PAT/book) | **3.14%** |
| FY25 closing-book return | **4.69%** |
| FY26 closing-book return | **6.74%** |
| Simple three-year mean, closing-book return | **4.86%** |
| FY26 source earnings yield at Oct23 historical price | **9.12%** |

Below-book equity valuation **can be economically justified** if the company's assets systematically earn less than shareholders' required returns. The following is a **no-growth all-earnings-distributed algebraic identity**, not a DCF or price target. Under that deliberately restrictive model `price/book = sustainable ROE / shareholder required return`.

| Hypothetical required nominal equity return | Sustainable ROE that supports observed 0.7388× book | Earnings-capitalization identity per prior ordinary share | Versus observed ₹505.80 |
|---|---:|---:|---:|
| 10% | **7.39%** | ₹461.31 | −8.8% |
| 12% | **8.87%** | ₹384.43 | −24.0% |
| 15% | **11.08%** | ₹307.54 | −39.2% |

These price identities **must not** be described as intrinsic values because the company *does not distribute all earnings and reinvests capital*. Book accounting, cost of capital, maintenance capex, inflation, forecast dividends, terminal growth and dilution all matter. Their value is to show that even a supposedly “26%-below-book bargain” still needs a durable ROE improvement, not merely an equity multiple rerating.

CRISIL describes **~₹120cr** planned FY27 capex, almost **96%** of its approximate ₹125cr FY26 operating cash. An intentionally simplified same-cash FY27 stress leaves only ₹5cr before dividends/other financial uses. This is **not a FY27 cash-flow forecast** and does not itself mean expansion is bad. Capital investment would be economically attractive only if its independently supported incremental after-tax returns compensate for risk and the time-to-ramp.

## Decision: **WATCH_ONLY_NO_SUPPORTED_MARGIN_OF_SAFETY**

Do not promote on low P/B alone, revenue is down 14.8% YoY even as margins improved, and capex plus structural nylon competition risk limit near-term distributable cash. For admission:
1. Obtain October 27 Q2 original standalone AND consolidated cash and profit, distinguish Q4 FY26 low-cost inventory uplift from recurring margin and real tyre-yarn volumes.
2. Source project-level PTCF/renewable capex completed capital, capacity, end-market orders, incremental segment cash returns and replacement cash.
3. Independently archive original documents/actual observation UTC + byte SHA, verify current diluted shares, contingent tax/lease/restricted assets, issuer's equity return normalized through cyclicality.
4. Compare conservative **parent** FCFE against dated actual executable entry price and realistic position size. Market volume Oct 23 was only ~37.5K shares (~₹1.9cr turnover), not an orderbook depth guarantee.
5. Continue open-market discovery without restricting to CENTENKA, BLS, Mastek, Crizac or IndiaMART. Keep original historical HG009 data unchanged.

Deterministic arithmetic/negative tests: `scripts/open006_centenka_roe_hurdle.py` and `tests/test_open006_centenka_roe_hurdle.py`. This finding is a concrete **potential false positive** not a stock recommendation.
