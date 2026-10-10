# HG007-P013: DEVX Lease/Earnings and Credit Source Custody

Status: **SOURCE ACQUISITION ONLY, no equity valuation and no live capital**.
Research planning date: 2026-10-10 IST.

## Why this matters more than a simple 15x EBITDA uplift assumption

HG005-D003 froze a reverse hurdle: 50% stock-capital uplift at a 15x
illustrative EV/EBITDA multiple would require roughly INR 11.847 crore
of incremental annual EBITDA for the Winston 450,000 sq.ft. project.

This **does not** show that INR 11.847cr will be earned, nor that the
same metric is available to shareholder debt service or dividends.

Dev Accelerator Limited's May 20, 2026 NSE-filed FY26 investor
presentation reports, on the *standalone* accounting basis:

- FY26 revenue from operations INR 170.91 crore.
- FY26 **IndAS EBITDA INR 103.46 crore**, margin 60.54%.
- FY26 **Cash EBIT INR 36.55 crore**, margin 21.38%.
- Annual lease liability rental cash outflows INR 66.92 crore.
- Its Winston 450,000 sq.ft. straight-lease pipeline was signed Q4,
  but actual occupied area and Winston-specific revenue/EBITDA
  were not provided as realized earnings.

The mechanical identity FY26 EBITDA minus lease rent cash outflow,
103.46 - 66.92 = 36.54 crore, reconciles the approximate reported
36.55 crore cash EBIT at the rounding level.

**Critical accounting concern:** IndAS 116 lease accounting removes
rent expense from EBITDA while recognizing right-of-use depreciation
and lease interest elsewhere. Applying a cash/lease-excluding EV
multiple to IndAS EBITDA without the corresponding lease liability,
cash conversion and capital bridge overstates economic upside.

## New independent 8 October 2026 creditor evidence

Original Acuité Ratings & Research report:

https://connect.acuite.in/fcompany-details/DEV_ACCELERATOR_LIMITED/8th_Oct_26

Key creditor-reported points:

- Rating **ACUITE BBB / Stable**, reaffirmed on INR 100 crore listed NCDs.
- Two NCD tranches of INR 25 crore and INR 75 crore (INR 100 crore total) shown in the annexure with August 4
  2026 issuance, **11.75% annual coupon** and August 4 2029 maturity.
- INR 100 crore NCD issue completed in August 2026, a further
  INR 50 crore proposed, NOT issued as of review.
- FY26 debt/EBITDA **3.11x including lease liabilities** and
  **1.32x excluding lease liabilities**, as stated by rating agency.
- Operational portfolio expanded from 0.83 msf to **1.13 msf
  and 17,294 seats** by September 2026, versus the originally
  frozen March/May fiscal-year context.
- About 46% of FY26 revenue derived from Ahmedabad, where a large
  part of the signed development pipeline is concentrated.
- Cash INR ~39 crore as of Sept 29 2026 and about INR 34 crore in
  security deposits, with qualitative caveats about availability.
- Its FY27 Q1 revenue softened partially due to a centre closure
  after a reported fire.
- Cash coverage and debt maturity remain independent underwriting
  gates. The rating is a credit opinion, NOT assurance of
  shareholder capital gains.

The exact original NSE investor PDF and original independent
Acuité HTML are sought on their fixed URLs. They are not replaced
with secondary analyst quotes.

## Source protocol

- Original NSE FY26 PDF:
  https://nsearchives.nseindia.com/corporate/DEVACCE_20052026134050_SE_Investors_Presentation.pdf
- Credit report: above original Acuité issuer rating URL.
- Source-only client: scripts/acquire_hg007_devx_originals.py
- Source tests: tests/test_hg007_devx_originals.py
- Workflow: .github/workflows/hg007-devx-original-earnings-credit.yml

No redirect following, cookie/evasion bypass or substitute unaudited
domain. The collector checks a 34-page NSE PDF and bounded
first-party issuer and financial/date identifiers, and independently
the creditor's exact issuer/rating, lease-liability metrics and
Oct 8 date in HTML.

Each original is retained unchanged and content-addressed by
SHA-256. A successful original byte capture is NOT a final
financial-semantic audit or investment recommendation. If either
source is absent, the complete bundle is not falsely promoted;
the GitHub run still preserves explicit missing receipts as
an independent CI artifact.

On successful publication, original source files are stored under:

research/hg007/devx-originals/raw/sha256/

## Next analytic protocol, not silently folded into HG005

After exact original bytes and source SHA are anchored:

1. Reconstruct FY26 IndAS EBITDA, lease rental, cash EBIT and finance
   costs on the same standalone basis. Verify source-page identity.
2. Reconcile September credit rating, completed NCD and currently
   proposed financing separately. An issuance cannot be counted as
   both unrestricted cash gain and free funded capex.
3. Build a fully lease-consistent Winston hurdle with realistic
   timeline, occupancy, fit-out, deposits, rent outflows and EBITDA
   under one accounting basis; preserve original H005 hurdle.
4. Avoid combining 8.1 lakh sq.ft. developmental management pipeline,
   4.5 lakh Winston straight lease, and 3.15 lakh operational Capital One
   as three immediately operating indistinguishable assets.
5. Only then consider a fresh, dated downside/base/upside
   incremental FCF rather than treating signing as completion.

Any resulting cases must remain observed-earnings and
source-verified-financing gates, not expected-return claims.
Neither source alone establishes net enterprise value, legal
project readiness, dilution or an executable stock recommendation.
