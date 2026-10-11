# HG007-P026: Exact Anant Raj / Ashok Cloud Demerger Debt and Asset Clauses

Reviewed 11 October 2026 IST against the originally retrieved **48-page**
issuer composite scheme. **This is a proposed scheme, not confirmation
of court sanction, shareholder entitlement, transfer balances or stock value.**

## Fixed original document

Issuer original 48-page PDF:

https://blob.anantrajlimited.com/anantraj/1785759469838-Composite%20Scheme%20of%20Arrangement.pdf

Original source PDF SHA-256:

76db08d6210360291e81ab7813302067acdb34206cd03561db1ce0ba7ffe528f

P025 independently reproduced **all 48 pages** with each page's UTF-8
original text, page number, length and SHA-256 in:

research/hg007/anantraj-full-scheme/page-text-v1/

P026 independently pins that exact page index and the earlier P022
conditional ownership scenario. Every extracted legal clause below
has its original human 1-based PDF page, SHA and precise anchor.

## Economic issues now unambiguously identified

### 1. Asset scope includes financing cash and potential QIP proceeds

- PDF pages 6-7, clause 1.13: the cloud undertaking includes the data
  centre business of Anant Raj Limited and Anant Raj Cloud Private
  Limited after the ARCPL amalgamation, and broadly associated
  permits, IP, contracts, customers, receivables and employees.
- **Page 7:** the definition expressly includes amounts raised,
  received, earmarked or allocated by ARL to invest in, expand or fund
  the data-centre business, **including proceeds from QIPs or other
  capital raises used for that purpose**.

This may shift cash assets as well as operating assets into Ashok
Cloud. **Neither the rupee amount of earmarked QIP proceeds nor actual
transfer of the cash is quantified by this clause.** Do not keep that
same money on ARL's balance sheet while adding it a second time in
Ashok Cloud valuation.

### 2. External debt allocation is potentially material

- **Page 7, clause 1.13(viii):** obligations arising from operating
  the demerged undertaking, and loans used solely for its activities,
  are included.
- **Page 8, clause 1.13(viii)(c):** general/multipurpose borrowings
  may be allocated in the proportion of transferred asset values
  relative to total ARL/ARCPL asset values immediately before the
  appointed date.
- **Page 8:** the boards may resolve whether disputed assets,
  obligations and liabilities pertain to the demerged undertaking.
- **Pages 31-32, clauses 21.14 and 22:** relevant intercompany
  parent/resultant obligations cancel, while business obligations
  vest in Ashok Cloud subject to the actual scheme and conditions.
- **Page 33, clause 23:** pre-existing asset encumbrances can follow
  the affected assets, rather than disappearing.

Therefore the cloud business is NOT source-proven debt-free. The
actual loan-level transfer, asset-ratio inputs, external charges,
guarantees and remaining consolidated debt are all unknown.
An authorized scheme clause is not a transferred-debt balance sheet.

### 3. Two economic claims, but no free extra company

- **Page 37, clause 28:** the proposed resulting-company allotment is
  one INR 2 Ashok Cloud equity share for each eligible INR 2 ANANTRAJ
  share. The existing ARL-owned Ashok Cloud shares are expressly
  **not cancelled**, and eligible shareholders retain their ARL
  shares.
- **Same page:** the ratio may be adjusted for intervening capital
  changes, including convertible instruments.
- **Page 41, clause 30:** the resulting company's proposed
  **authorized**, not issued, capital is 734,449,483 INR 2 equity
  shares, nominal INR 146.8898966 crore.

The number 734,449,483 happens to equal the original P022 simplified
conditional capitalization:

374,572,553 existing parent-held newco shares
+ 359,876,930 illustrative historical old ARL share proxy
= 734,449,483 shares.

This supports internal consistency of the **draft capital capacity**,
but DOES NOT verify the future record-date share count, final issuance,
ratio adjustment, voting/control, effective rights or valuation.

Counting the same Ashok Cloud business as 100% stand-alone cloud
equity PLUS 100% parent retained cloud value would double-count it.

### 4. Proposed accounting, not a fair-value mark-up

- **Pages 41-42, clause 31:** the parent reduces the transferred
  undertaking's standalone assets/liabilities/reserves at carrying
  values; Ashok Cloud uses common-control pooling-of-interests book
  accounting, and the related intercompany balances are cancelled.
- **Page 48, Annexure A:** the proposed undertaking identifies two
  immovable locations: CP-1 in IMT Manesar and TP-1 in Industrial
  Estate Rai, Sonipat.

A list of two plots is not evidence of their market value, debt-free
ownership, occupancy, sanctioned data-centre power, data-centre
capacity or current cash generation.

### 5. Scheme is still conditional

- **Page 6:** record date is to be fixed mutually by boards.
- **Page 8:** the effective date is the first day of the month after
  the month in which clause 37.1 conditions occur.
- **Pages 45-46, clauses 37-38:** exchange no-objections, required
  shareholder/creditor majorities, tribunal sanction, ROC filings
  and other applicable consents must be satisfied before effect.
  Failure can lead to amendment or cancellation.

There is no legal basis to claim the scheme already completed
merely because this 48-page proposed draft was publicly filed.

## What the code proves and deliberately does NOT

Reproducible, source-pinned P026 review stores every bounded clause,
its actual page locator/hash, and the exact prior P022 conditional
ownership file identity.

It explicitly leaves **null**:

- transferred operating asset and land value;
- QIP cash, bank accounts and other funding transferred;
- directly attributable and allocated general-purpose debt;
- contingent guarantees, taxes and lender charges;
- actually canceled intercompany balances;
- cloud/data-centre carveout EBITDA or free cash flow;
- effective date and record-date actual basic shareholder count.

The model does not create an approved newco capitalization, company
completion probability, enterprise value, price target, upside or
alpha trial.

## Next critical documents

1. Management-audited **undertaking-wise balance sheet** and
   loan-by-loan direct/general allocation, including QIP cash use.
2. Annexure A title, liens and external facility documents for both
   listed immovable locations.
3. Separated ARL real-estate versus newco cloud audited revenue,
   power expenditure, data-centre capex, debt service and FCF.
4. Exchange/SEBI no-objection, court NCLT approval, credit consents,
   final capital schedule, actual record/effective date and listing.
5. Holdings/tax/legal ownership look-through reconciling both ARL-
   retained and directly issued Ashok Cloud shares.

## Code and evidence

- src/marketlab/hg007_anantraj_scheme_terms.py
- scripts/audit_hg007_anantraj_scheme_terms.py
- tests/test_hg007_anantraj_scheme_terms.py
- .github/workflows/hg007-anantraj-clause-audit.yml
- resulting immutable, source-verified:
  research/hg007/anantraj-full-scheme/p026-clause-review-v1.json

**No investment recommendation, return probability, or capital
authorization is justified by a proposed corporate demerger scheme.**
