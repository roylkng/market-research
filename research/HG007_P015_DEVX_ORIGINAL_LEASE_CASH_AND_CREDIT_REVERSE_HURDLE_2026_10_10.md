# HG007-P015: DevX FY26 Lease-to-Cash-EBIT and October Credit Risk Audit

Status: **source-verified financial-quality diagnostic only** (10 October 2026).
Hurdle/stock selection unchanged. Not an equity forecast or investment order.

## Source authority and independent cross-check

The original 34-page 20 May 2026 Dev Accelerator Ltd investor
presentation filed with NSE and original 8 October 2026 Acuité credit
report are both preserved in the GitHub repository (P013/P014).

NSE source:
- URL: https://nsearchives.nseindia.com/corporate/DEVACCE_20052026134050_SE_Investors_Presentation.pdf
- Original exact PDF SHA-256:
  2a3c319d7965a0c3c8602b65b6375bf5af63c0689dd5455ad05478724901a2a7
- Original bytes: 5,537,004; 34 pages.
- Page 28 (human 1-based) is the issuer FY26 **standalone**
  IndAS and IGAAP reconciliation with all relevant cash/rental rows.

Acuité:
- URL: https://connect.acuite.in/fcompany-details/DEV_ACCELERATOR_LIMITED/8th_Oct_26
- Exact original HTML SHA-256:
  958e9f33b27d2299b6e49ae5cfbdaf042bd6f9248481ab1e5cadc21429876333
- Original bytes: 87,503, original textual content independently SHA
  matched to the previously source-retained receipt.
- Date: 8 October 2026, credit BBB / Stable.

The first two sources are independently original SHA-pinned and
the historical HG005-D001/D003 market/payoff JSON Git blobs
must reproduce byte for byte. Any changed original, PDF page
text/issuer, Acuité ratios or original HG005 hurdle fail closed.

## Hidden failure mode in naive 15x incremental EBITDA

Source: FY26 issuer **standalone** earnings, in INR crore.

| Metric | FY26 reported |
|---|---:|
| Revenue from operations | 170.91 |
| IndAS EBITDA | 103.46 |
| EBITDA margin | 60.53% |
| Lease rental cash outflows | 66.92 |
| Cash EBIT | 36.55 |
| Cash EBIT margin | 21.39% |
| Lease interest | 27.20 |
| Right-of-use asset depreciation | 50.24 |

The issuer's approximation reconciles:
103.46 - 66.92 ≈ 36.55 (rounding difference 0.01 crore).

FY26 cash EBIT is **only ~35.33%** of headline standalone IndAS
EBITDA under this *historical company-wide accounting mix*.
The lease rental cash outflow corresponds to ~64.68% of
standalone EBITDA.

The direct subtraction does NOT claim free cash flow:
- property fit-out/maintenance capex, working capital and taxes
  still matter;
- debt principal and third-party interest are separate;
- IndAS right-of-use liabilities belong in a consistent EV bridge;
- the company includes nonworkspace subsidiaries in consolidated
  accounts, which should NOT be mixed with standalone ratios.

HG005-D003's original prospective Winston reverse hurdle is
**₹11.847268466 crore incremental annual EBITDA**, at an
**illustrative 15x EV/EBITDA** with 50% gross-equity-equivalent
market-cap uplift. This is an unchanged historical *reverse hurdle*,
not a future earnings prediction or stock target.

As a diagnostic only, if future Winston revenue, rent and EBITDA
happened to have the exact FY26 standalone business-wide cash EBIT
conversion, then an incremental ₹11.85 crore of INDAS EBITDA
would translate arithmetically into about **₹4.19 crore cash EBIT**.

If, under the *same hypothetical historical ratio*, the 11.85 crore
requirement instead referred to cash EBIT, the necessary accounting
EBITDA would be about **₹33.54 crore**.

These are **NOT** alternate investment predictions:
- the future 450,000 sq.ft. Winston is a separately signed straight-lease
  centre, not verified income from 450,000 currently occupied sq.ft.;
- its negotiated cash rent, fit-out, refundable deposit and occupancy
  could differ drastically from existing property portfolio averages;
- a 15x IndAS EBITDA enterprise multiple is not equivalent to
  a 15x cash EBIT or post-debt free cash-flow multiple;
- 3.15 lakh sq.ft. Capital One was operating and 8.1 lakh sq.ft.
  development-management pipeline was signed on distinct models.
  These distinct stages and lease/capital structures cannot be pooled
  into realized net revenue without source proofs.

## The 8 Oct creditor review changes balance sheet risk

Original creditor report states:
- ACUITE BBB / Stable on *₹100 crore* rated NCDs, issued Aug 4, 2026,
  with coupon 11.75% and August 2029 maturity.
- An additional ₹50 crore NCD funding is **proposed**, not
  confirmed issued at the same rate.
- Reported consolidated FY26 debt/EBITDA **3.11x including
  lease liabilities**, versus **1.32x excluding them**.
- Approximately 46% FY26 revenues linked to Ahmedabad and region.
- September operating portfolio 1.13 million sq.ft.,
  17,294 seats, versus earlier May presentation ~0.83 million
  sq.ft. FY26 footprint. This is a *date-specific scale update*,
  not proof that Winston itself became operational.
- Credit report mentions a closure following a fire in one centre
  affecting Q1 FY27 performance.
- Cash/deposits discussed by Acuité are qualitative creditor
  liquidity context, not unrestricted cash and final DEVX net debt.

The nominal annual simple coupon on the ₹100 crore August NCD issue
is ₹11.75 crore, **not FY26 historical interest**. The proposed
₹50 crore issue does not receive an invented coupon rate, draw date
or guarantee of completion.

Higher growth may still create shareholder value. But new external
debt, rent-commitment duration, geographic concentration and signed
but not producing centres create downside paths that a gross 15x
EBITDA-uplift shortcut omits.

## Practical gate before underwriting equity upside

Next mandatory issuer-level original documents:
- dated Winston site handover, lease commencement, rent-free period,
  tenant occupancy and contracted realized annual cash rent;
- Winston-specific capitalized and cash-fit-out capex, deposits,
  working capital, tenant receivables, operating maintenance costs;
- latest consolidated lease liabilities, debt maturity, net unrestricted
  cash, associate sale cash actually received, NCD amortization
  and covenant schedule;
- independently verified current shares including warrants/ESOP;
- fully lease-consistent enterprise value and FCF margin sensitivity,
  downside for 12/24-month commissioning delays or sub-target occupancy.

**No return prediction, stock target, fund investment or portfolio
eligibility** is authorized by this diagnostic.

## Reproduction

- Original-backed checker: src/marketlab/hg007_devx_lease_economics.py
- CLI: scripts/build_hg007_devx_lease_bridge.py
- Tests: tests/test_hg007_devx_lease_economics.py
- Workflow: .github/workflows/hg007-devx-lease-cash-bridge.yml

The machine-readable full report is anchored, after green CI, at:
research/hg007/devx-originals/lease-cash-credit-gate-v1.json.
