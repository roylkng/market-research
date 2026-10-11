# HG007-P032: Sambhv 25/75% Warrant Cash-Realization and Dilution Boundary

Frozen before actual source acquisition: **11 October 2026**. A new, explicit
source-contract experiment over the **original July 15 2026 issuer board
proposal**, not a retrospective adjustment of the original HG002/HG005 scores.

## Critical missing distinction

The company's October 6 monitoring-agent notice refers to **₹99.9971
crore issue proceeds**. That number cannot be treated as already
available company bank cash to fund the newly announced steel or power
projects. The issuer's original 15 July board resolution makes the
warrant economics contingent on **actual allotment and later exercise**.

Source of record:

https://www.sambhv.com/uploads/pdf/investors/investor-information/announcement/Outcome-of-Board-meeting-of-July-15-2026-for-Raising-of-Funds.pdf

The five-page original issuer PDF reports:
- Up to **8,695,400** fully convertible warrants.
- Price **₹115** for each equity warrant.
- Maximum stated gross consideration **₹999,971,000 = ₹99.9971 crore**.
- One ordinary ₹10 face value equity share per warrant.
- **25% of price on actual warrant subscription/allotment** and
  remaining **75% on actual warrant-to-equity exercise**.
- Maximum 18 months **from the date of actual warrant allotment**,
  not 15 July board approval or 10 August shareholder approval.
- Unexercised warrant subscription money to be forfeited after expiry.
- Seven proposed warrant allottees. One promoter-group entity,
  Anjaneya Minerals Private Limited, is proposed **6,608,600**
  warrants, around **76.00%** of the overall proposed count.
  The other six receive 347,800 proposed warrants each.

This is a **proposal and potential cash obligation**, not necessarily
completed allotment, bank proceeds or present shares outstanding.

## Conditional cash stages

Assuming, strictly hypothetically, **100% warrants are first allotted**:

| Cash stage | Scenario cash, ₹ crore | Trigger |
|---|---:|---|
| 25% subscription on allotment | **24.999275** | Only with actual allotment and cash receipt |
| 75% later on exercise | **74.997825** | Only with actual exercise/ordinary-share allotment |
| Maximum total if all exercised | **99.997100** | Neither stage is verified as bank cash today |

If **zero warrants** were actually allotted, then the warrant proposal
creates **zero** realized bank cash. The October monitoring-agency
appointment and August shareholder approval do not change that fact.

The frozen HG005 scenario already modeled fully converted
**8,695,400 shares**, from original **294,671,429** reported fully
diluted reference shares to a **303,366,829** pro-forma denominator.

The old capital-base is **not verified current fully diluted shares**.
Pro-forma issuance may create roughly 2.95% extra shares relative to
that old denominator *if fully exercised*, not an immediate realized
ownership change. Warrant proceeds may also have already been
allocated, restricted or used, even when paid.

## Compare to plant funding, without presuming allocation

Original August issuer roadmap separately described:
- Phase-I steel coils: **₹810 crore**.
- 25 MW captive power: **₹125 crore**.
- Gross combined project reference: **₹935 crore** if both required.

Full hypothetical gross warrant proceeds cover **10.695%** of that
gross combined reference. Arithmetic difference: **₹835.0029 crore**.

**This is not a funding deficit or evidence that the company lacks
capital.** Other funding sources, existing capex payments, operating
cash, debt, reallocation, staged spend and warrant use restrictions
must be sourced before forecasting actual financing needs. Nor should
the same ₹99.9971 crore be counted both as cash-on-hand and as a
capex reduction on top of newly issued share dilution.

## Source-bound acceptance

Provenance sources already existing in the repository:
- Original HG005 Oct1 company financing context Git blob
  2dbbc3055d1aacec8a37dd510a1a75a3c7868006.
- Original P017 steel + captive power roadmap Git blob
  1dbb0ddaa6243b6afe79746906f214c4cc422461.
- Original P031 October Q2 sales and CARE appointment Git blob
  4f6c9df119250e9a29efa432570bb00f386d1614.

The P032 workflow fetches **only the fixed original company URL**,
does not follow redirects, does not evade 401/403/429, requires exactly
five legible PDF pages and verifies the exact legal/cash/convertible
clauses and allottee count on the correct pages. It records the
original byte-level SHA-256, page text hashes and capture UTC
timestamp, preserving the unmodified PDF in Git.

It does not accept a synthetic invoice, unrelated PDF, secondary
article or October monitoring-agency reference in place of the actual
15 July issuer source.

Build after original source acquisition:

    python scripts/acquire_hg007_sambhv_july_warrants.py \
      --out-dir /tmp/hg007-p032-source

A successful anchored result will appear under:

research/hg007/sambhv-july2026-warrant/

GitHub Action:
.github/workflows/hg007-sambhv-warrant-cash-stages.yml

Tests:
tests/test_hg007_sambhv_warrant_cash_tranches.py

## Outstanding event and valuation gates

- Original post-shareholder-approval notice that documents **actual
  warrant allotment date/count, allottee, 25% realized money**, if any.
- Original later conversion/exercise and **75% additional consideration**
  collection evidence, if any, with revised share register.
- Current diluted share count, capex banking/monitoring reports, actual
  capital deployment and borrowing/interest/covenants.
- Q2 FY27 revenue, recurrent EBITDA per realized tonne, FCF, new
  Phase-I commissioning and separate power-plant savings.
- Exact conditional project funding, consolidated cash/debt, taxes,
  share dilution and downside valuation.
- Mature prospective outcomes for a falsifiable alpha hypothesis.

This P032 record **does not** assert a currently known allotment,
exercise, promoter cash transfer or investment opportunity.
All probability, expected-return, selection and live-capital gates
remain disabled.
