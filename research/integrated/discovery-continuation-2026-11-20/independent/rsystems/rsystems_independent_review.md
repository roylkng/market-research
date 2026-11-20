# Independent challenge of R Systems | 20 November 2026

## Conclusion

**Scenario arithmetic reproduced. Research WATCH is supportable. A confident BUY is not established.** This business is a credible discovery result with substantial observed cash generation and funded debt maturities. The conclusion depends on the unresolved Novigo exchange terms, post-acquisition growth, normalized margins and recurring compensation. Do not demote it merely because the final swap ratio is not yet published. Model the range, retain it as a priority case and let price or business evidence change the decision.

A separate implementation, `independently_check_rsystems.py`, reads a frozen input snapshot and does not import the author's calculator. It integrates six separate debt tranches to their maturity dates rather than using the author's sequential balance implementation. It independently reconstructs cash uses, distributions, remaining treasury, share claims and IRRs. All three original scenarios match to floating-point precision. This verifies arithmetic under assumptions, not future returns or forensic accounting.

| Comparison | Five-year annualized scenario at ₹242.50 |
|---|---:|
| Author working model, 12× following year-six cash | **10.5910%** |
| Same model, 12× year-five cash | **9.6077%** |
| Full ₹66.975cr legacy gratuity reserve, in addition to ₹150cr operating floor | **10.3167%** |
| December2025 granted RSU count, less9M26 exercises, as an incomplete-current proxy | **10.9133%** |
| 18.5% margin, 1.25% future compensation from year4 and separate gratuity reserve | **8.9787%** |
| Favorable 8% growth / 19.5% margin with otherwise unchanged assumptions | **13.1123%** |
| Base plus hypothetical ₹42.4cr annual deductible acquisition amortization | **11.4462%** |

No probabilities are assigned. The lower and higher variants are alternatives, not additive bonuses or independent forecasts. The year-five versus year-six distinction should be visible in any chart or ranking against CMS, Medi Assist or other cases. A following-year terminal multiple is permissible, but it creates almost **one percentage point** of the displayed base return here.

## Material challenges and resolutions

### 1. Existing compensation cannot disappear when the first grant cycle ends

The first draft proposed 0.3% of revenue for a later compensation cycle. FY25 share-based compensation was ₹25.194cr, and H1FY26 was ₹12.651cr. These are closer to about1% of contemporaneous sales. The author changed the working assumption to **1.0% cash-equivalent compensation from year5**, and retained **1.25% from year4** as an earlier-replenishment sensitivity.

This is an economic charge for a new cycle. The existing plan is already diluted and its noncash expense is added back in the operating model. Deducting the same old grant's compensation expense again while fully diluting it would double count the award. Conversely, never charging later grants would overstate perpetual owner cash. The revised treatment is an explicit scenario, with an earlier, larger charge also shown.

### 2. The 8m shares are authorized plan capacity, not current grants outstanding

FY25 annual note11 authorizes no more than8,000,000 shares under the2023 plan. The model deducts100,137 actual2025 issuances and92,376 actual9M2026 issuances once, leaving7,807,487 as an unissued **ceiling**. It adds this once to current issued shares.

The actual December2025 outstanding award count was **5,945,625**:442,848 time-based,5,466,777 market-performance and36,000 nonmarket-performance awards. Subtracting9M26 exercises from that count is not a complete September2026 grant inventory because grants and forfeitures during2026 remain unverified. The full-capacity assumption is conservative and must not be called the actual fully diluted share count. Replacing it with that older grant-count proxy raises the base return by only0.32percentage point. It does not create the whole investment case.

The 5,160,833 Velotio OCRPS share conversion ceiling is a separate economic claim. Its nominal₹1 face value is not the investment cost, and it must not be confused with Novigo CCPS.

### 3. Novigo's additional claim is equity, not a second cash acquisition bill

The August2025 original agreement presentation states additional stock consideration tied to **8× average FY26 andFY27 EBITDA less the₹400cr upfront cash payment**. The later merger is intended following theFY2026-27 audit, with a swap ratio to be disclosed when approved. The current model's₹85cr average EBITDA and₹242.50 issue price are assumptions, not disclosed final settlement economics.

The annual acquisition note valued Novigo's CCPS at₹192.388cr, and the June and September balance sheets present that amount as noncontrolling interests. The model treats the future stock exchange as dilution. It does **not** subtract₹192.388cr again as financial debt or cash earnout. That is correct for the chosen equity-settlement scenario. A changed legal settlement mechanism would require a new case.

The final issuance price affects the share count. It should not automatically be set equal to today's price without the explicit sensitivity already retained. The acquisition formula and current share-price assumptions are not definitive share entitlements.

### 4. Current consolidated cash is established, but Novigo's own old numbers need reconciliation

