# HG007-P033: Source-Updated Five-Company Casework (Sambhv Cash Timing)

Status: **OUTCOME-BLIND, PROSPECTIVELY DATED EVIDENCE UPDATE**,
11 October 2026 IST. No new stock hypothesis, rank or trading.

## Why integrate the original July funding evidence?

HG007-P030 documented the main financial gaps for the five frozen
special situations, including **SAMBHV**. However, that immutable
review preceded the original-source October sales-volume update
(P031) and July board-resolution 25/75 warrant cash-stage audit
(P032). An underwriter using P030 alone could silently treat the
₹99.9971 crore warrant proceeds figure as actual financing.

P033 maintains all **five original P030 cases and original HG005
payoff sensitivities**, adding a separate source timestamp and
blocked cash/EBITDA readiness overlay ONLY to SAMBHV.

Original exact, Git-SHA-pinned sources:

- P030 five-case evidence ledger:
  research/hg007/hg007-p030-five-case-underwriting-readiness-v1.json
- P031 original 2 October Q2 sales volume and 6 October CARE
  monitoring-agency notices:
  research/hg007/sambhv-oct2026-sources/sambhv-october-case-v1.json
- P032 original five-page 15 July board proposal and warrant cash
  tranche arithmetic:
  research/hg007/sambhv-july2026-warrant/warrant-board-cash-timing-v1.json
- P032 official July original receipt and original exact issuer PDF
  (SHA-256 9e421b2e6de480acfc7db7fb1f3b6aa1b4b125513c1cf2360ca34b8f0c3e1a6f).

## Revised Sambhv evidence, not earnings

| Company source fact | Verified issuer statement | What it does NOT prove |
|---|---|---|
| Q2 FY27 total sales volume | 122,662 tonnes, +24.19% YoY | Actual Phase-I steel commissioning, EBITDA, profitability per tonne or cash conversion |
| July 2026 warrant proposal | Up to 8,695,400 at ₹115, max ₹99.9971cr | All warrants actually allotted, currently issued and/or exercised |
| Due only upon full allotment | 25%, maximum ₹24.999275cr | Cash already credited to company bank |
| Due only upon full conversion | 75%, maximum ₹74.997825cr | Cash already raised for Q4FY27 planned plant commissioning |
| Warrant expiry | Up to 18 months **from actual allotment** | Known expiry date, if actual allotment date is missing |
| Proposed lead promoter-group recipient | Anjaneya Minerals 6,608,600 warrants, around 76.0011% | Actual promoter payment, share conversion, future performance or current FD count |
| Steel plus separate power gross capex | ₹810cr steel + ₹125cr power = ₹935cr, *if both required* | Project spend, debt funding, retained company cash or financing deficit |

Gross full-conversion proposed warrant issue would equal **10.69%**
of that historical combined project capex estimate, but proposed
25%-on-allotment money corresponds to only **2.67%**. Those figures
are **scenario ratios**, not confirmed financing adequacy.

The payment structure has a potentially material financing timing
mismatch: Q4FY27 target commissioning may occur before the
permitted 18-month warrant conversion window has expired.
Neither the actual allotment date nor cash realization is
verified; therefore no explicit conversion deadline,
future bank money or projected construction-financing shortage
may be invented.

## Model and acceptance

- Module: src/marketlab/hg007_sambhv_update.py
- CLI: scripts/build_hg007_sambhv_updated_underwriting.py
- Tests: tests/test_hg007_sambhv_updated_underwriting.py
- CI: .github/workflows/hg007-sambhv-five-case-refresh.yml

The exact original P030/P031/P032 source bytes, source receipt and
July board PDF are cryptographically pinned. The builder rejects
missing old company cases, amended original nominal payoff values,
changed original 25/75 consideration, false cash/EBITDA promotion and
any mismatch in the project's declared capex.

The entire revised **5-case, all-source-provenance** report is saved
append-only after successful main CI under:

research/hg007/hg007-p033-five-case-sambhv-source-timing-v1.json

## What remains unresolved

Actual post-shareholder warrant allotment date and bank receipt,
converted shares and 75% consideration, current warrants,
basic/FD share count, Q2 financial statements/EBITDA/FCF,
capital expenditure spend, commissioning, debt service and
existing market valuation. For the other four companies,
the original P030 evidence gates remain unchanged.

HG006 still publishes zero source-supported case-specific
transaction completion probabilities. No source qualifies for
a 50% share upside estimate, capital allocation, or a
portfolio-grade hidden-gem buy recommendation.
