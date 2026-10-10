# HG007-P004: Original BSE PDF Page-Text Custody for WWIL/Vibhav

Created 10 October 2026 IST. This is **source text extraction**, not independent
economic semantic approval or a recommendation to purchase INOXGREEN.

## Exact original

The original BSE attachment was fetched in HG007-P003, retained in Git and
independently identified by the same SHA-256 as the earlier SS002 October
company-event pilot:

- 541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451
- Original bytes: 354,999
- Filing: Inox Green Energy Services Limited, 7 October 2026
- Subject: Wind World (India) Limited O&M undertaking acquisition and
  proposed funding of Vibhav Energy Private Limited.

P003 establishes bytes/URL/timestamp, not the completeness or semantic
correctness of translated page text.

## Extraction rules

Reuse the existing deterministic SS002 PDF page extractor from the
original raw bytes in the repository. Reject changed SHA-256, changed
P003 source receipt, mismatching SS002 document ID, failed/empty page
extractions, displaced page locators or any source that does not look
like the same issuer, filing date and underlying WWIL transaction.

Retain every extracted page as an individual explicit page-numbered
record, with exact text and SHA-256. No summary replaces the original.

The extracted source pages are written to:

research/hg007/wwil-bse-original/original-page-text-v1.json

No approval, expected return, source adjustment factor or investment
ranking is assigned by this step.

## Independently re-run and inspect

Run scripts/extract_hg007_wwil_original_pages.py with --out
/tmp/wwil-original-pages-v1.json and --print-pages.

The post-merge source workflow prints each page with an unmistakable
PAGE N locator to GitHub Actions logs, retains an artifact and commits
the deterministic full-page JSON to Git. Source changes or existing
conflicting page packets block publication rather than overwrite.

## Remaining reviewer obligations

1. Inspect exact page contents, including annexures, to match each
   amount and condition to its actual economic issuer/borrower.
2. Distinguish disclosed proposed conversion from completed conversion,
   and cash consideration paid from legal BTA transfer completed.
3. Reconcile the amount, security classes, interest, subordination,
   maturity, collateral and conversion price with the original text.
4. Inspect page images wherever layout or signatures make text
   ambiguous. Text extraction does not alone constitute visual approval.
5. Obtain additional original terms/financial statements where the
   filing does not provide normalized WWIL EBITDA, working capital,
   minority control rights or actual legal transfer completion.

Current company-specific completion probability surfaces remain
unpublishable; no capital or portfolio permission is granted.
