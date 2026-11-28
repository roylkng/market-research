# PETRONET: prospective December 2026 PAT

**Base forecast: ₹1098.70 crore.** Scope: CONSOLIDATED, target: PAT_ATTRIBUTABLE_TO_OWNERS. Evidence cutoff: 28 November 2026 IST. This case belongs to the frozen first-12 supplement and does not replace the 27 November forecast.

## Verified financial anchors

| INR crore | Jun 2026 | Sep 2026 | Sep 2025 | Dec 2025 |
|---|---:|---:|---:|---:|
| Reported target PAT | 1137.1400 | 1256.4300 | 830.3000 | 869.6100 |

The financial anchors come from S1 and S2, at the page locators below. No current owner-PAT correction. The Q2 bridge gap21.80 and Q1 gap28.87 are share of JV profit after tax. Standalone press PAT1235cr is not the target. The correct consolidated target includes JV profit and is1256.43cr.

## Facts, issuer commentary and interpretation

- **Fact:** S1 p13 reports continuing Qatar force majeure through September, vessel-owner claims625.42cr plus applicable taxes, unprovided, and arbitration with uncertain outcome. It also discloses use-or-pay receivable provision230.72cr and Q2 waivers252.80cr.
- **Fact:** S1/S2 reconcile all four consolidated PAT anchors after adding equity-JV profits.
- **Issuer statement:** S3 says total throughput231TBTU versus207 sequentially and228 prior year. Dahej capacity is now22.5MTPA versus17.5, so lower utilization percentage is not evidence of lower physical throughput.
- **Issuer statement:** S3 pp6–7,10 reports aggregate commercial/operational efficiency gains658cr in Q2,494 in Q1 and41 in prior Q2. Management explicitly no longer discloses trading and inventory gains separately. The basket composition and persistence are unresolved. Forex is separate.

Forecast remaining tolling/regas earnings plus the aggregate commercial/operational efficiency basket. Its components are not separately isolated and persistence is unknown. Q2 throughput grew only1% year on year, whereas management-identified efficiency gains rose from41 to658cr. The current profit surge therefore should not be treated as a stable throughput-growth trend. The base replaces658 with450 and modestly improves regas contribution.

## Explicit forecast assumptions

- Q2 consolidated PBT1658.24 less identified efficiency gain658 leaves1000.24. This subtraction maps holding-company gain to the consolidated bridge, with small subsidiary operating differences otherwise held constant.
- Base future gains450, regas contribution+30, treasury-20 and depreciation/operating-cost-15 produce PBT1445.24. Gain450 is below both current and previous quarter, with no assigned probability.
- Tax25.5%, JV profit22 and no NCI. No December vessel provision in base. Adverse recognizes the disclosed625.42cr claim amount plus weaker efficiency gains/throughput. Applicable taxes, later claims and other losses are outside this particular charge assumption, so this is not maximum exposure. It is a stress assumption, not a prediction that the claim is legally payable.
- No benefit from uncommissioned petrochemicals or a presumed Kochi pipeline completion is booked.

Formula: `owner_PAT = sum(PBT_component_amounts) * (1-tax_rate) + equity_JV_after_tax; no NCI`. Full parameters and signed component amounts are in the companion JSON.

| Sensitivity | PAT, ₹ crore | Assumption |
|---|---:|---|
| Adverse | 305.42 | Aggregate gain150, weaker throughput and625.42cr vessel claim charge with assumed tax relief. Applicable taxes and later claims are outside this charge assumption. |
| Base | 1098.70 | Gain450 and modest regas increase, no legal charge. |
| Favorable | 1300.18 | Gain650 persists and regas contribution rises60, no legal charge. |

These scenarios have no assigned probabilities. They are neither confidence intervals nor coverage claims.

## Competing simple forecasts

| Baseline | Reported inputs, ₹ crore | Normalized inputs, ₹ crore |
|---|---:|---:|
| latest quarter | 1256.43 | 1256.43 |
| two quarter mean | 1196.79 | 1196.79 |
| damped sequential | 1286.25 | 1286.25 |
| seasonal naive | 869.61 | 888.65 |
| seasonal additive | 1295.74 | 1314.78 |
| seasonal yoy | 1315.91 | 1344.72 |

Damped baseline carries 25% of the latest sequential PAT change. Additive seasonality uses prior December plus current September minus prior September. Multiplicative seasonality is suppressed when required PAT values are nonpositive.

**Normalization:** Prior-December labour past-service charge25.44cr in S2 note5 only: assumed tax relief25.168% gives19.0372608cr PAT addback. Tax relief is an assumption. Current aggregate commercial/operational efficiency gains, use-or-pay waivers and receivable impairments are not removed from reported-PAT baselines, since they are repeated commercial/accounting exposures. They are explicit forward drivers instead.

## What can break this forecast

- Components of the aggregate efficiency basket may reverse rather than merely decline. Trading, inventory and recurring operating efficiencies are not separately quantified.
- Force-majeure resolution, future freight claims, use-or-pay settlements and impairment timing.
- Tax deductibility and timing of any vessel claim provision, applicable taxes on the claimed amount and later claims. Actual PAT can fall outside the sensitivity range.

Research hypothesis: PAT moderates as unusual commercial gains soften, even if throughput holds up. The unresolved legal exposure requires a wide sensitivity. No market-price target or portfolio action follows.

## Primary-source receipts

- **S1** [Unaudited financial results, September 2026](https://www.petronetlng.in/documents/d/pertonetlng/ufr30092026-pdf), dated 2026-11-02. PDF p10 consolidated statement and p13 notes3–4. Scanned original visually checked. Captured 944,687 bytes. SHA256 `b75b9b22ec3b2ebdd04e15de65611088996ee7c88660f63cc7c5a7b533768597`.
- **S2** [Unaudited financial results, December 2025](https://www.petronetlng.in/documents/d/pertonetlng/ufr31122025-pdf), dated 2026-02-12. PDF p5 consolidated statement, p6 notes3–5, labour past-service charge. Captured 720,500 bytes. SHA256 `257e4647f3eecf510332db3b5bddaf8d82a22ed94d9edae5d12f5543e42d467b`.
- **S3** [Post-results conference call, held November3](https://www.petronetlng.in/documents/d/pertonetlng/intimationtranscript-1-pdf), dated 2026-11-09. PDF pp6–7 efficiency gains, p8 depreciation, p10 current/prior gains. Printed transcript page numbers are one less than PDF pages. Captured 565,212 bytes. SHA256 `971f95a3c66d6fa9d7742d725ed4f9aa3ce2bd597f4df4c7b8e37cd8be775d4e`.

Original PDFs were captured outside the tracked repository. Exact receipt paths, web references, review time and visually inspected page numbers are recorded in the JSON. No absent screenshot or absent original-byte claim is made.
