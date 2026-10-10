# HG007-P019: Original NPST Q1 FY27 Investor/Reg32 PDF Page Source Custody

Status: **ORIGINAL ISSUER PDF PAGES CAPTURED; FINANCIAL TABLE SEMANTICS PENDING**.
Recorded 11 October 2026 IST.

## Exact original inputs

The HG007-P018 source workflow successfully obtained, verified and
hash-retained the following two original BSE PDF attachments:

- 11 Aug 2026 NPST Q1 FY27 investor presentation, period ended
  30 June 2026: 22 pages, 4,868,023 bytes, original SHA-256
  5afd8b272e7bd2f7f3fad549aa1270e4899e1d24c8d982268cab16a17bbe2225
- 11 Aug 2026 NPST Reg32 June use-of-proceeds statement:
  3 pages, 6,447,208 bytes, original SHA-256
  79010c968b0fe8359f685d27a203c891a8e35f684a73b86a67cf78ee46b54013

Both were matched against the original issuer and June reporting
period and are permanently source-retained under:

research/hg007/npst-aug2026-originals/

A third 11 Aug BSE attachment indexed in one source as a March
monitoring-agency report was fetched as an 11-page original candidate.
The captured text mentioned the June quarter but did not supply
the required March date tokens. The issuer/date inconsistency is
**unresolved**, and the candidate is retained in its original
GitHub Actions run artifact, not silently imported or reclassified
as March or June monitoring proof.

## This P019 step

Reparse the first two exact original PDF SHA-256 source files.
For each page preserve:
- 1-based original PDF page index,
- exact original UTF-8 extracted text,
- SHA-256 of exact page text from HG007-P018 capture,
- issuer original PDF SHA-256,
- literal keyword snippets with source page locator.

Keyword snippets guide the independent review to locations where
EBITDA, cash funds, utilization, allocation and unutilized
balances may be discussed. They are **not** approved numerical
facts or a free pass to apply an earnings multiple.

Fail closed if source bytes, original receipt Git blob, P018 page
hashes, selected reporting quarter, page count or original issuer
identity change.

Reg32 table structure and accounting meaning still require
independent visual/source review, especially if numbers represent
proceeds raised, cash deposited, paid expenses or changed
allocation objects.

## To reproduce

    python scripts/extract_hg007_npst_original_pages.py \
      --out /tmp/npst-original-June-pages-v1.json \
      --print-matches

The post-merge workflow emits this page text to a source-only Git
artifact and appends once to:

research/hg007/npst-aug2026-originals/june-original-page-text-v1.json

Neither missing third monitoring file nor future company
earnings are filled or inferred from this extraction.

## Investment-research gates remain closed

The earlier frozen HG005 mechanical NPST reverse hurdle:
₹61.42562125 crore incremental annual EBITDA at an illustrative
30x for 50% hypothetical value uplift. This is not a forecast,
expected share return or current company value.

Before promoting an investment case require:
- verified original Q1FY27 normalized EBITDA and annual comparability;
- original current unutilized funds and schedule of uses, plus
  prior-quarter monitoring chronology correctly classified;
- independently verified cash conversion, receivables and
  deployment-to-incremental earnings;
- full diluted count, actual execution price, corporate actions,
  financing, debt and downside scenarios;
- valid cross-company alpha/multiple-testing and prospective
  outcome evidence, without retroactive selection.

No portfolio permission or live capital is enabled.
