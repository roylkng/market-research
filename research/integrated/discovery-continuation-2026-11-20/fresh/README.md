# Fresh discovery: R Systems completed case

Decision date: 20 November 2026. Reference price: **₹242.50**, NSE EQ close on 19 November. Horizon: five years. Research only. **Disposition: RESEARCH WATCH, not BUY.**

R Systems is a credible new cash-producing candidate, but the fully funded base return is approximately **9.6–10.6% a year**, depending on whether the terminal multiple uses year-five or following-year cash. The base includes acquisition consideration, incentive dilution, ordinary capital expenditure, leases, tax and all ₹275 crore of acquisition-debt principal. The disappointment case loses approximately 6.1% a year. A moderate combination of slower growth, weaker margins and a lower terminal multiple produces only 2.0% a year.

This is a completed priced assessment. The reason for WATCH is the return versus operating and allocation risks. It is not absence of a cash-flow statement or a universal 15% threshold. A price around **₹210–220** merits renewed purchase evaluation with unchanged economics. At the present price, evidence supporting **8% organic growth and a 19.5% cash EBITDA margin**, with the same terminal multiple and modeled dilution, raises the modeled return to 13.1%. These are separate routes for changing the decision.

## Deliverables

- `rsystems_inputs.json`: facts, assumptions, unit conventions and source-sensitive treatments.
- `rsystems_model.py`: standard-library calculator with dated debt payments, cash ledger, dilution and payout accounting.
- `rsystems_model_results.json`: all annual ledgers, scenarios, sensitivities and entry-price arithmetic.
- `lead_triage.md`: four new leads, selection rationale and the boundary of this search.
- `source_receipts.json`: original source URLs, byte counts and SHA-256 receipts, including failed routes.
- `verification.md`: visual checks and remaining source discrepancies.

Run `python rsystems_model.py` from this directory or use its absolute path. No network, external package or new input is required.

## 1. What shareholders are buying

R Systems sells product engineering, data, cloud and automation work to technology and enterprise customers. It also has a smaller knowledge-services business. The customer need is understandable: modernize revenue-producing software, integrate data and automate workflows. Yet spending is project-based. On the 4 November call the CEO explicitly explained that renewals usually mean winning new projects from existing clients. The revenue should not be valued as contractual subscription revenue. [S3, S6]

Latest quarterly revenue is ₹615.200 crore and owner PAT is ₹64.183 crore. Nine-month revenue is ₹1,791.669 crore and owner PAT is ₹185.167 crore. The fiscal year ends in **December**, so these are Q3 and nine-month CY2026 figures, not Q2 FY2027. TTM reported owner PAT to September is ₹221.575 crore. At the latest verified issued count of 118,495,958 shares, the reference market capitalization is approximately ₹2,873.5 crore. The naive reported P/E is about 13 times, but that denominator omits substantial future ownership claims. [S1, S3]

Nine-month profit includes zero allocation to non-controlling interests even though Novigo preference shares appear as ₹192.388 crore of NCI in the balance sheet. This accounting presentation does not eliminate the former owners' future claim. [S3, S5]

## 2. Cash that has actually been collected

All amounts below are consolidated ₹ crore. Cash interest is deducted separately because it is classified in financing cash flow. Lease cash is the full reported lease payment. [S2, S4]

| Period | Operating cash | PPE and software capex | Lease cash | Interest cash | Cash before debt principal, dividends and existing incentive dilution |
|---|---:|---:|---:|---:|---:|
| CY2025 | 219.869 | 44.000 | 19.398 | 7.214 | 149.257 |
| H1 CY2025 | 59.216 | 21.030 | 8.283 | 0.442 | 29.461 |
| H1 CY2026 | 163.258 | 15.070 | 13.128 | 14.241 | **120.819** |
| TTM to June 2026 | 323.911 | 38.040 | 24.243 | 21.013 | **240.615** |

