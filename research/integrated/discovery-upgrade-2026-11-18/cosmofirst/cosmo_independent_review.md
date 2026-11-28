# COSMOFIRST independent cash and funding review

Review date: 18 November 2026. Bounded review of the author's current underwriting, not a second market search. Sources were the retained original signed results, annual report and earnings transcript. No author model files were edited.

## Verified cash correction

The signed H1FY27 consolidated cash-flow page was visually inspected at local `q2_cf-8.png`, source PDF page 8. It shows CFO ₹256.42 crore, capex ₹90.40 crore, interest paid ₹74.14 crore, lease principal ₹6.01 crore, and lease interest ₹4.27 crore. Therefore:

**₹256.42 − ₹90.40 − ₹74.14 − ₹6.01 − ₹4.27 = ₹81.60 crore.**

Dividend paid is ₹10.38 crore. Substituting that number for interest would overstate this residual by ₹63.76 crore, producing the erroneous ₹145.36 crore. The original document supports the author's correction of the machine-readable fields. This residual remains before ordinary debt principal and dividends. It must not be called cash actually distributed to owners.

H1 cash also contains large financing movements within working capital: trade payables contributed ₹178.90 crore, other financial liabilities ₹87.14 crore, while inventories and receivables absorbed ₹302.13 crore. The signed refund note reports USD6.97 million received, USD3.31 million provisionally appropriated, comprising USD2.61 million recognized in other income and USD0.70 million credited against inventories. The USD3.31 million is not a separately stated customer-refund liability. The author reserves approximately ₹35 crore against the remaining USD3.66 million, which is a conservative scenario rather than a verified named liability. Removing the accounting income alone does not remove the temporary customer-refund cash benefit. A prospective cash model should reserve that outflow or model its settlement.

## Existing obligations, rather than only new capex

The original FY26 consolidated annual report contains the following facts:

| Item | Original location | ₹ crore at 31 March 2026 |
|---|---|---:|
| Current capital-goods payable | PDF p142, note26 | 30.41 |
| Noncurrent capital-goods payable | PDF p142, note26 | 0 |
| Capital contracts not yet provided, net of advances | PDF p146, note38 | 57.62 |
| Uncalled investment funding commitments | PDF p146, note38 | 57.89 |
| Current maturities of term borrowings | PDF p141, note24 | 253.25 |
| Current cash credit/working-capital facilities | PDF p141, note24 | 147.23 |
| Supplier finance within trade payables | PDF p161, note53 | 649.59 |

The ₹30.41 crore capital-payable balance is a March observation, not a confirmed September balance. Adding it as a temporary reserve to opening debt is conservative if future capex already includes settlement. It must be described as a research reserve rather than additional verified September borrowing. Likewise, management's November statement that planned projects are largely included in Q2 accounts is not by itself proof that all related cash has been paid.

Supplier-finance terms are 90–180 days, versus up to 90 days for comparable other liabilities. Reported operating cash flow includes payments under this arrangement. A runoff stress is useful, but adding all ₹649.59 crore to debt while also charging its settlement through working capital would double count. The author's proposed separate ₹150 crore runoff stress avoids that error if entered only once.

A net-debt reduction forecast does not establish that every contractual principal maturity is paid from that year's free cash. Year-one retention around ₹200 crore is below the March current term-debt maturity amount. The model consequently relies on some combination of working-capital facility rollover, existing financial assets and normal refinancing. This is a funding assumption to disclose. The March undrawn-facility figure is not verification of September availability.

## Valuation construction checks

