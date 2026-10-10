# HG007-P005: Reviewed Original 7 October WWIL/Vibhav Source Terms

**Snapshot 10 October 2026. Original PDF textual paragraphs and annexures
reviewed, but page-image visual review and independent investment diligence
remain pending.**

## Original source

- Original BSE filing for Inox Green Energy Services Limited / INOXGREEN,
  dated 7 October 2026.
- Exact original 354,999-byte PDF SHA-256:
  541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451.
- All six page texts were re-extracted using the same deterministic PDF
  parser as the earlier SS002 pilot, verified against their six independent
  page SHA-256s and anchored in
  research/hg007/wwil-bse-original/original-page-text-v1.json.
- Their identity matches the earlier SS002 original document ID, but the
  earlier extraction's full independent semantic approval is **not** hereby
  granted. This audit covers only the listed issuer's disclosed claims
  visible in text.

## Exact, bounded issuer-source findings

**Page 1: legal stage.** The NCLT approved the consortium's resolution
plan on 27 July 2026. The IMC extended the previously discussed
implementation period to **8 October 2026**. Vibhav executed the BTA
and, on **6 October**, paid the full **₹550 crore** amount toward the
WWIL O&M purchase. The same page still states that the O&M business
transfer is conditional on satisfaction of the BTA conditions precedent.

These are issuer statements; no completed transfer/effective date
certificate was found in this six-page filing. Passage of 8 October
alone proves neither completed transfer nor cancellation.

**Page 2: money and actors.** INOXGREEN contributed ₹450 crore to its
wholly owned purchase vehicle Vibhav, comprising **₹250 crore subscribed
equity** and **₹200 crore intercompany deposit**. Authum supplied
**₹100 crore in a separate outside intercompany deposit**. Together
these reported funding amounts equal ₹550 crore.

Authum's proposed future equity/securities conversion is mentioned,
but its actual coupon, ranking, maturity, security class, conversion
price and effective shareholding consequences are **not** provided
in Annexure B, which only covers INOXGREEN's own facility.

**Page 3: distinguish subsidiary and acquired business.** Vibhav had
**₹250.01 crore paid-up equity** after the new allotment.
Vibhav's FY26 historical turnover was **nil**. That is **not** a
statement that WWIL's acquired O&M operation had no turnover.
The page's 'no government/regulatory approval required' disclosure
concerns the internal subsidiary equity subscription; it does not
erase the BTA conditions precedent required for WWIL's transfer.

**Page 4: equity already issued.** Vibhav completed its allotment to
INOXGREEN of **25 crore equity shares at ₹10 face value at par**,
total ₹250 crore. INOXGREEN held 100% of Vibhav equity as of the
filing before proposed future outside equity/securities conversion.

**Page 5: parent intercompany lending economics.** The ₹200 crore
INOXGREEN-to-Vibhav loan is unsecured and subordinate to WWIL
restructured debt and other third-party debt. It cannot be repaid
until that debt has first been repaid. Contractual interest is
**fixed at 12% per annum**; repayment is a bullet on a mutually agreed
date. An amount **up to ₹50 crore principal together with accrued
interest MAY be converted** into Vibhav equity/securities later, on
mutually agreed terms. It is not an unconditional requirement to
convert exactly ₹50 crore at par.

The naive nominal coupon arithmetic is
₹200 crore × 12% = **₹24 crore per year**, before any conversion.
It is only a contractual intercompany interest illustration:
actual accrual/payment, recoverability and senior-debt constraints
are unverified. Intragroup coupon income is **not** independent
consolidated group EBITDA or shareholder cash inflow.

**Page 6: formal loan identity.** Lender INOXGREEN, borrower Vibhav;
₹200 crore unsecured loan; agreement date **25 September 2026**.
There is no verified fixed maturity or evidence that proposed
convertible principal has already become equity.

## Corrections to the earlier provisional HG007-P002 bridge

- Earlier shorthand saying ₹50 crore 'is to be converted' must be
  corrected to **optional up to ₹50 crore plus accrued interest,
  on mutually agreed terms**. Confirmed actual conversion = no.
- A simplified **75% parent / 25% outside** diluted ownership result
  is **not established by this filing**. It can only be presented
  under an explicitly hypothetical future ordinary-share, at-par
  capitalization assumption. Original Authum instrument pricing,
  securities class and actual conversion remain unknown.
- Completed parent equity subscription is not completed BTA transfer.
  Neither the parent subscription's approval field nor the
  NCLT consortium approval overrides separate WWIL BTA conditions.
- Vibhav's nil historical revenue is not WWIL O&M carve-out EBITDA.
  Acquired business profitability, cash conversion and 4.5 GW
  contract-level economics are **not audited by this filing**.

## Current underwriting gates, not a stock recommendation

Immediate missing originals to obtain:

- Subsequent filing explicitly confirming BTA conditions precedent and
  effective date, or latest extension/cancellation.
- Full WWIL O&M carve-out P&L, maintenance capex, retained client
  contracts, receivables and post-acquisition cash flows.
- Executed parent intercompany facility agreement and Authum loan
  agreement, with all conversion prices/class, accrued interest, loans'
  priority and consent/restriction rights.
- Latest subsidiary cap table plus INOXGREEN post-QIP diluted shares,
  debt, treasury cash, related-party loans and minority rights.
- Independent page-image review wherever signatures, scanned images or
  tables make original text extraction ambiguous.

The pre-existing HG006 survivor-conditioned completion model has **no
publishable current-company probability**; do not assign one based on
stage narratives or 8 October's former deadline.

## Reproducibility and limitations

- Source anchor and assertions:
  src/marketlab/hg007_wwil_terms_review.py
- CLI: scripts/reconcile_hg007_wwil_original_terms.py
- Test: tests/test_hg007_wwil_terms_review.py
- Generated source fact packet:
  research/hg007/wwil-bse-original/reconciled-issuer-terms-v1.json

The machine-readable artifact contains **only issuer-filing-sourced
statements and explicitly annotated arithmetic**, not independently
validated WWIL actual business cash flow, fair market value, a
completion probability or a trading signal.

**Portfolio eligibility and live capital remain disabled.**
