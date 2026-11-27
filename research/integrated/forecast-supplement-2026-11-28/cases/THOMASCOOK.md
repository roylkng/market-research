# THOMASCOOK: prospective December 2026 PAT

**Base forecast: ₹68.33 crore.** Scope: CONSOLIDATED, target: PAT_ATTRIBUTABLE_TO_OWNERS. Evidence cutoff: 28 November 2026 IST. This case belongs to the frozen first-12 supplement and does not replace the 27 November forecast.

## Verified financial anchors

| INR crore | Jun 2026 | Sep 2026 | Sep 2025 | Dec 2025 |
|---|---:|---:|---:|---:|
| Reported target PAT | 71.9000 | 51.6700 | 66.4400 | 41.7000 |

The financial anchors come from S1 and S2, at the page locators below. No current owner-PAT correction. Q1 owner71.90 exceeds group63.71 because NCI loss is8.19. The bridge must include equity associates0.21/0.08. Prior September property gain and prior December labour charge create opposite seasonality distortions.

## Facts, issuer commentary and interpretation

- **Fact:** S1 p16 confirms owner PAT71.90/51.67/66.44 in current June, current September and prior September. S2 p19 confirms prior-December owner PAT41.70.
- **Fact:** Prior-December PBT before exceptional items is89.74cr. Its30.10cr labour charge is separate from recurring service, finance and operating costs.
- **Issuer statement:** S3 pp14,18 clarifies forward India leisure/MICE December-quarter bookings are30% higher in value, and that India basket is roughly51% of the travel segment, not the entire group.
- **Issuer statement:** S3 pp18–19 says international recovery remains uneven. Sterling input-GST cost impact is discussed as4cr in Q2 and is not presented here as a temporary addback.

Use prior December pre-exception PBT as the seasonal operating anchor, then separately vary India travel, international DMS, Sterling, financial services, DEI, treasury and ongoing scheme costs. This avoids projecting a30% booking-value claim onto the entire group. Tax and minority profit convert the business-level estimate to owners.

## Explicit forecast assumptions

- Base pretax changes from the prior December anchor: India+8, financial services+3, Sterling+4, internationalDMS-8, DEI-2, other income+10, cost inflation/central costs-3 and scheme cost-1 = PBT100.74.
- The +10 treasury adjustment retains only part of Q2 other-income uplift from prior December40.93 to current58.87. All forward component amounts are analyst assumptions, not company guidance.
- Base effective tax29%, associates0.3 and NCI3.5. Current group perimeter, including Sterling, is retained. No demerger completion or new labour past-service charge assumed.

Formula: `owner_PAT = sum(PBT_component_amounts) * (1-tax_rate) + equity_associates_after_tax - NCI`. Full parameters and signed component amounts are in the companion JSON.

| Sensitivity | PAT, ₹ crore | Assumption |
|---|---:|---|
| Adverse | 35.43 | Bookings fail to convert and overseas recovery stalls, tax34% and NCI4. |
| Base | 68.33 | Selective India and lodging recovery offsets part of overseas damage. |
| Favorable | 91.95 | Stronger conversion, near-normal international operations and sustained other income. |

These scenarios have no assigned probabilities. They are neither confidence intervals nor coverage claims.

## Competing simple forecasts

| Baseline | Reported inputs, ₹ crore | Normalized inputs, ₹ crore |
|---|---:|---:|
| latest quarter | 51.67 | 51.67 |
| two quarter mean | 61.79 | 61.79 |
| damped sequential | 46.61 | 46.61 |
| seasonal naive | 41.70 | 62.77 |
| seasonal additive | 26.93 | 65.74 |
| seasonal yoy | 32.43 | 66.60 |

Damped baseline carries 25% of the latest sequential PAT change. Additive seasonality uses prior December plus current September minus prior September. Multiplicative seasonality is suppressed when required PAT values are nonpositive.

**Normalization:** Prior Q2 property sale: subtract17.74cr, the explicitly disclosed parent-company post-tax gain in S1 note7. Prior Q3 labour charge30.1cr: add21.07 assuming30%tax relief and full owner attribution. Labour amount is documented, its tax/NCI split is not. That21.07 is an analyst normalization estimate, not an issuer-reported adjusted owner PAT. Current legal-scheme charges0.20/0.84 remain because further costs may recur.

Labour addback at25%tax would be22.575 instead of21.07, and minority attribution could reduce either. Reported and normalized baselines are both retained.

## What can break this forecast

- Booking cancellations, visa/flight constraints and conversion of advance bookings into recognized net income.
- International DMS and DEI recovery, forex/MTM gains and owner-NCI mix.
- Legal-scheme completion and any change to December reported group scope.

Research hypothesis: earnings recovery can outpace weak September reported PAT, but booking growth must be converted within the correct segment and owner scope. No investment verdict inferred.

## Primary-source receipts

- **S1** [Unaudited standalone and consolidated results, September 2026](https://resources.thomascook.in/downloads/Financial_Results_Sept_30_2026.pdf), dated 2026-11-02. PDF p16 consolidated income statement, pp21–22 notes5–9. Search renderer rejected large PDF. Direct captured original was inspected. Captured 14,694,352 bytes. SHA256 `faaa61dba66fb0d0b5d0421223b6dbeb185077d3a325430110984583c9ce1cbd`.
- **S2** [Audited March 2026 results with December 2025 comparative](https://resources.thomascook.in/downloads/Audited_Financial_Results(Standalone_and_Consolidated)_for_the_quarter_and_year_ended_March_31_%202026_20260513.pdf), dated 2026-05-13. PDF p19 December comparative owner PAT and exception, p26 note12 labour-code charge. Captured 7,843,847 bytes. SHA256 `f8699551ce650bf1de23805950758c071944612a733242103618f0cbed63bde5`.
- **S3** [Q2 FY27 earnings call transcript, call held November3](https://resources.thomascook.in/downloads/TCIL_Q2_FY27_Earnings_Call_transcript_20261109.pdf), dated 2026-11-09. PDF pp6,14–15,18–19 booking scope, Sterling costs and recovery commentary. Captured 411,643 bytes. SHA256 `60118b1357e13affb18909b9713b849ce7c3b3810e4b9c43ca608faff53cf5e9`.

Original PDFs were captured outside the tracked repository. Exact receipt paths, web references, review time and visually inspected page numbers are recorded in the JSON. No absent screenshot or absent original-byte claim is made.