The acquisition deck reports Novigo FY25 revenue₹264.4cr and adjusted EBITDA₹65.7cr. The FY25 consolidated annual report says Novigo contributed₹28.194cr from13November2025 and would add₹153.189cr to revenue had the acquisition occurred on1January2025. Those amounts imply₹181.383cr for that pro-forma calendar scope. This does not directly reconcile with the deck's March fiscal-year figure.

Calendar, entity perimeter, revenue recognition and gross-versus-net definitions are possible explanations. None has been proved here. It is not evidence of wrongdoing, and it does not invalidate the current signed consolidated₹615.2cr Q3 revenue. It does prevent describing the₹85cr average earnout EBITDA as a verified extrapolation of a clean historical Novigo series. The author retained the earnout as a sensitivity and the unresolved comparison as a limitation.

The current earnings call does not disclose a separate precise organic growth figure. Management says Novigo and the group move broadly together and describes growth as below its ambitions. It also attributes some margin improvement to currency and names **18.6–18.7%** as a sustainable earlier margin level. A working19% pre-existing-SBC cash margin is reasonable as an assumption with18.5% stress. Calling latest20.2% adjusted EBITDA permanently earned would require more evidence.

### 5. The declared dividend is deducted once from the correct cash starting point

The Q3 press release includes cash equivalents₹302.310cr and other bank balances₹139.853cr. The signed Q3 filing says₹94.797cr was set aside for theSeptember-declared₹8/share dividend and paid16October. Current borrowings are₹0.967cr. Therefore:

`302.310 + 139.853 − 94.797 − 0.967 = ₹346.399cr`.

The model subtracts another₹2cr for small loans/restrictions and starts at₹344.399cr. It does **not** begin with the press release's already-net₹348.7cr summary and deduct the dividend twice. The₹2.301cr discrepancy between that summary and the detailed balance-sheet bridge remains unreconciled. The lower detailed number is used. It is not large enough to determine the decision.

### 6. Gratuity is an existing claim, but avoid automatic duplicate reserves

FY25 note24 gives₹70.406cr defined-benefit obligation and₹3.431cr plan assets, leaving **₹66.975cr net unfunded gratuity**. Future EBITDA charges for new employee service do not automatically settle previously earned obligations. The ₹150cr operating cash floor may partly cover this risk, but that allocation must be explicit.

The author now preserves an additional full₹66.975cr reserve sensitivity on top of the₹150cr floor. It reduces the base return only to10.3167%. This is a conservative alternative if no floor allocation is assumed. Do not separately deduct the same old labour-code charge and the whole unfunded liability again. Ordinary trade payables are also not extra financial debt when the normal working-capital economics are retained.

### 7. The debt and lease treatment is internally coherent

The original NCD face amount is₹275cr at9.75%. The six equal principal maturities run11May2028 to11November2030. The ledger funds every₹45.833cr tranche from cash and cash generation. Principal is therefore not subtracted again from terminal equity after it is repaid. Current carrying debt is lower than face because issuance costs are amortized. Repayment uses the face obligation.

Interest is modeled by day-weighted outstanding principal inside each annual period. This is a precise principal-timing calculation but an annual-period approximation of cash coupon timing, not a separately reconstructed quarterly coupon ledger. The difference is not material at the current research precision. Recurring leases are charged as cash costs and are not also deducted at exit as if the same leases had not been paid.

## Scope of independent evidence review

I read the retained original text of theFY25 annual report, H1FY26 financials, Q3FY26 signed results, Q3 press release, acquisition terms and current earnings call. I separately viewed the rendered H1 consolidated cash page, annual acquisition note and signed9M profit statement. Source bytes and SHA receipts are in the author's source manifest. This is an independent review by another research agent, not an external audit or independently adjudicated dataset.

Critical primary documents:

- [FY25 annual report](https://media.rsystems.com/wp-content/uploads/2026/05/RSI-Annual-Report-2025.pdf), notes11,13,21,24,35 and38.
- [21 August2025 Novigo acquisition terms](https://nsearchives.nseindia.com/corporate/RSYSTEMS_21082025193752_R_Systems_SPA.pdf).
- [H1FY26 signed consolidated results](https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_04082026210024_RSYSTEMS.pdf).
- [Q3FY26 signed consolidated results](https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_03112026211010_RSYSTEMS_sd.pdf), note9 on the dividend.
- [Q3FY26 issuer press release](https://media.rsystems.com/wp-content/uploads/2026/11/Press-Release.pdf), detailed balance sheet and cash definition.
- [Current earnings-call transcript](https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_10112026193327_Rsystems_.pdf), organic growth, margin and currency discussion.

**Practical result:** put the paired9.6–10.6% working scenario in front of the user, retain the13.1% same-price evidence route, and let price improvement or stronger organic cash evidence decide. Neither the₹400cr acquisition headline nor a list of cautious adjustments is a sufficient decision rule.
