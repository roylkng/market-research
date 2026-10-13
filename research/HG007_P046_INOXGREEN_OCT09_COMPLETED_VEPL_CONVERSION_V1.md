# HG007-P046: INOXGREEN/VEPL Oct9 Completed Equity Allotment, WWIL Transfer Still Unknown

Frozen review: 13 October 2026 IST. Classification: **COMPANY
TRANSACTION-STAGE RECONCILIATION, NOT A REVISED RETURN PREDICTION**.

## Why this matters

The previously frozen HG007-P002 and HG007-P005 source analyses relied on
the **7 October** INOXGREEN BSE filing: the listed company had provided
₹250 crore VEPL equity plus a ₹200 crore intercompany loan; Authum had
loaned ₹100 crore; VEPL was then wholly owned by Inox Green. Future
ICD conversions were not yet completed as of that document.

An **independent original NSE 9 October filing** has now been retrieved,
hash verified and published in:

research/hg007/wwil-oct09-vibhav-conversion/

Original SHA-256:
12a0a512c279ee6580120b82346bc85c1720c4ae0e5959edd9b7d3225e9b898f

Original NSE PDF:
https://nsearchives.nseindia.com/corporate/IGESL_09102026233918_IGESL_SE_Vibhav_WOS_intimaiton_dsc.pdf

## Reported completed corporate step

On **9 October**, VEPL converted ₹150 crore of already-funded ICDs into
₹10-face-value shares:

| Investor | Prior funding converted | VEPL shares issued |
|---|---:|---:|
| INOXGREEN | ₹50 crore | 5 crore |
| Authum | ₹100 crore | 10 crore |
| **Total** | **₹150 crore** | **15 crore** |

VEPL paid-up capital rose from **₹250.01 crore** to **₹400.01 crore**.
The issuer now explicitly states Inox Green holds **75%**, Authum **25%**.
VEPL ceased to be wholly owned, but remains an Inox Green subsidiary.

The new shares are **noncash conversion of existing deposits**.
Neither parent nor outside investor transferred another ₹150 crore in
cash at conversion. The prior ₹550 crore cash payment toward the WWIL
O&M purchase remains a distinct event.

## Absolutely critical distinction

- **Completed:** VEPL equity allotment and dilution on 9 October 2026.
- **Not proven completed:** the underlying transfer of WWIL's acquired
  O&M business under the BTA. The 7 October filing explicitly states
  completion depends on BTA conditions precedent, and the 9 October
  subsidiary-allotment filing does not close those conditions.

The 9 October announcement was reported after NSE cash-market hours.
The original PDF itself has an October 9 document date but does not
independently provide an authenticated first broadcast timestamp.
This research therefore **does not backdate** the notice into a
9 October preclose stock-decision signal.

The mathematical ₹150 crore residual on Inox Green's earlier ₹200 crore
intercompany deposit is an arithmetic implication of converting ₹50 crore
principal. It is NOT an independently reconciled current
post-conversion loan/interest/settlement balance.

The 12% rate in the prior parent ICD Annexure B must not be
extrapolated to all future outstanding subsidiary liabilities without
a new original contract/interest reconciliation.

## Impact on subsidiary consolidation and equity payoff

Inox Green continues to **control** VEPL, allowing consolidation
subject to actual IFRS/IndAS conditions and group accounting, but
there is now a **25% third-party equity interest** in VEPL. Any
shareholder-attributable earnings or residual enterprise value model
must evaluate non-controlling interest. It cannot simply assign
100% of any future WWIL O&M free cash flow to listed INOXGREEN owners.

The September 29 listed-parent shareholding report gave
422,070,138 diluted parent shares, first public 8 October; this
does not certify the diluted share count as of **13 October**.
No new listed-company shares were reported from VEPL's separate
subsidiary equity conversion.

## Code and reproducibility

- src/marketlab/hg007_vibhav_conversion_stage.py
- scripts/reconcile_hg007_oct09_vibhav_conversion.py
- tests/test_hg007_vibhav_conversion_stage.py
- .github/workflows/hg007-vibhav-conversion-stage.yml
- report after merge: research/hg007/hg007-p046-28-case-vibhav-conversion-stage-v1.json

All source contracts are Git-blob-SHA-pinned. The original 28
mechanically selected candidate identities and existing HG005/HG006
payoff and probability evidence remain immutable. The new status is an
as-of **separate overlay** rather than an alteration of historical
facts.

## Mandatory next evidence

1. Original WWIL BTA condition-by-condition legal completion or effective-date
   certificate. Subsidiary equity allotment is not that certificate.
2. Standalone acquired WWIL O&M normalized EBITDA/FCF, maintenance capital,
   renewable offtaker contracts, receivables and retention/churn.
3. Authum original **10 October** counterparty notice and its separate
   ₹350 crore resolution-plan obligation, mapped to the correct assets.
4. Original remaining parent ICD covenant/interest/accrual records and
   Authum third-party rights. Avoid double-counting intragroup cash.
5. Listed INOXGREEN current fully diluted shares, pledged promoter
   collateral details, consolidated debt and minority interest.

No completion probabilities, stock price targets, expected returns,
portfolio positions or live capital are authorized by this reconciliation.
