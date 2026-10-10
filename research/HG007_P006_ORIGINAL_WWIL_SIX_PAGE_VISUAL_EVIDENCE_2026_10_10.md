# HG007-P006: Original WWIL Six-Page BSE Visual Evidence

Status: **Original page images reproducible and source pinned.**
Not a completed human visual/semantic due-diligence approval or equity valuation.

## Why this step is necessary

HG007-P003 independently captured exactly the BSE 7 October 2026
INE510W/INOXGREEN original PDF. P004 locked its six page texts by SHA.
P005 checked the financing and BTA statements against those pages.

PDF text extraction can miss table column associations, annotations,
signatures or overlaid source images. To complete a defensible review we
must be able to visually inspect every original page at a legible size.

## Reproduction

The code accepts only the exact previously recorded PDF byte SHA:
541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451.

It re-verifies the original P004 page-text hashes before invoking Poppler
for a grayscale PNG rendering of each original page. The output is six
ordered 1600-pixel-max grayscale PNG images and a manifest recording:
- exact original PDF SHA-256
- corresponding independent text-page SHA-256
- exact PNG content SHA-256
- page number, image dimensions and byte count
- visual-semantic-review-complete = FALSE

GitHub Actions retains an independent run artifact. After merging, it
commits original page images and their manifest under
research/hg007/wwil-bse-original/page-render-images/ exactly once.

## Required manual inspection

Review all six pages, especially:
- page 1: NCLT approval, extension to Oct 8, Oct 6 payment and still
  conditional BTA legal business transfer.
- page 2: precise source/recipient identity of ₹250cr subscribed
  equity, ₹200cr group loan and ₹100cr Authum outside financing.
- pages 3-4: ₹250.01cr issued capital, 25cr ₹10 face-value shares
  issued at par, parent 100% ownership as of reporting date,
  historical Vibhav nil turnover versus WWIL target cash flow.
- page 5: parent facility unsecured, subordinate, 12% contractual
  interest, repayment after prior senior debt, optional conversion
  up to ₹50cr principal plus accrued interest under unknown pricing.
- page 6: 25 September parent loan agreement, lender/borrower,
  exact ₹200cr outstanding and disclosed security.

A human analyst still must separately approve the original-page layout
and source-term semantics; automatically rendering pages does not
verify the BTA legal close, Authum instrument terms, acquired WWIL
income or diluted parent value.

## Code

- scripts/render_hg007_wwil_original_pages.py
- tests/test_hg007_wwil_original_visuals.py
- .github/workflows/hg007-wwil-original-page-renders.yml

All prospective outcome, probability, recommendation, portfolio and
live-capital privileges remain DISABLED.
