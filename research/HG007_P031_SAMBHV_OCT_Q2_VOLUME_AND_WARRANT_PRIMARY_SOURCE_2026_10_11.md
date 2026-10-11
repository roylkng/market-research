# HG007-P031: Sambhv Original October Sales and Warrant Source Evidence

Prepared 11 October 2026 IST. **Issuer-reported operating volumes and a
warrant-monitoring appointment, not verified earnings, warrant exercise,
bank cash, a fully diluted valuation or a stock recommendation.**

## First-party source evidence

Two issuer-hosted copies of stock-exchange disclosures:

1. 2 October 2026, Q2 FY27 Sales Volume Update, two pages.
   https://www.sambhv.com/uploads/pdf/investors/investor-information/announcement/Sales-Volume-Update-Q2-FY-2026-27.pdf
2. 6 October 2026, CARE Ratings monitoring agency appointment for
   preferential issue of warrants, one page.
   https://www.sambhv.com/uploads/pdf/investors/investor-information/announcement/Monitoring-Agency-Appointment-for-Preferential-Issue-of-Warrants.pdf

The Company states that shareholders approved the relevant preferential
warrant transaction on 10 August 2026; the 6 October notice **appoints**
the monitoring agency. It does not independently establish that all
warrants were exercised, issued consideration was received as freely
deployable cash, the proceeds have been allocated as spent, or the
company's FD equity count.

Reported warrant-related issue proceeds: ₹99,99,71,000
= **₹99.9971 crore**. Do not label that amount confirmed net bank cash
or regard it as the present cash value of the expansion project.

## Source Q2 volume accounting

| Product segment | Q2 FY27 tonnes | Q1 FY27 tonnes | Q2 FY26 tonnes | YoY change |
|---|---:|---:|---:|---:|
| Structural pipes and tubes | 67,020 | 56,617 | 57,788 | +15.98% |
| Pre-galvanised (GP) coils and pipes | 32,126 | 29,814 | 20,207 | +58.98% |
| Stainless-steel coils | 14,445 | 14,760 | 11,567 | +24.88% |
| **Value-added subtotal** | **113,591** | **101,191** | **89,562** | **+26.83%** |
| Intermediate products | 9,071 | 6,580 | 9,206 | -1.47% |
| **Total sales tonnes** | **122,662** | **107,771** | **98,768** | **+24.19%** |

Source row arithmetic validates both the three-category subtotal
and final subtotal-plus-intermediates across all three quarter
comparisons. Q2FY27 total tonnes grew **13.82% QoQ**.

Sales tonnage growth is not identical to revenue growth,
average realization, incremental plant operating throughput,
utilization rate, EBITDA/tonne, EBITDA margin, collections or
free cash flow. Prices, production mix, captive sales, freight,
inventory movements and working capital could offset volume growth.

Also, a volume update for the quarter ended 30 September 2026
**does not prove commissioning** of the 0.36 MMTPA greenfield
capacity targeted for Q4FY27 in the separate August roadmap.

## The existing expansion funding constraint

Original HG007-P017 already documented that the Q4FY27 roadmap
contains **₹810 crore steel capex plus ₹125 crore for a separate
25MW captive-power project**, totaling ₹935 crore if both are
required in the illustrative operating scenario.

The new warrant monitoring notice refers to approximately ₹100cr
of issue proceeds; its actual exercise/receipt/utilization and
the remaining financing of ₹935cr construction cash needs
must be reconciled separately.

Do not simply subtract the whole ₹100cr from project capex, add it
to cash and add corresponding earnings: that would cause double
counting and could erase future issuance/dilution costs.

## Exact original source capture

Module and one-shot CLI:
scripts/acquire_hg007_sambhv_october_sources.py

GitHub workflow:
.github/workflows/hg007-sambhv-october-sources.yml

The workflow obtains only the two fixed HTTPS URLs, never
follows redirects or evades HTTP 403/429, validates first-page
issuer identity, filing date, source text/page length and every
reported quarter's figures, and retains original bytes and
SHA-256 page text/receipt data.

A partial or malformed issuer response is a **blocked source**:
the combined financial readout is not published unless both
original PDFs validate. Failed attempts are retained as Actions
artifacts. Successful original reports are immutably anchored in:

research/hg007/sambhv-oct2026-sources/

The machine-readable case report preserves exact PDF URL/hash,
capture time, reported tonnes, derived YoY/QoQ growth and the
unknown warrant/full-capex/FCF states, without an expected return.

## Mandatory next work

- Independant original visual/table-layout audit of the two
  issuer PDF pages before broad extraction or automation.
- Source-verified actual proceeds credited, cost and use of
  warrant funds, warrant strike/exercise dates and fully diluted
  equity classes.
- Audited Q2 revenue, recurring operational EBITDA, steel coil
  realized production and cash conversion.
- Actual Phase-I commissioning milestones, ₹810cr steel /
  ₹125cr power expenditure, debt/interest capitalized and
  future power cost saving evidence.
- Independently verified price/FD shares, downside and capital
  allocation before any probability-weighted investment thesis.

No HG002 selection, HG005 operating assumption, past stock
return, portfolio permission or live capital is changed by P031.
