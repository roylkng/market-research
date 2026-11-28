# DEVYANI: prospective December 2026 PAT

**Base forecast: ₹12.72 crore.** Scope: CONSOLIDATED, target: PAT_ATTRIBUTABLE_TO_OWNERS. Evidence cutoff: 28 November 2026 IST. This case belongs to the frozen first-12 supplement and does not replace the 27 November forecast.

## Verified financial anchors

| INR crore | Jun 2026 | Sep 2026 | Sep 2025 | Dec 2025 |
|---|---:|---:|---:|---:|
| Reported target PAT | 14.6470 | -0.2420 | -21.8870 | -10.3890 |

The financial anchors come from S1 and S2, at the page locators below. No owner-PAT correction to the frozen register. Its 0.229cr Q2 PBT-to-PAT gap is explained by JV loss, not a bad owner-PAT input. Group Q2 PAT is +3.462 but owner PAT is -0.242 after 3.704 NCI.

## Facts, issuer commentary and interpretation

- **Fact:** S1 verifies the four current comparative owner-PAT anchors jointly with S2. Units are million rupees, converted to crore by dividing by 10.
- **Fact:** S2 documents 21.503cr group exceptional charges in prior December, including 12.213cr group labour-code charge and 9.290cr lease dispute payment.
- **Issuer statement:** S3 reports 70 net store additions in Q2, including 50 KFC India units, and 2325 global stores. Management retains 200–220 full-year net-addition guidance.
- **Issuer statement:** S3 reports KFC India same-store sales +4.4%, Costa +9.9% and Pizza Hut -1.4%. It says CCI approval for the Sapphire merger was received while remaining approvals were progressing.

Positive KFC same-store sales and new units support a December recovery, but high depreciation, lease finance costs and NCI substantially dilute restaurant-level gains. Use an EBIT-to-owner bridge after all operating costs and depreciation. Assumed 4.8% EBIT margin is above the observed Q2 3.90% and below an aggressive margin-recovery case.

## Explicit forecast assumptions

- Revenue 1595cr assumes about 5% sequential growth from holiday demand plus unit additions.
- EBIT margin 4.8% explicitly includes depreciation, operating cost and FX. Other income12, finance66, tax25%, NCI4 and equity-JV loss0.2 complete the owner-PAT bridge. No new exceptional or discontinued-business charge is assumed.
- Forecast uses the September group perimeter. Merger completion is not assumed before December reporting. If combination is completed and historical comparatives restated, record a scope break rather than silently claim comparable forecast skill.

Formula: `owner_PAT = (revenue * EBIT_margin + other_income - finance_cost + exceptional_pretax) * (1-tax_rate) + equity_JV_after_tax - NCI`. Full parameters and signed component amounts are in the companion JSON.

| Sensitivity | PAT, ₹ crore | Assumption |
|---|---:|---|
| Adverse | -8.65 | Revenue1530, 3.5% EBIT, no tax credit on operating loss, high finance cost and unchanged positive NCI. |
| Base | 12.72 | Holiday demand and new units support margin recovery to 4.8%. |
| Favorable | 24.05 | Revenue1640 and 5.5% EBIT from stronger same-store sales and cost absorption. |

These scenarios have no assigned probabilities. They are neither confidence intervals nor coverage claims.

## Competing simple forecasts

| Baseline | Reported inputs, ₹ crore | Normalized inputs, ₹ crore |
|---|---:|---:|
| latest quarter | -0.24 | -0.24 |
| two quarter mean | 7.20 | 7.20 |
| damped sequential | -3.96 | -3.96 |
| seasonal naive | -10.39 | 5.26 |
| seasonal additive | 11.26 | 26.90 |
| seasonal yoy | Invalid sign/denominator | Invalid sign/denominator |

Damped baseline carries 25% of the latest sequential PAT change. Additive seasonality uses prior December plus current September minus prior September. Multiplicative seasonality is suppressed when required PAT values are nonpositive.

**Normalization:** Prior Q3 only: parent-specific labour-code charge 11.572 plus lease-dispute charge 9.290, multiplied by assumed 75% after-tax retention = +15.6465. The pretax amounts are documented in S2 note3. Tax benefit at 25% is an analyst assumption, not disclosed item-specific tax. Parent charges belong to owners. Additional group labour charge 0.641 and discontinued-business losses are left untouched because owner attribution is unresolved. Current periods have no exceptional charge in S1.

Prior-Q3 adjustment would be +20.862 with no tax benefit. Primary reported-PAT baselines are retained alongside adjusted comparators.

## What can break this forecast

- Sapphire merger approval/completion and accounting-effective reporting perimeter.
- Brand mix, local currency changes, store closure charges and exact December NCI.
- Current 3.90% operating EBIT margin can deteriorate despite positive same-store sales.

Research hypothesis: operating improvement can return owner PAT to profit. This is a quarterly earnings experiment, not a valuation or position-size recommendation.

## Primary-source receipts

- **S1** [Unaudited consolidated results, September 2026](https://dil-rjcorp.com/wp-content/uploads/2026/11/financial-results.pdf), dated 2026-11-02. PDF p1, quarterly columns and owners/NCI rows. INR million divided by 10. Captured 5,729,407 bytes. SHA256 `b3019d958c4d163cab6a7269e818ed2b7f8b6bcaca8e65c8cddc56a3c5d8fa18`.
- **S2** [Unaudited results, December 2025](https://dil-rjcorp.com/wp-content/uploads/2026/02/financial-resultsq3.pdf), dated 2026-02-04. PDF pp1,3, owners PAT, discontinued operations, note3 exceptional items and note4 merger. Captured 803,442 bytes. SHA256 `fd8b0dd7bdadf911842b21658d53f8f98c9faf305d661ef90f1aff455d3fe2d2`.
- **S3** [Q2 FY27 investor presentation](https://dil-rjcorp.com/wp-content/uploads/2026/11/investor-presentation.pdf), dated 2026-11-02. PDF pp4,5,7,12,15,18, management commentary, openings and same-store sales. Captured 4,065,602 bytes. SHA256 `0101c9db2fd918c99f3a721ab47d7a50c524937edf68a5f9023196721d506114`.

Original PDFs were captured outside the tracked repository. Exact receipt paths, web references, review time and visually inspected page numbers are recorded in the JSON. No absent screenshot or absent original-byte claim is made.
