# HG009 P031: official NSE four-tier industry-source evidence

**Source collection method registered:** 2026-10-21.
**Research status:** source acquisition for a **different future trial**, not a revision to the 2026-10-15 300-company study.
**Investment recommendations and live capital:** none.

## Why the next experiment cannot begin with the old industry labels

The Oct15 frozen HG009 100 selected and 200 controls had matched only on historical liquidity. The first **unadjusted H1** selected-arm mean price change was -1.410336%, versus -1.268997% and -1.076299% for the one- and zero-lane arms. A method chosen after seeing that result cannot become the original study's pre-entry feature. PRs #505, #506, #508 and #509 correctly classify later sector analyses as **post-entry** and refuse retroactive causal sector-alpha statements.

On October 20, P030 found only 142 of the fixed 300 had exact symbol+ISIN industry matches in a later October 16 NSE index subset, with industry retrieval provenance not established as *before* the original entry. That produces only 46 selected, 43 one-signal, and 53 zero-signal matches, far below the **new future cohort requirements** of at least 90/100 per arm and 285/300 total.

## P031 source retrieval, no price labels

NSE Indices uses a **four-tier classification**, defined by the issuer's economic sector, sector, industry, basic industry and primary segment revenue. Original listed-company NSE equity quote payloads expose this structure through either legacy \`industryInfo\` or newer \`equityResponse[].secInfo\`. Unlike an index-constituent CSV, an individual issuer quote can cover a company outside Nifty 500. These APIs are web-facing and can be unavailable, rate limited or return a changed shape. We cannot invent data for failures.

- Freeze the original 300 symbols and ISINs from HG009 D001 and P001 unchanged.
- Fetch an exact **NSE quote-equity** record, verify EQ series plus original symbol and **ISIN**, all four nonempty classification levels, and actually observed UTC retrieval time **not before October 21**.
- Archive exact returned original JSON bytes as gzip with SHA-256 and a separate signed receipt. Retain original unverified 403/schema/ISIN failures as source receipts, with no company assigned an invented sector.
- Honor a small maximum-request budget, at least 750 milliseconds between issuer requests and stop a batch on access denial or rate limitation.
- Produce a source-only signed report with verified original industry coverage per arm. The 90% per arm and 95% overall thresholds are **necessary, not sufficient** for a separate future test.
- Keep the original quotes' market prices, market caps, free-float and returns **out** of the normalized industry records and any original Oct15 source feature. Even if a late quote is retrieved in October, it is **not proof** of the classification at the Oct15 opening.
- A new stock-entry cohort may only be registered **after** classification, market-cap/float/size, beta/risk, financial reporting regime, accounting quality, future source clock, and costs are separately verified and frozen before an independent new decision date.

The P031 implementation reuses the existing \`marketlab.nse.NSEClient\` and exact original 300-name cohort validators. Source paths reside under \`research/hg009/p031-industry/originals\`; actual request receipts under \`receipts/YYYY-MM-DD\` and the derived coverage under \`latest-status.json\`.

Run the offline test/replayer without HTTP:

    python scripts/capture_hg009_p031_industry.py --check
    pytest -q tests/test_hg009_p031_industry.py

Run only a **small source probe** when network access is permitted:

    python scripts/capture_hg009_p031_industry.py --max-symbols 5 --attempts 1 --pause-seconds 1.5

This method does not establish current company value, hidden-gem alpha, or a recommended portfolio. The original Oct15 H1 underperformance and original P030 sector gap remain historical facts.
