# FDC focused independent review

19 November 2026. Reference price ₹373.90, official NSE close on 18 November. Amounts are INR crore except shares and per-share values.

## Verdict

**WATCH_PRICE survives the independent review and one implemented accounting correction.** The final downside, working and upside calculations reproduce independently to floating-point precision. I found no double count between operating earnings, treasury earnings, retained cash, dividends or the conditional buyback denominator.

The original model omitted the **21.93 September current tax liability** from starting credited treasury while excluding tax assets. The author accepted and implemented a separate deduction. It is not absorbed into the 75 operating buffer or 25 claims buffer. Corrected working credited treasury is **990.624**, and working annualized return is **4.005%**, versus the preliminary 4.083%. This is a real accounting improvement with a small effect on the decision. [R1, physical PDF page 11]

| Final scenario | Annualized model return | Present value at 10% | Present value at 12% |
|---|---:|---:|---:|
| Downside | −9.391% | ₹147.88 | ₹135.84 |
| Working | 4.005% | ₹284.67 | ₹260.85 |
| Upside | 14.944% | ₹463.87 | ₹424.61 |

Working present values at 8% and 15% are ₹311.21 and ₹229.52. These are alternative return preferences, not a universal hurdle or a price target.

## Successful reconciliation

- **Core versus treasury:** Mechanical TTM PAT is 313.2516. Removing all other income and normalizing the separately disclosed exceptional employee charge gives core EBITDA 380.1079, or 16.6035% of TTM revenue. Treasury income is absent from the operating multiple and is modeled separately after tax. The approach is conservative for potentially recurring nonoperating items, but avoids capitalizing financial assets' earnings and then adding the same assets again. [R1, R2]
- **Cash:** TTM CFO 453.6519 less PPE cash 260.4527, non-lease finance cash 0.6858 and full lease cash 8.7139 equals 183.7995. The annual cash flow separately identifies lease principal and interest, both included once. Forecast cash leases reduce cash economics, and lease debt is not deducted again from terminal value. [R1, physical page 12, R2, printed page 214]
- **Buyback:** 162,810,084 existing shares less 2,400,000 produces 160,410,084 conditional post-buyback shares. The same conditional state spends 120 plus the analyst 2 cost reserve. A new purchase receives no tender premium or assumed acceptance. The signed offer's record date was 13 November, and completion is not established merely because the offer opened on 19 November. [R3]
- **Retained cash:** Only the modeled ₹5 annual dividend is distributed. Remaining core cash and after-tax treasury return accumulate and enter terminal equity once. Future capex includes maintenance and growth. CWIP and a second project reserve are not deducted again.
- **Refunds and assets:** The 67.89 tax asset balance is excluded. The later refund orders totaling 72.13 receive one 75% valuation credit of 54.0975. This is not a measured probability or a claim of cash receipt. Existing investment impairment is already reflected in the accounts and is not separately charged again. [R1, R2 and the author's original refund disclosures]

## The cash rebound is not a steady run rate

Independently reconstructing the cash bridge gives TTM pre-working-capital cash of **384.938** and a working-capital source of **154.1357**. The latter explains much of the selected 183.7995 cash residual. Subtracting that source leaves a diagnostic 29.6638, still after the actual growth-heavy capex. This is **not** an estimate of maintenance-only FCF. [R1, R2]

Similarly, doubling H1 PAT produces 363.10, versus actual mechanical TTM PAT of 313.2516. June-quarter PAT was 132.49 and September 49.06. The annual plus latest-half minus prior-half construction is appropriate. Some quarterly other-income and expense subtotals are not additive under the filing's fair-value presentation note, so they should not be assembled into a separate annual operating run rate. The author already explains these limitations. [R1]

## Is the model excessively conservative?

I removed the working 5% investment haircut, the entire 75 operating buffer and the entire 25 claims buffer, retaining the tax correction and all operating assumptions. This deliberately favorable sensitivity raises working return only to **4.569%** and present value at 10% to **₹292.22**. It is not a claim that these balances can safely be distributed. It demonstrates that buffer conservatism is not the main reason the current price fails the working case.

The consequential assumptions remain 8% working revenue growth, 16.60% core EBITDA margin, capex of 200/150/110/100/110 over five model years, 4% after-tax treasury return and an 18× terminal core-owner-cash multiple. These are analyst choices. Faster profitable growth, lower necessary investment or stronger margins can improve value, but are not established by a strong seasonal half-year or a large investment portfolio.

## Employee obligation and remaining limits

Normalizing the FY26 20.7891 exceptional labor-law charge does not establish the cash amount still unpaid. Annual CFO starts after that charge, and combined gratuity and compensated-absence provisions were approximately 32.61 versus 32.58 a year earlier. Mechanically subtracting the full expense again would not be justified. The author instead added an explicitly conditional 20.7891 settlement stress. It lowers working return to approximately **3.934%**, without calling the amount a verified current payable. [R2, printed pages 214, 250 and the employee-benefit notes]

The model is a five-year rolling scenario using September accounts and a November price, not an executable historical return or a fully observed November balance sheet. Refund timing, portfolio realization, capital spending and future shareholder distributions remain assumptions. No new material model blocker remains after the current-tax correction. The appropriate next review is actual post-buyback shares and cash, followed by sustained operating cash conversion after investment.

## Scope and receipts

The reviewer inspected the executable model and inputs, independently computed all three scenarios, read the annual investment, cash, tax and employee-provision notes, and visually checked H1 original pages 10–12. Source and final-model hashes, arithmetic checks and the favorable buffer sensitivity are in `fdc_independent_review.json`. The final numeric input snapshot is retained separately. No author file was modified by this reviewer.

- **R1, signed H1 results, 27 October 2026:** https://nsearchives.nseindia.com/corporate/FDC_27102026182924_OUTCOME27102026Signed.pdf
- **R2, FY26 audited annual report:** https://www.fdcindia.com/pdf/AnnualReports/FDC%20Ltd_Annual%20Report%20FY%202025-26.pdf
- **R3, signed buyback letter of offer, 16 November 2026:** https://nsearchives.nseindia.com/corporate/FDC_16112026171030_SE_Intimation_Letter_of_Offer_S.pdf
