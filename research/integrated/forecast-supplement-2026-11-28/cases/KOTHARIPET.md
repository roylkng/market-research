# KOTHARIPET: prospective December 2026 PAT

**Base forecast: ₹18.32 crore.** Scope: STANDALONE, target: STANDALONE_PAT. Evidence cutoff: 28 November 2026 IST. This case belongs to the frozen first-12 supplement and does not replace the 27 November forecast.

## Verified financial anchors

| INR crore | Jun 2026 | Sep 2026 | Sep 2025 | Dec 2025 |
|---|---:|---:|---:|---:|
| Reported target PAT | 17.0247 | 19.5310 | 18.4156 | 18.6957 |

The financial anchors come from S1 and S2, at the page locators below. Direct June comparative in S1 shows PAT17.0247 and tax5.4306. Frozen half-year-minus-Q2 extraction gave PAT17.0248 and tax5.4305. This 0.0001cr rounding difference affects the new mean and damped baseline only, old predictions remain unchanged.

## Facts, issuer commentary and interpretation

- **Fact:** S1 note3 identifies a single manufacturing segment, Poly Iso Butylene. Note2 says no subsidiaries, associates or JVs, supporting standalone target.
- **Fact:** Q2 operating EBIT derived as PBT+finance-other income is22.0958cr, 13.36% of sales. Prior-December analogous EBIT is23.2532cr, 17.25% of sales.
- **Fact:** S1 cash flow identifies lease rental, interest and investment gains within non-operating income.
- **Issuer statement:** No quantitative forward sales-volume, price or margin guidance was verified. Financial-statement facts, rather than an invented management forecast, anchor this case.

A poly-isobutylene producer earns from selling-price versus feedstock and conversion-cost spread. Current sales increased but EBIT margin is about13.36% versus17.25% last December. Assume December sales160cr and margin13.5%, retaining current spread rather than extrapolating last-year peak margin. Treasury/rental/investment income is separated from manufacturing profit.

## Explicit forecast assumptions

- Sales160cr allows a3.2% sequential decline, with the prior September-to-December revenue decline serving only as a one-year seasonality clue.
- 13.5% EBIT margin keeps current feedstock/conversion spread broadly stable. Other income3cr is near recent2.86–3.27. Finance0.18 and25%tax avoid extrapolating Q2 unusually low22.5%effective tax.

Formula: `standalone_PAT = (revenue * EBIT_margin + other_income - finance_cost) * (1-tax_rate)`. Full parameters and signed component amounts are in the companion JSON.

| Sensitivity | PAT, ₹ crore | Assumption |
|---|---:|---|
| Adverse | 14.69 | Sales150, EBIT11.5%, smaller treasury income and26%tax. |
| Base | 18.32 | Sales160 and EBIT13.5%, near current spread. |
| Favorable | 21.75 | Sales170 and EBIT15%, partial recovery toward prior-December spread. |

These scenarios have no assigned probabilities. They are neither confidence intervals nor coverage claims.

## Competing simple forecasts

| Baseline | Reported inputs, ₹ crore | Normalized inputs, ₹ crore |
|---|---:|---:|
| latest quarter | 19.53 | 19.53 |
| two quarter mean | 18.28 | 18.28 |
| damped sequential | 20.16 | 20.16 |
| seasonal naive | 18.70 | 18.70 |
| seasonal additive | 19.81 | 19.81 |
| seasonal yoy | 19.83 | 19.83 |

Damped baseline carries 25% of the latest sequential PAT change. Additive seasonality uses prior December plus current September minus prior September. Multiplicative seasonality is suppressed when required PAT values are nonpositive.

**Normalization:** No adjustment. Prior September has a 0.2582cr exceptional expense in the signed PBT bridge but its nature was not established in reviewed notes. It is left in reported PAT. Prior December note says labour-code effect was not material. Do not invent a tax-adjusted addback.

## What can break this forecast

- Actual sales volume and realization were not separately disclosed in reviewed statements.
- Feedstock costs, inventory valuation and product mix can change spread sharply.
- One year of December comparison cannot establish stable seasonality.

Research hypothesis: sales growth alone overstates profit improvement if raw-material spread remains below prior-year December. No security valuation or capital action follows from the PAT estimate.

## Primary-source receipts

- **S1** [Unaudited standalone results, September 2026](https://www.kotharipetrochemicals.com/wp-content/uploads/2026/08/Unaudited-Results-30.09.2026.pdf), dated 2026-11-03. PDF p2 results, p4 segment/scope notes, p5 cash flow. INR lakh divided by 100. Captured 2,623,647 bytes. SHA256 `fae52794737ca60ee34c71c658440842107b462d5e42c736b148f55bc169cf9a`.
- **S2** [Unaudited standalone results, December 2025](https://www.kotharipetrochemicals.com/wp-content/uploads/2026/02/Unaudited-Results-31.12.2025.pdf), dated 2026-02-05. PDF pp2–3 results and labour-code note. Captured 658,050 bytes. SHA256 `0636c4a4a3b2727d4ba1dbaf288bed23ec014942bc6d814889497d1bf8b8241f`.

Original PDFs were captured outside the tracked repository. Exact receipt paths, web references, review time and visually inspected page numbers are recorded in the JSON. No absent screenshot or absent original-byte claim is made.