The TTM cash result and H1 annualized result of ₹241.638 crore broadly agree. Neither is a nine-month cash result. The September filing has no nine-month cash-flow statement. H1 receivables released ₹51.192 crore, but other assets absorbed ₹47.583 crore, provisions absorbed ₹17.528 crore and payables absorbed ₹4.384 crore. Net working capital therefore absorbed cash. The improvement is not simply a one-line receivable release.

Historical cash is before the economic cost of equity compensation. The forecast addresses the existing pool through diluted shares, rather than also subtracting the same awards as cash. It introduces a separate 1% of revenue cash-equivalent compensation cost from year five for a new award cycle. The 1.25% cost beginning in year four is an explicit sensitivity.

## 3. Growth quality and competitive pressure

Nine-month INR growth of 27.7% includes Novigo, acquired on 13 November 2025, and currency effects. Management does not disclose a complete organic growth bridge. The latest quarter grew only about 1.2% sequentially in US dollars. Its aspiration to reach 3–4% quarterly growth is an issuer ambition, not achieved growth or guidance used by this model. [S3, S5, S6]

The company's presentation attributes ₹78.7 crore of the ₹119.9 crore increase in nine-month adjusted EBITDA to currency, about **66%**. The quarterly bridge is even clearer: operating changes reduced adjusted EBITDA ₹3.3 crore while currency added ₹7.0 crore. The base therefore grows revenue 6%, without assuming further currency depreciation, and uses a 19% cash EBITDA margin. Statutory nine-month EBITDA before existing noncash RSU charges is about 19.65%, below the issuer's 20.14% adjusted measure. Hedge accounting began on 1 January 2026, moving effective forward-contract remeasurement into OCI until the hedged transaction occurs. Direct comparison of reported other income across years is unsafe. [S3, S5, S6]

AI can increase demand for integration and implementation while reducing the billable effort required per project. Clients can demand part of the productivity benefit. Larger engineering suppliers, specialist firms, clients' own technology teams and software platforms are plausible substitutes. No exclusive technology, protected price premium or externally verified customer retention moat was established in this review. Top-ten customers are only 24.44% of revenue and the largest is 5.81%, which limits single-client exposure. It does not remove common IT-budget risk. Americas account for 70.6% of revenue. [S5, S6, analyst inference]

## 4. The complete ownership and funding bridge

| Claim | Treatment | What is known and what is assumed |
|---|---|---|
| Issued equity | 118.495958 million shares | Verified September issued shares. Later allotments were not comprehensively certified. |
| Velotio OCRPS | Add 5.160833 million shares | One-for-one conversion modeled in full. Do not also deduct the ₹240.7 crore historical equity carrying value as cash. |
| Existing incentive plan | Add remaining 7.807487 million shares | Full authorized eight-million-share capacity less shares already issued. This is a conservative ceiling, not the count of awards currently certain to vest. |
| Novigo contingent stock | Base adds 11.546392 million shares | Deal presentation: eight times average FY2026/FY2027 EBITDA, less ₹400 crore upfront. Base assumes ₹85 crore EBITDA and ₹242.50 conversion value, implying ₹280 crore of stock. The exact future swap ratio is not yet disclosed. |
| Base total diluted shares | **143.010670 million** | Approximately 20.7% above issued shares. All dilution is charged from the start, including shares that may be issued later. |
| NCD principal | Repay ₹275 crore in cash | Six approximately ₹45.833 crore semiannual payments from May 2028 through November 2030. Coupon 9.75%, accrued on the dated remaining principal. |
| Leases | Deduct full annual cash rent | Do not also subtract all ₹112.204 crore lease liabilities from terminal equity. |

The ₹192.388 crore balance-sheet NCI is the fair value of the same Novigo claim. It is not deducted again after modeling shares. The ₹85 crore base earnout EBITDA is an assumption, not verified current Novigo performance. The acquisition announcement reports FY2025 Novigo revenue of ₹264.4 crore, while the annual report's calendar-year acquisition contribution and pro-forma disclosure imply ₹181.383 crore. Different periods and possible scope or accounting differences require reconciliation. Neither number is silently substituted for current consolidated organic growth. [S2, S3, S7]

