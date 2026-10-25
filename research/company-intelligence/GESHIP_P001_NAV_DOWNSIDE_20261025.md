# GESHIP P001: issuer-sourced NAV discount and prospective-investment rejection gate

Research frozen for this **post-hoc diligence** snapshot: 2026-10-25. This is **not** an H002/H003/HG009 investment alpha signal, not a prediction, not a trade instruction, and not a cash-authorized investment.

## Original source audit
- **Issuer original investor deck**, signed company BSE/NSE covering letter, Aug 4 2026, slide 4 (PDF page 5) and slides 5–8: https://greatship.com/upload/announcements/Q1FY27_Updates_Presentation.pdf_(1).pdf
- **June 30 consolidated asset NAV**: issuer headline ₹1,886/share; its detailed consolidated scenario range **₹1,862–1,911/share**. Standalone NAV is *different* at ₹1,512/share. Never substitute standalone for consolidated.
- **Company original methodology**, page 45 (PDF zero-index page 44): book fleet block replaced by end-quarter values, **average of at least two international shipping broker opinions per ship**. This is better supported than an arbitrary management multiple, but broker inputs, individual vessel marks and realization costs are **not** independently in our source archive.
- **Reported consolidated net cash** (negative net debt) ₹8,056 crore June 30, gross debt ₹799 crore. **Normalized**, after swaps/NCDs etc, net cash ₹7,726 crore: a separate sensitivity not silently interchangeable with the reported amount.
- **NSE original issuer Q1 XBRL** (standalone report, 03-Aug, INR lakh) reports paid up capital ₹14,277 lakh, FV ₹10. Source: https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_181838_03082026184049_iXBRL_WEB.html . Implies 14.277 crore shares for the *June balance sheet*. This is not October diluted outstanding capital.
- **Oct 23 NSE close** ₹1,496.60 (exchange date verified independently by https://in.investing.com/equities/great-eastern-shipping-historical-data and https://dhan.co/stocks/great-eastern-shipping-company-ltd-share-price/). October 25 is a Sunday, so this is the latest prior observed regular-session close; not a live tradable quote.
- **Company original Oct 23 buyback filing** https://greatship.com/upload/investors/buyback_2026/droct23.pdf: 189,800 bought that day average ₹1,499.9841; **3,651,960 acquired cumulatively**. All are not necessarily extinguished, and all purchase cash debits and transaction costs not independently reconciled as of October 23.
- **Company original Oct 23 acquisition filing** https://greatship.com/upload/press_releases/image/GE_Shipping_contracts_to_buy_a_secondhand_Very_Large_Gas_Carrier.pdf: new 2015-built 82k cbm VLGC to be internally financed and delivered Q3 FY27, 2 secondhand Kamsarmax and a newbuild Suezmax committed. Transaction prices unknown. Company reports 40 current owned vessels at 3.24mn DWT and near-full utilization.

## Disclosed cash and *conditional* valuation algebra
The headline *reported* NAV discount at dated price is `1 - 1496.6/1886 = 20.65%`. Its possible gross price appreciation to June NAV without adjustments is 26.02%, **not** a validated expected return or after-cost margin of safety.

At June capital of **14.277 crore shares**, reported June net cash of ₹8,056cr works out to ₹564.26/share. The **algebraic residual** to June consolidated NAV is ₹1,321.74/share. It includes the issuer's appraised fleet and all other net claims, and **is not just the fleet**. Ex-dividend assumption is ₹14.40/share from the August declared Q1 interim dividend.

Static scenario function (price assumptions in INR per share; no probability, horizon or return distribution):

```text
NAV_stressed = (8056/14.277) * (1 - net_cash_haircut)
             + (1886 - 8056/14.277) * (1 - residual_haircut)
             - 14.40
illustrative_price = NAV_stressed * assumed_market_to_NAV_multiple
relative_price_change = illustrative_price/1496.60 - 1
```

| Case | Cash haircut | Residual haircut | Market / stressed NAV | Hypothetical share price | vs Oct 23 close |
|---|---:|---:|---:|---:|---:|
| June headline NAV parity ex-dividend | 0% | 0% | 1.00 | ₹1,871.60 | +25.06% |
| Defensive repricing | 5% | 15% | 0.85 | ₹1,398.36 | −6.56% |
| Adverse shipping cycle | 10% | 30% | 0.75 | ₹1,063.99 | −28.91% |
| Favourable asset repricing | 0% | −10% | 0.95 | ₹1,903.58 | +27.19% |

The **entire quoted discount disappears** if residual NAV is written down about **28.37%**, cash unchanged, and market price converges to stressed NAV with only the Q1 dividend removed. Further persistent shipping-sector NAV discounts can destroy apparent upside even without such a large asset markdown. **These haircuts and market ratios are user-research stress assumptions, not calibrated industry base rates**.

A disciplined **research watch threshold** (NOT a buy order) is **₹1,233.84** *under the explicit 15% residual markdown, 5% cash haircut and 25% additional discount to stressed NAV assumptions*. This number becomes obsolete if current fleet values, liabilities, fleet purchase cash, offshore claims or denominator materially change. With the issuer's *normalized* net cash of ₹7,726cr instead of the reported ₹8,056cr, the same conservative rule shifts downward by roughly ₹16.5/share **if all else is held constant**. No contemporary fair-value band or precise entry order is approved by this.

## Why the apparent cheap trailing P/E can fail
- The issuer's Q1 FY27 original presentation shows reported consolidated net income **₹1,309cr versus ₹505cr Q1 FY26**, and FY26 ₹2,943cr. These are **not normalized cycle earnings**. Q1 Suezmax time-charter equivalent benchmark spiked to ~$143,199/day versus ~$44,627 one year earlier, which the company connects to the West Asian conflict, ton-mile rerouting and freight dislocations.
- The Q1 deck separately reports ~₹125cr profit on sale of ships/assets. Strip out gains and separate transport TCE from cyclical market earnings before using P/E or cash-yield valuation.
- June presentation notes significant crude/product/LPG shipping orderbook, potential oversupply when new ships are delivered. Fleet value marks can reverse well before cash flow.
- Original FY26 cash numbers in repository P017 show high vessel purchase cash. Operating cash minus gross PPE purchase is not owner free cash: ship acquisitions, sales, periodic drydock, spares, environmental retrofits and replacement maintenance are economically different.
- October buyback cash and contracted multi-vessel purchases require a fresh enterprise/parent bridge; don't copy June net cash into October unchanged.
- Offshore subsidiary ownership, separate vessel-level debt/finance leases, swaps/FX, end-of-life scrap prices, taxes on realization and concentrated charter counterparties must be audited.

## Falsification, monitoring and decision
**Current result: HIGH_PRIORITY_WATCH_WITH_QUANTIFIED_NAV_HURDLE; NOT BUY.** This is a more concrete, source-specified asset-evaluation problem than the Zuari holding-company issue, but not a defensible value of the equity as of October 25.

A future investment decision requires an independently original-byte-archived issuer deck and P040 receipts (this markdown is a publicly verifiable issuer disclosure, not canonical repo raw custody), refreshed Sep 2026 audited/reviewed fleet/accounting/leases, *broker-by-broker* fleet estimates, buyback extinguished share count and actual cash deployed, disclosed VLGC/Kamsarmax/Suezmax consideration and timing, offshore attributable NAV, current genuine bid/ask, taxes and executed fee model, a freight-cycle trough cash model, and a bear/base/bull *parent* valuation with independently supportable scenario frequencies. Preserve no live capital while these are missing.

The sensitivity is deterministic and testable in `scripts/geship_p001_nav_stress.py`, with original input file and tamper tests. It does not backfill 2026-10-15 alpha results.
