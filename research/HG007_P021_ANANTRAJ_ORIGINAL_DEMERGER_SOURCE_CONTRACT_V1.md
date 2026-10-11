# HG007-P021: Original July 2026 ANANTRAJ / Ashok Cloud Scheme Sources

Frozen for scientific source review: **11 October 2026 IST**.
Status: **ORIGINAL FILE COLLECTION, NOT TRANSFERRED-ASSET VALUATION**.

## Why this matters for the hidden-gem experiment

The original frozen HG005-D003 Anant Raj transaction sensitivity is based on
the gross value of data-centre/cloud business, but it cannot determine the
incremental **economic value to listed-company shareholders**. The *actual*
proposal is not a simple distribution of 100% of an existing operating
subsidiary to direct public shareholders.

The listed parent proposes a one-for-one demerger entitlement **without
canceling its existing Ashok Cloud ordinary shares**. As of the July
subscription, the parent says it owns 100% of Ashok Cloud. Issuing new
shares directly to existing parent shareholders would create an additional
minority layer while the parent retains its own shareholding and
consolidation/control could continue.

**The economic value of one Anant Raj parent share plus any issued
Ashok Cloud direct entitlement is NOT the original Anant Raj business value
PLUS 100% of Ashok Cloud a second time.** Ownership look-through,
net liabilities transferred, issued newco share capital, newco
minorities and the cum/ex-demerger pricing convention are essential.

## Three exact original exchange PDF filings

These are separate events and must never be conflated:

1. **20 July 2026, Finance Committee rights subscription proposal:**

   https://nsearchives.nseindia.com/corporate/ANANTRAJ_20072026150454_Intimation_20072026.pdf

   Three pages. Parent proposed acquiring another **374,322,553**
   Ashok Cloud shares for **₹74,86,45,106**, each at ₹2 face value,
   increasing subsidiary shares from 250,000 to 374,572,553 after
   subscription. As of the proposed transaction, parent held 100%.

2. **21 July 2026, completed purchase of subscription shares:**

   https://nsearchives.nseindia.com/corporate/ANANTRAJ_21072026120301_Intimation_ACPL_Updates.pdf

   One page. Lists the 374,322,553 fully paid shares
   acquired and total ₹74,86,45,106 already paid.

3. **21 July 2026, proposed composite demerger press:**

   https://nsearchives.nseindia.com/corporate/ANANTRAJ_21072026190031_Intimation_Press_Release_21072026.pdf

   Four pages. Original page 4 states
   **one ₹2 Ashok Cloud share per one ₹2 Anant Raj share**
   on the future scheme's eligible record date. It also explicitly
   states that parent Anant Raj's existing Ashok Cloud shareholding
   will **not** be canceled and Ashok Cloud **will remain a subsidiary**.

   All exchange/shareholder/creditor/court approvals and the effective
   date remain conditional.

## Original-share baseline research caveat

Independent third-party 30 June 2026 shareholder table reports
**359,876,930** fully paid-up Anant Raj ordinary shares, and this also
equals HG005-D001's historical reported fully diluted source denominator
implied by ₹20,795.48840005 crore / ₹577.85.

However, that historical issued/FD count is **not** a prospectively
confirmed future *record-date* basic share count.

Even if it were unchanged, the hypothetical parent retained stake
would be 374,572,553 / (374,572,553 + 359,876,930) = approximately
**51%** of Ashok Cloud, with approximately 49% directly issued to
existing parent shareholders.

That is a conditional arithmetic scenario only. Scheme implementation,
record date, eligible shares, other securities, transfer/debt adjustments,
ownership, valuation, and any prospectively realized return remain
unverified.

## Source capture and integrity

- Python: scripts/acquire_hg007_anantraj_originals.py
- Tests: tests/test_hg007_anantraj_originals.py
- Workflow: .github/workflows/hg007-anantraj-originals.yml
- After all three official PDFs pass: original source SHA-256s, bytes,
  timestamps and exact PDF identities preserved under
  research/hg007/anantraj-july2026-originals/.

The collector only accepts the three hardcoded official NSE archive
URLs, refuses redirects, records access blocks without bypass, requires
exact PDF page counts and issuer/transaction numeric tokens,
and independently validates all original bytes before committing.
Partial failures stay explicit in run artifacts and cannot promote
transaction status.

## Independent next steps

1. Extract and audit actual original 3+1+4 PDF pages.
2. Obtain scheme's full schedules, net liabilities/assets/rights
   transferred, parent retained stake and beneficiary record-date.
3. Bind the most recent original NSE shareholding basic and fully
   diluted counts from the pre-scheme period, without lookahead.
4. Create a **double-counting-safe** economic look-through ownership
   bridge with explicit minority and control lines.
5. Quantify independently verified DC/cloud normalized EBITDA, FCF,
   capex, power, customer retention, debt and transferred working capital.
6. Only then propose separately preregistered SOTP scenarios at sourced
   valuation multiples, with full downside and a time/maturity horizon.

No portfolio position, target price, estimated completion probability
or verified capital is implied by P021.