1. Using EBITDA after recurring lease cash and debt excluding lease liabilities is internally consistent. Do not also subtract lease liabilities from that equity value without adjusting the earnings basis.
2. If free cash is retained to reduce debt, it creates value through lower terminal debt. Only dividends actually assumed paid are also counted separately. Counting the entire free cash flow as annual owner distributions and using the same cash to reduce terminal debt would duplicate value.
3. Excluding all other income from operating EBITDA while applying a stated haircut to financial assets in opening net debt avoids treating volatile investment returns as operating earnings. The haircut is a scenario, not an independently measured fair-value loss.
4. Current investment categories include corporate/perpetual bonds, AIFs and unquoted equity. The September portfolio mix is not proven by March categories. Liquidity and value cannot be inferred solely from the accounting label “current.”
5. Cash-tax assumptions must not recycle the H1 tax-credit benefit. A tax sensitivity of an extra ₹10–15 crore annually is appropriate if the working case uses cash tax below an approximate ordinary tax charge.
6. Issued capital of ₹26.25 crore at face value ₹10 implies 2.625 crore issued shares. Weighted EPS denominators differ because treasury and potential ordinary shares exist. Using the full issued count as a conservative denominator is reasonable if labeled, not called an exact diluted count without a full option reconciliation.

## Source custody

Original results: https://www.cosmofirst.com/public/uploads/images/63da6a9c3c48.pdf

Original annual report: https://www.cosmofirst.com/public/uploads/pdf/7cf169e34112.pdf

Original call transcript: https://www.cosmofirst.com/public/uploads/pdf/245f3cae08f6.pdf

The author's `source_downloads.json` records original byte counts and hashes. A web-preview retry failed because of source accessibility/annual-file size, so this review relies on the retained original files and explicitly inspected pages, not a successful web-text extraction.

## Completed numerical model review

The final calculation file was read and independently recalculated. Free cash, annual dividends, retained cash, ending net debt, terminal enterprise/equity value, and discounted values all reconcile. Only the assumed ₹10 crore annual dividend is distributed. The remaining cash reduces terminal net debt. There is no cash-distribution/deleveraging double count.

| Case | Present value at 10% | At 12% | At 15% | Current-price cash-flow IRR |
|---|---:|---:|---:|---:|
| Downside | ₹217.58 | ₹206.30 | ₹190.82 | −29.80% |
| Working | ₹756.26 | ₹716.64 | ₹662.25 | 6.85% |
| Upside | ₹1,311.95 | ₹1,243.09 | ₹1,148.56 | 28.46% |

The current price is ₹824.90. The author uses 2.65 crore shares as a rounded conservative diluted assumption, compared with issued 2.6249727 crore and H1 implied weighted diluted approximately 2.6348 crore. The distinction is explicit. Working cash tax was raised to ₹60/65/70 crore after review, avoiding reliance on the tax-credit benefit.

The user has not supplied a universal 15% hurdle. Showing 10/12/15% preferences is appropriate. The current price exceeds even the 10%-discounted flat working value, so a price-dependent verdict does not require imposing 15% as policy.

### Incentive collection assumption

The H1 cash statement removes ₹36.68 crore of unrealized sales-tax incentives before working-capital changes, whereas the amount remains in operating EBITDA. This must be accounted for explicitly when converting EBITDA to available cash. The author clarified the working ₹45 crore annual cash absorption as ₹30 crore for incentive-receivable growth and ₹15 crore for ordinary working capital. That is a scenario, not an observed future collection rate.

The independent review confirmed on annual-report PDF pages 134–135 March current plus noncurrent incentive receivables of ₹129.17 crore versus ₹101.52 crore a year earlier. Against ₹57.20 crore annual income recognition, the mechanical difference suggests approximately ₹29.55 crore collection or other adjustment. This is not a directly verified receipt amount. If annual incentives of ₹73.36 crore remained wholly uncollected, an incremental ₹43.36 crore annual cash absorption beyond the already reserved ₹30 crore would be needed. This should enter once, not be added again as a second full ₹73.36 crore working-capital charge.

**Review conclusion:** the calculation mechanics pass. WATCH_PRICE at ₹824.90 is consistent with the stated flat operating case. The approximate ₹650–700 entry discussion remains conditional on sustained operating earnings, some incentive collections, no damaging supplier-finance runoff and the disclosed debt/funding assumptions. Neither scenario present values nor the entry range are measured downside floors. The most consequential cash qualifications are now explicit rather than hidden in EBITDA.

No model files were edited. This review does not validate forecast profitability or confer trade authority.
