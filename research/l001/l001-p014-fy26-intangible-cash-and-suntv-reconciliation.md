# L001 P014 | Intangible acquisition cash: the missing leg of FY26 reinvestment

**Research date:** 2026-10-18. **Purpose:** falsify false-positive high-cash-yield candidates in the existing frozen 100-company HG009 discovery cohort. **Status:** independently replayable original source accounting only, **NOT** owner earnings, prospective alpha, a recommendation, or revision of original HG009 selection.

## Source boundaries

Pinned prior original NSE P004 all-100 archive, GitHub Actions artifact `12111414537`, sealed P004 report SHA `97cd3432e3c779f48ad09c75d42b5c18b431e2f6e297cf10421a31055c92e82d`. The prior replay independently checked 300 exact original company XBRL documents and 400 numerical accounting concepts. This P014 additionally rereads the exact financial-statement INR context `FourD` concept `PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities` from all **100** original FY26 annual source XML files, rejecting any changes to the original complete inventory, issue date, source SHA, context, unit or amount.

The source audit distinguishes:
- **Tagged spending:** a nonzero original XBRL amount for intangible purchases is a real reported cash investing outflow. **17 of 100** companies have a positive amount under this specific concept, and **83 have zero**.
- **Zero specific concept:** neither absence of content acquisitions nor absence of other intangible/capex/investing cash. A company may classify economic reinvestment under another investing or acquisition line. An original zero must **never** be used as proof of zero economic investment.
- **Owner cash:** `CFO − PPE − intangible purchases` is still merely a cash classification proxy. Maintenance versus growth, content creation costs, cash taxes, leasing, interest, minority owner claims, unrelated financial acquisitions, dispositions, time-lag and fully diluted valuation remain unresolved.

## Major falsification: SUNTV

Official issuer source: [Sun TV Network FY26 consolidated annual report](https://www.suntv.in/pdf/Finance/2025/Sun_TV-41st_Annual_Report_25-26.pdf), consolidated cash-flow statement, approximately printed financial page 159.

| FY26 consolidated accounting | ₹Cr |
|---|---:|
| Operating cash flow | 1,801.64 |
| Purchase of PPE | 83.91 |
| Earlier CFO − PPE only (misleading owner-cash proxy) | **+1,717.73** |
| Actual original cash purchase of intangible assets | **2,130.31** |
| CFO minus both accounting purchase categories | **−412.58** |
| FY25 intangible purchase comparative | 354.97 |

The much larger FY26 intangible investing cash purchase makes the earlier **~6.9% CFO-minus-PPE / Oct15 basic market-cap screening ratio invalid as an owner-cash proxy**. Including this single expenditure category changes that mechanical cash calculation by **₹2,130.31 crore**, which reverses its sign.

### Sunrisers Leeds franchise rights: do not misclassify a purchase as recurring maintenance

The same issuer annual report, Note 46(C) on business combinations / asset acquisition, describes its acquired 100% Sunrisers Leeds investment during FY26 for **£100.5 million (~₹1,184.99 crore)**. The note calls the transaction an **asset acquisition of franchise rights**, rather than recurring operating spending.

However, the annual-report note and cash-flow investing line are not by themselves an *exact transaction-to-cash-line reconciliation*. In particular, purchase consideration, recognized franchise-right intangible amount, initial cash flows and entity/consolidation mechanics must match before subtracting ₹1,184.99 crore from this cash-flow concept as an actual adjustment.

**Conditional-only stress, not a verified adjustment:** *if* the entire ₹1,184.99cr was actually paid within the FY26 ₹2,130.31cr original intangible-purchase outflow and represented nonrecurring growth investment, the remainder would be **₹945.32cr**, and FY26 CFO less PPE less that conditional remainder would be **₹772.41cr**. This is neither verified normalized FCF nor parent-distributable cash. Repeating FY25 spend as a steady-state maintenance proxy is likewise unsupported.

Sun TV's revenue franchises include television, digital rights, film rights and sports franchise assets with economically distinct useful lives. A simple industrial maintenance-capex multiplier cannot substitute for asset rights, amortization, recurring sports and content investments, minority claims or investment liquidity.

## Other original source observations

The preliminary exact XBRL scan found positive intangible purchases for **17** issuers:
`SUNTV, BAJFINANCE, HINDCOPPER, DEEPAKNTR, SATIN, NTPCGREEN, UNIMECH, WSTCSTPAPR, OLAELEC, TRAVELFOOD, BAJAJCON, BALRAMCHIN, ADVENZYMES, GAEL, SARLAPOLY, HSCL, PIXTRANS`. This is **source classification and diligence triage**, not a return ranking. BAJFINANCE and SATIN use specialist NBFC accounting. OIL and other zero-tag companies may have enormous non-PPE economic investing outflows that require different original concepts.

Top direct source leg examples (₹Cr):
- SUNTV **2,130.31** intangible purchase
- BAJFINANCE **401.07**, NBFC specialist treatment required
- HINDCOPPER **329.04**
- DEEPAKNTR **13.72**

No other 83 issuers should be classified as `INTANGIBLE_INVESTMENT_ABSENT` or assigned zeros in a generalized economic owner's cash calculation merely because this exact XBRL concept reports zero.

## Code, test and execution contract

- `src/marketlab/l001_p014_intangible_cash.py`: exact XBRL `FourD`, INR raw figure from 100 original hash-verified annual FY26 documents, with complete symbol+ISIN, fiscal-period and release-time acceptance, preserved P004 source hash, and new cash-purchases proxy clearly marked non-owner cash.
- `scripts/materialize_l001_p014_intangibles.py`: deterministically regenerate 100-row source report from sealed P004 ZIP and nested 300-original XML archive.
- `tests/test_l001_p014_intangible_cash.py`: adversarial test cases for context errors, wrong unit, missing/duplicate/nonfinite facts, incorrect immutable original panel, exact UTC cutoff and Sun TV arithmetic.
- `.github/workflows/l001-p014-original-intangibles.yml`: independent GitHub Actions original source replay (not a simulation) and 90-day artifact retention. Merge only with full repo CI and all-100 replay green.

## Next consequential research gate

Split Sun TV's actual FY26 intangible purchase cash line by archived original note, rights type (movie/TV/OTT/sports franchise), useful life, sustaining versus expansion/revaluation cash, and holding-company financing/investments. Require audited bank/payment evidence or appropriately source-linked note schedule before claiming the `₹772.41cr` conditional number as even a provisional normalized financial measure.

Across 100 companies, model **economic maintenance of all productive assets** for industrial versus media/digital versus banking versus shipping businesses. Explicitly measure historical dilution and attributable claims before price-value comparisons. Then preregister a fresh after-cost 252/504/756-session research cohort, and evaluate only future realized total returns.

**Capital-eligible = false. Expected returns = null. HG009 frozen arms and return observations unchanged.**