Opening cash uses issuer September balance-sheet cash of ₹302.310 crore plus other bank balances ₹139.853 crore, less ₹94.797 crore of September-declared dividend paid in October and ₹0.967 crore current borrowing. This gives ₹346.399 crore. An additional ₹2 crore reserve for minor loans or restrictions gives **₹344.399 crore** in the model. Management's already-net presentation number of ₹348.7 crore differs by ₹2.301 crore. We use the lower reconstructed amount and do not deduct the dividend twice. [S3, S5]

A ₹150 crore operating cash reserve is withheld from terminal excess cash. Annual-report net unfunded gratuity is ₹66.975 crore, with other employee-benefit provisions separately reported. Reserving that full gratuity balance again, beyond the operating cash floor, is a sensitivity and reduces base IRR by 0.27 percentage point. This is not a claim that the entire liability is due immediately. [S2]

## 5. Funded valuation

These are analyst scenarios, not probabilities or forecasts validated by historical outcomes. Annual periods run from 20 November 2026 to 20 November 2031. All shareholder cash flows are pre-personal-tax and exclude trading costs.

Common assumptions are leases of 1.1% of revenue, total capital expenditure of 1.5%, incremental working capital of 16% of incremental sales, tax of 28.5% and a 50% distribution of cash left after debt principal. The model labels 1.2% capex as maintenance and 0.3% as growth for interpretation, but both are fully deducted. That split is not a company disclosure. No additional acquisitions, treasury interest or capital raising are credited.

Acquired-intangible amortization is not replacement capex. The model starts from cash EBITDA, deducts actual economic capital needs and assumes **no acquired-amortization tax shield**. Allowing a ₹42.4 crore annual tax deduction, approximately four times the latest disclosed acquisition amortization, would raise base IRR to 11.45%. Eligibility and duration have not been established, so this benefit is excluded from the base.

| Scenario | Revenue | Cash EBITDA margin before existing RSU accounting | Novigo stock claim and assumed issue value | Terminal multiple | Year-one owner cash before principal | Five-year dividends/share | Terminal/share | Annualized return |
|---|---|---:|---|---:|---:|---:|---:|---:|
| Downside | First-year −10%, then flat | 14.5% | ₹125.6cr at ₹200 | 10× year-six cash | ₹161.4cr | ₹21.10 | ₹158.68 | **−6.06%** |
| Base | 6% a year | 19.0% | ₹280cr at ₹242.50 | 12× year-six cash | ₹260.1cr | ₹42.78 | ₹349.02 | **10.59%** |
| Upside | 10% a year | 20.5% | ₹440cr at ₹300 | 15× year-six cash | ₹284.8cr | ₹51.33 | ₹535.17 | **20.22%** |

Downside also includes a ₹25 crore receivable loss and realizes only half the potential working-capital release. No scenario requires fresh borrowing or a cut below the modeled cash floor. The upside needs both stronger operations and a richer valuation and is not the decision anchor.

The model values **following-year cash** at the terminal date. Using 12× year-five cash instead produces a **9.61% base return**, the better direct comparison when another case uses year-five cash. These are two conventions, not two independent positive scenarios.

At the base fully diluted share count, the reference price represents about 14.4 times the historical ₹240.615 crore cash residual. The base terminal assumption therefore compresses that ratio to 12 times. It does not require a rerating above the current cash valuation. The multiple is an analyst assumption with explicit 10× and year-five alternatives, not an observed fair-value fact.

Interest in the forecast is day-weighted annual-period cost on the scheduled principal balance. It approximates the economic burden without claiming to reconstruct every quarterly coupon date or accrued-interest cutoff.

