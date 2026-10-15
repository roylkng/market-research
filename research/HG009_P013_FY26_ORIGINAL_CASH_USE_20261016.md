# HG009 P013: original NSE FY26 investing and financing cash bridges

**Research date:** October 16, 2026. **Financial period:** FY26 consolidated audited year ended March 31, 2026. **Original byte custody:** P009 NSE issuer iXBRL original HTML, first verified October 14. **Live capital:** prohibited.

## Why a new analysis is necessary

The P008 cash-from-operations-less-PPE proxy does not show what happened to cash spent on financial securities, dividends, leases, borrowed funds and other investing flows. P013 independently replays 17 exact cash-flow statement cells per issuer from the SHA-pinned complete original NSE HTML and requires the statement to reconcile beginning cash to ending cash.

| FY26, ₹ crore | ACUTAAS | ACE | TRAVELFOOD |
|---|---:|---:|---:|
| Operating cash flow | 292.17 | 417.27 | 392.97 |
| PPE cash purchase | -327.98 | -93.26 | -38.53 |
| CFO less PPE, not normalized FCF | -35.81 | 324.01 | 354.44 |
| Full net investing cash | -265.94 | -349.89 | -149.81 |
| Cash after all investing | 26.23 | 67.38 | 243.16 |
| Full net financing cash | +4.10 | -51.91 | -220.74 |
| **Net change in cash** | **+30.33** | **+15.47** | **+22.42** |

Official source links: [ACUTAAS NSE FY26](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_154986_30042026190518_iXBRL_WEB.html), [ACE NSE FY26](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_159432_20052026205221_iXBRL_WEB.html), [TRAVELFOOD NSE FY26](https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_161065_25052026215924_iXBRL_WEB.html).

## Company-specific hypotheses to falsify

**ACUTAAS:** CFO was less than cash PPE spending. The source-reported inventory and trade-receivable cash movements together were approximately -₹106.87 crore, before supplier/payables and remaining working-capital lines. The ₹30.33 crore net FY26 cash increase does not mean the expansion was internally funded or has already produced attractive incremental capital returns. Reconcile productive asset commissioning, customers, margins and financing.

**ACE:** The original NSE source reports financial-security purchases ₹831.07 crore and sale proceeds ₹508.32 crore, a ₹322.75 crore net investment placement. Financial investment purchases are not necessarily expenses or permanent losses. Cash after *all* investing was ₹67.38 crore, and financing reduced annual cash by ₹51.91 crore. Reported cash/investments require realizability, restrictions and parent attribution checks, not automatic addition to valuation.

**TRAVELFOOD:** The original source reports lease principal paid ₹123.70 crore, financing interest paid ₹30.06 crore and dividends paid ₹60.05 crore. The investing section has ₹144.50 crore of net equity/debt-instrument purchases. Net financing was -₹220.74 crore and annual cash rose by ₹22.42 crore. Airport concession renewal, leases, minority interests and access to financial securities remain valuation gates.

## Scientific limits and reproducibility

P013 retains the complete P009 original issuer archive paths and first verified retrieval UTC with original hashes. It replay-checks original consolidated statement labels, amounts, issuer symbols and financial periods. Tests reject altered, missing or duplicated source rows, incorrect cash arithmetic and accidentally using the operating section's zero interest instead of paid financing interest.

**None** of CFO less PPE, cash after all investing, or cash after financing is a normalized owner cash flow or predicted annual stock return. Future valuations need documented maintenance-versus-expansion capex, repeatable working capital, current fully diluted parent shares, financial-asset restrictions, minority claims, capacity economics and execution costs. No share price target or investment recommendation is introduced.

Canonical signed artifact: research/hg009/hg009-p013-fy26-cash-use-bridge-v1.json. Reproduce with scripts/materialize_hg009_p013.py --check and tests/test_hg009_p013_cash_bridge.py.
