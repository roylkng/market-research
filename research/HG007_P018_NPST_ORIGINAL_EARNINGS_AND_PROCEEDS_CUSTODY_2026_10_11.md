# HG007-P018: NPST Original June Quarter Earnings and Capital-Deployment Filing Custody

Status: **SOURCE RETENTION ONLY, NO SEMANTIC APPROVAL OR STOCK FORECAST**.
Prepared 11 October 2026 IST. The existing mechanically selected HG002
28-company research cohort and HG005 valuation-hurdle selection are unchanged.

## Why the original sources matter

NPST is in HG004's procedural live financing/capital-deployment review
and among the five HG005 company-specific mechanical payoff cases.
The frozen HG005-D003 reverse hurdle states that an *illustrative*
50% listed-equity-capital-uplift at 30x would require
**₹61.42562125 crore additional annual EBITDA**.

Recent market-data summaries refer to a reported ~₹300 crore fundraising
program, around ₹264.36 crore reportedly unused on 30 June 2026 and a
Q1 FY27 company quarterly EBITDA around ₹18.79 crore. These figures
are secondary leads until the original listed-company filings, units,
consolidation basis, use-of-proceeds classifications and retained
amounts are independently reconciled.

An unutilized fundraising balance is **not** an accrued operating profit.
Equity proceeds already collected may be held as cash or invested, and
raising funds dilutes existing shareholders. A 30x EBITDA scenario is
not credible without proving earnings persistence, parent-attributable
free cash flow and post-allotment diluted shares.

## Exact original document identities

Three BSE original regulatory attachments were identified from the
11 August 2026 announcement index:

1. **Q1 FY27 Investor Presentation**, financial period ended June 2026:
   https://www.bseindia.com/xml-data/corpfiling/AttachLive/5fab053f-1334-4b70-8ba7-4325e7f07b2e.pdf
2. **Regulation 32 Statement of Variation and Use of Funds**, June
   quarter ending **30 June 2026**:
   https://www.bseindia.com/xml-data/corpfiling/AttachLive/0f52b8e1-9062-4b5a-be7c-ef0206f32489.pdf
3. **Monitoring Agency Report**, available 11 August 2026 but covering
   the **March 31, 2026** quarter, NOT June:
   https://www.bseindia.com/xml-data/corpfiling/AttachLive/32b88b70-da2a-4109-8187-d3a51bb7b860.pdf

The date of announcement must not be mistaken for the financial
reporting period. A March 31 monitoring report cannot independently
verify June 30 unspent proceeds.

## Fixed source-custody protocol

- Collector: scripts/acquire_hg007_npst_originals.py
- Regression: tests/test_hg007_npst_originals.py
- Workflow: .github/workflows/hg007-npst-original-source.yml
- Original successful files: research/hg007/npst-aug2026-originals/

Only the exact fixed BSE URLs are permitted. No login workaround,
redirect or alternative document host is accepted. HTTP 401/403/429
is recorded immediately as blocked rather than converted to 200 or
circumvented. HTTP 200 HTML is rejected as a PDF.

On an apparently valid PDF the collector checks original PDF byte
envelope, total page count, extractable text-page hashes and whether
the issuer name and correct reporting-period text are actually
present. Content is retained under exact SHA-256 with receipt
timestamp, URL, page count and reporting family.

A retrieved PDF with an unreconciled issuer or period is preserved
only in the GitHub run artifact, **not** promoted to the immutable
source-reviewed file. Original-source PDF custody is not equivalent
to complete accounting semantic approval or actual profitability.

The workflow tries each distinct attachment independently, keeps
block/no-access artifacts and anchors only passing documents to Git
without overwriting an existing successful original. It runs once
on merge, with bounded October follow-up and manual re-run support.

## Mandatory follow-on review before NPST payoff

1. Original Q1 consolidated versus standalone revenue, operating
   EBITDA and cash-flow reconciliation. Verify whether the
   ₹18.79 crore reported quarterly measure is exact and comparable
   to the HG005 annual incremental EBITDA hurdle.
2. Original Reg32 utilization schedules, opening balance, issued
   proceeds, purposes, source cash balance and recipient entities.
3. Separate March monitoring report's prior period from *current
   June reporting*: no silent quarter substitution or forward fill.
4. QIP/preferential/warrant conversion, fully diluted shares and
   any promoter lock-in or related-party funding.
5. Use of capital to incremental contracted income, revenue
   recognition, renewal/counterparty dependency, receivables,
   working-capital needs and maintenance investment.
6. Attributable earnings to the existing ordinary share base,
   explicit downside and annualized return-cost sensitivity.
7. Verify source/exchange timestamp against market price snapshot.

All 28 original HG007 companies, H021 research experiments and
statistical alpha-trial ledgers stay unchanged. No return prediction,
valuation target, stock recommendation, portfolio eligibility or live
capital is authorized here.
