# HG007-P025: ANANTRAJ 48-Page Original Composite Scheme Text Custody

Status: **ORIGINAL PAGE SOURCING AND AUDIT PREPARATION, NOT ASSET/LIABILITY VALUATION**.
Prepared 11 October 2026 IST. Source price or event return outcomes remain closed.

## Why

HG007-P024 recovered the 48-page original issuer composite scheme PDF,
including the proposed Anant Raj Cloud merger into Anant Raj Limited and
subsequent data-centre/cloud undertaking demerger to Ashok Cloud.

The earlier model identifies a double-counting risk because both direct
distribution and parent-retained Ashok Cloud securities may belong to
the original listed shareholder through separate economic channels.
The actual transferred liabilities, contingent claims, share allocation
and effective date are still unverified.

Merely downloading the 48-page PDF is not a page-specific review of
what economic liabilities transfer. This stage creates that evidence
spine without inventing a cash/debt transfer or declaring completion.

## Source integrity and page custody

The exactly preserved source is:

- Issuer official investor page: https://anantrajlimited.com/investors
- Issuer original PDF:
  https://blob.anantrajlimited.com/anantraj/1785759469838-Composite%20Scheme%20of%20Arrangement.pdf
- Original source PDF SHA-256:
  76db08d6210360291e81ab7813302067acdb34206cd03561db1ce0ba7ffe528f
- Original size: 10,044,735 bytes
- Pages: **48**
- Original 48-page receipt:
  research/hg007/anantraj-full-scheme/original-source-v1.json

The extractor re-hashes **every individual page's exact source text**
against HG007-P024's independently retained original per-page SHA-256
and checks every page's original character count and 1-based locator.

It writes each page separately:

research/hg007/anantraj-full-scheme/page-text-v1/original-page-01.txt

through:

research/hg007/anantraj-full-scheme/page-text-v1/original-page-48.txt

The accompanying page-index-v1.json contains the original document SHA,
48 exact text SHA-256s, page labels, and a term-location index.

Keyword labels for debt, borrowing, liability, security, capital, record
dates and entity ownership are **search hints only**, not semantic facts.

Every original text file is append-only. Mutated PDFs, altered source
receipts, changed text-page order, wrong source byte hash and existing
conflicting page files stop publication.

## Next actual underwriting steps

Once P025 pages are retained, independently review the original clauses
on issuer-specific business transfers:

1. identify the *precise* data-centre and cloud undertaking definition;
2. distinguish transferred fixed assets/investments/intangibles, claims
   and operational liabilities from those retained by the listed parent;
3. isolate contingent liabilities, guarantees, taxes, leases, external
   borrowings and parent/subsidiary intercompany balances;
4. verify the appointed date versus the contingent effective date and
   final record date, approval sequence and court/stock-exchange status;
5. identify whether any annexure schedules actually quantify assets,
   liabilities and revenue/cash flows as opposed to granting open-ended
   vesting rights;
6. reconcile resulting and retained newco share classes with the frozen
   HG007-P022 double-counting look-through; only then construct a
   downside-tested source-based sum-of-parts.

This original text extraction **does not approve a legal scheme, make
an accounting valuation, assign a transaction completion probability,
calculate an equity price target or authorize trading**.

## Reproduce

Module: src/marketlab/hg007_anantraj_scheme_pages.py

CLI: scripts/materialize_hg007_anantraj_scheme_pages.py

Tests: tests/test_hg007_anantraj_scheme_pages.py

CI/source custody:
.github/workflows/hg007-anantraj-48-page-source-text.yml

The workflow runs on a PR and commits the 48 original separate page
texts with hashes only after a reviewed main merge. It keeps a source
artifact independently, and prospective stock/capital eligibility
remains disabled.
