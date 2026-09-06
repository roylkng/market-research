# Company intelligence v1: promise to delivery

## Objective

Create a source-grounded record of what management said would happen and what later official disclosures show actually happened.

This layer is designed to answer questions that ordinary ratio screens do not answer well:

- Does management repeatedly hit its own operating targets?
- Are capacity announcements commissioned when promised?
- Does an announced order/ramp actually convert into revenue and cash?
- Is growth produced by physical activity or by price/mix/accounting effects?
- Does a company revise targets transparently before or after a missed deadline?

V1 does **not** use share-price returns and does not produce an investment score.

## Evidence rules

Every claim needs:

- date
- official source URL
- source type
- source locator
- normalized metric/target
- target date or horizon
- immutable content hash for the normalized claim record

Every outcome needs independent later evidence and cannot predate the claim.

Allowed resolution states:

- `MET`
- `PARTIAL`
- `MISSED`
- `LATE`
- `UNRESOLVED`

`UNRESOLVED` is a valid research result. The system must never force ambiguous evidence into success or failure.

## Initial evidence chains

### CCL Products

Claim source, 6-Nov-2024 Q2 FY25 earnings call:

`https://www.cclproducts.com/wp-content/uploads/2024/11/Q2-Earnings-Call-Transcript-2024-25.pdf`

Management maintained FY25 volume-growth guidance of 10-20%.

Outcome source, 6-May-2025 Q4 FY25 call:

`https://www.cclproducts.com/wp-content/uploads/2025/05/Q4.pdf`

Management described full-year volume growth as roughly 10%. V1 records this `MET` with the observed value marked approximate because the later disclosure itself was approximate and close to the lower bound.

### Shaily Engineering Plastics

Claim source, 11-Aug-2025 Q1 FY26 earnings call:

`https://static.shaily.com/iCbuWN4RSVShshhOJqvW-shaily-engineering-q-1-f-y-26-c-all-transcript-pdf`

Management described two pen-capacity expansions and an effective capacity of about 70-75 million pens per year after expansion, with the second 25-million line expected during Q1 FY27.

Outcome source, 10-Aug-2026 Q1 FY27 earnings call:

`https://static.shaily.com/cmUVF3BhT3mFfVZJC9K8-sepl-q-1-f-y-27-e-arnings-conference-call-transcript-final-pdf`

After Q1 FY27 had ended, management stated that the additional 25-million line was still expected to become operational by end-September 2026. V1 therefore records the earlier timetable as `LATE`, without inventing an observed installed-capacity number for the pre-commissioning date.

### Netweb Technologies

Claim source, 31-Jan-2025 earnings call:

`https://www.netwebindia.com/investors/Transcript_31012025.pdf`

Management described AI systems as roughly 14-15% of business and expected the contribution to reach roughly 20% within one to two years.

Outcome source, 31-Jul-2025 Q1 FY26 investor presentation:

`https://www.netwebindia.com/investors/board-meeting/2025-26/Earning_Presentation_Q1.pdf`

AI systems contributed 29% of operating revenue in Q1 FY26. V1 records the earlier mix target as `MET`.

The later quarter is a single-period mix and is not evidence that 29% is a sustainable annual mix. The ledger records whether the earlier threshold was observed, not whether the company has permanently transformed.

## CLI

```bash
marketlab delivery-report \
  research/company-intelligence/claims_v1.yaml \
  --symbol CCL
```

The report is descriptive. `met_rate_resolved` is not a validated investment signal.

## Next research step

Expand this ledger across the development cohort, then test the **pre-existing** delivery record as one independent feature in proposed H003. A claim whose outcome became known after the H003 decision date cannot contribute to that decision's credibility feature.