| Base sensitivity, other assumptions unchanged | Annualized return |
|---|---:|
| Margin 18.5% | 9.73% |
| Margin 17% | 7.00% |
| Growth 3% | 8.11% |
| Terminal multiple 10× | 7.58% |
| Novigo consideration at ₹200/share | 10.19% |
| Novigo average earnout EBITDA ₹105cr, without extra operating benefit | 9.54% |
| Future compensation 1.25% of sales from year four | 10.14% |
| Total capex 2% of sales | 9.38% |
| Incremental working capital 22% | 9.77% |
| Retain all generated cash, no dividend | 10.07% |
| Distribute all cash available after principal | 11.16% |
| Joint moderate stress: 3% growth, 17.5% margin, 10× terminal, ₹200 issue value and earlier 1.25% compensation | **1.97%** |

Distributions reduce company cash in the same ledger. Retained cash is counted once, as terminal excess cash. The 10.07–11.16% payout sensitivity shows that arbitrary dividend timing is not creating the base return.

## 6. Leadership, alignment and integrity

| Observed management choice | Evidence and economic consequence | Assessment |
|---|---|---|
| Bought Novigo for ₹400cr upfront and additional stock | ₹275cr of acquisition debt plus a real contingent claim. Capability expansion is plausible, but gross acquisition cost is not just the advertised upfront six-times EBITDA. | MIXED |
| Returned cash while integrating acquisitions | Paid ₹6/share in H1 2026 and ₹8/share in October. Historical distributions are real. They are neither an entitlement for a new buyer nor proof that the same payout repeats. | SUPPORTED action, future payout unknown |
| Granted management incentives | Eight-million-share plan and performance-linked awards. The 12 November CEO continuation ballot refers to existing 2,841,546 awards, not a new second grant of that amount. | MIXED alignment and dilution |
| Discussed weaker organic progress and productivity gains | Ambition to accelerate is not the same as booked execution. FX drives much of the reported margin improvement. | MIXED |

The FY2025 audit opinion and latest limited review do not establish a fraud-free company. The annual auditor reported specific audit-trail limitations: parent database and revenue systems in Q1 2025, payroll throughout 2025, and insufficient audit-trail assurance for an acquired subsidiary. The report also describes migration of the main accounting software in April 2025. Current completion of all remediation has not been verified. This is **adverse control evidence requiring review**, not an allegation that the financial statements are fabricated. A future purchase decision must revisit remediation and any fresh auditor or regulatory finding. High earnings growth cannot offset an unresolved material integrity problem. [S2, S3]

The CEO, CFO and finance vice-president appeared on the latest call. That verifies named accountability, not succession depth or culture. Independent customer and employee corroboration was not completed. Blackstone's historical acquisition or delisting proposal is not a valuation floor or an integrity guarantee. [S6, S8]

## 7. Ten-lens coverage and decision changes

| Framework lens | Status | Decision implication |
|---|---|---|
| Market, sector, opportunity cost | MIXED | Current issuer FX and demand evidence is strong. A fresh market-wide return, rates and flow census is outside this four-lead search. Compare the 9.6–10.6% base with other completed cases and diversified exposure rather than infer all-market cash. |
| Customer need and runway | MIXED | Integration and modernization needs are identifiable. Project wins and funded demand matter more than AI market-size claims. |
| Competition and value capture | MIXED | Customer concentration is manageable. Pricing power and moat durability remain unproven. |
| Leadership and judgment | MIXED | Acquisition and payout choices are observable. Organic execution must catch up with stated ambition. |
| Integrity, incentives, minority alignment | ADVERSE_EVIDENCE | Audit-trail deficiencies and dilution warrant explicit review. No misconduct finding is inferred. Current remediation is unknown. |
| Team, culture, succession | UNKNOWN | Named finance and operating leaders verified. Independent execution depth and succession resilience not established. |
| Stakeholder reputation | MIXED | Repeat-project narrative and diversified customers are issuer evidence. Independent corroboration is absent. |
| Capital allocation and owner economics | MIXED | Collected cash and debt funding are reproducible. Contingent equity, future award cycles and further M&A can change per-share value. |
| Expectations and valuation | SUPPORTED | Price identity, cash bridge, diluted scenarios and sensitivities completed. Assumptions remain scenarios, not probabilities. |
| Catalysts, timing, portfolio fit | MIXED | Next comparable organic growth, year-end cash and Novigo conversion disclosures can change the decision. Portfolio holdings and concentration are not supplied. |

