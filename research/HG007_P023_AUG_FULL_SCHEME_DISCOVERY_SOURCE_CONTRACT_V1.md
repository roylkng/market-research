# HG007-P023: Discover Official Full Composite Scheme Source, without Inventing URLs

Status: **PUBLIC OFFICIAL LISTING DISCOVERY ONLY**, not full scheme
acquisition, legal approval, transferred-liability valuation or alpha.
Frozen source-validation contract 11 October 2026.

## New published primary source that matters

NSE's official [Scheme Document listing](https://www.nseindia.com/companies-listing/corporate-filings-scheme-document)
names **Anant Raj Limited**, and shows a **17 August 2026** upload
whose displayed attachment size is about **35.58 MB**, plus a
15 September complaint report.

That is substantially more comprehensive than HG007-P021's verified
three July source PDFs, and may contain the proposed demerged
undertaking's exact assets, liability allocation, schedules and
share entitlement terms. Its actual content has NOT yet been verified.

Anant Raj's official
[investor page](https://anantrajlimited.com/investors)
also lists 'Composite Scheme of Arrangement', 'Pre and Post
Shareholding Pattern', 'Share Entitlement Report', 'Fairness Opinion
Report' and other original source families.

**Neither page justifies guessing an archive filename.**

## Source-safe discovery

The P023 probe fetches only two exact HTTPS pages:

- https://anantrajlimited.com/investors
- https://www.nseindia.com/companies-listing/corporate-filings-scheme-document

It captures original HTML byte hashes, request UTC timestamps,
HTTP status, no redirects, and independently preserves original
HTML bytes if the direct public page responds.

The parser lists only candidate PDF links exposed in actual original
HTML anchors or literal server-rendered HTML/JSON, and only on the
known issuer, BSE or NSE official PDF hosts. A candidate requires
some associated scheme, issuer or arrangement context.

Crucially, **every PDF candidate has source identity verification
and original-PDF SHA verification set to false**. A missing link is
explicitly not a missing official scheme. The page may load its
attachments client-side and the source can be otherwise accessible.

HTTP 401/403/429 and redirects are retained as failures without
workarounds. The probe never silently follows an alternate domain
or manufactures a scheme document URL.

## Operations and evidence

- Probe: scripts/discover_hg007_anantraj_full_scheme.py
- Tests: tests/test_hg007_full_scheme_discovery.py
- Main/dispatch workflow:
  .github/workflows/hg007-anantraj-full-scheme-discovery.yml
- Output: append-only official HTML/source manifest under
  research/hg007/anantraj-full-scheme-discovery/attempts/
  with run-specific identifier; GitHub artifacts preserve
  the original independent capture as well.

The P023 manifest deliberately retains:

    aug17_35_58mb_scheme_pdf_original_bytes_retrieved = false
    scheme_schedules_assets_liabilities_reconciled = false
    nclt_effective_scheme_verified = false
    portfolio_eligibility_allowed = false
    live_capital_allowed = false

## Next evidence gate

If a verified original official PDF URL is present:
- independently request exactly that posted 17 Aug document;
- verify content-type, PDF envelope, original SHA, issuer,
  title, actual source dates and full PDF page count;
- retain original bytes under SHA-256 and append a source receipt;
- inspect the exact definition of demerged undertaking, its
  assets, liabilities, inter-company debts, encumbrances,
  contracts, capex and any schedule of audited segment assets;
- reconcile the 1-for-1 entitlement with existing parent-retained
  subsidiary shares, issued classes and the actual record-date
  eligible share count.

If no direct URL is present in the HTML, the data source is
**DISCOVERY_INCOMPLETE**, not 'scheme nonexistent' and not
approval. The next research step would resolve the client-rendered
listing or obtain the full filed copy directly from issuer relations
under its official document family.

The original P022 51/49 ratio is an explanatory *conditional*
ownership scenario only, with no value or legal-completion claim.
No equity expected return or buy recommendation can be built from
the proposal without full scheme and transferred liabilities.