**Three decision-moving facts:** comparable organic growth without another acquisition step, sustainable cash margin without another favorable FX move, and the actual Novigo conversion ratio. These receive priority over more narrative coverage.

The **price route** is renewed evaluation around ₹210–220. With identical operating assumptions, ₹210 gives base 14.02% and downside −3.20% a year. ₹220 gives base 12.90% and downside −4.13%. These levels improve the asymmetry but are not automatic orders or guarantees.

The **same-price route** is evidence supporting 8% organic growth and a 19.5% cash margin, with no larger dilution than modeled and funded cash conversion. That produces 13.11% at ₹242.50 without changing the 12× terminal convention. The next complete comparable period and full-year cash statement can test that route. Current book profit, the AI label and the historical purchase price cannot substitute for those observations.

**Strongest counter-thesis:** productivity benefits accrue to clients, organic growth stays low, currency reverses, and management uses retained cash for additional acquisitions. In that world a seemingly inexpensive P/E can coexist with weak outside-shareholder returns. The joint stress quantifies a less dramatic version of that outcome.

## Original-source map

All sources observed on 20 November 2026. SHA-256 and byte receipts are in `source_receipts.json`. PDF physical page numbers are used below where relevant.

- **S1** NSE official 19 November EQ bhavcopy. https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261119_F_0000.csv.zip
- **S2** CY2025 annual report, audit dated 10 February 2026. Cash physical pages 226–227, borrowings 255, acquisition 276–277, controls printed page 220 and Note 39. https://media.rsystems.com/wp-content/uploads/2026/05/RSI-Annual-Report-2025.pdf
- **S3** Signed Q3 and nine-month financial results, filed 3 November 2026. P&L physical page 3, notes page 4. https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_03112026211010_RSYSTEMS_sd.pdf
- **S4** Signed H1 financial results, filed 4 August 2026. Consolidated cash physical page 7. https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_04082026210024_RSYSTEMS.pdf
- **S5** Q3 issuer press release and investor presentation, 3 November 2026. Balance sheet press release page 7, FX bridge presentation pages 4–5. https://media.rsystems.com/wp-content/uploads/2026/11/Press-Release.pdf and https://media.rsystems.com/wp-content/uploads/2026/11/R-Systems-Investor-Presentation-Q3-2026.pdf
- **S6** Earnings call of 4 November, filed 10 November 2026. https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_10112026193327_Rsystems_.pdf
- **S7** Novigo acquisition terms, 21 August 2025. Stock formula physical page 10 and merger/conversion disclosures pages 15–16. https://nsearchives.nseindia.com/corporate/RSYSTEMS_21082025193752_R_Systems_SPA.pdf
- **S8** CEO continuation postal ballot, 12 November 2026, approval pending as of the review date. https://nsearchives.nseindia.com/corporate/RSYSTEMSPJ_12112026195700_Intimation_of_Postal_Ballot_Notice_.pdf

This file does not change frozen historical experiments, earlier company judgments, portfolio policy or live-capital restrictions. Scenario probabilities, benchmark outcomes and out-of-sample calibration remain unset. Named peer review checks the evidence and arithmetic. It is not independent investment ground truth.

The separate reviewer reproduced all three scenarios, share counts and tranche-interest calculations. Its report is [the R Systems peer review](../independent/rsystems/rsystems_independent_review.md). It additionally combines 18.5% margin, earlier 1.25% future compensation and the full legacy-gratuity reserve, yielding 8.98% with the following-year terminal convention. That combined result reinforces WATCH rather than changing it to BUY.
