# RM001: December 7 NSE cash / derivatives clock transition audit

**Reviewed:** October 21, 2026. **Source:** official [SEBI Oct 15 circular HO/47/11/11(3)2025-MRD-POD2/I/23843/2026](https://www.sebi.gov.in/legal/circulars/oct-2026/review-of-certain-aspects-of-the-closing-auction-session-market-timings-and-settlement-methodology-for-derivatives-contracts_105293.html). [Original SEBI PDF, seven pages](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1792079571420.pdf), paras 4.2, 4.9 and 6. The complete original SEBI PDF bytes have **not** been archived under this repo. NSE implementation SOP still needs source verification.

## Impact on scientific measurements

Beginning **December 7, 2026**, the SEBI cash-market Closing Auction Session will operate **15:30–15:40 IST**, and final closing auction prices may only be published after the random close / order matching. The frozen NSE FY27-Q2 calendar marks normal session closes at **15:30 IST**, too early to prove a completed post-transition CAS closing price.

Derivative settlement follows a separate clock and price basis:
- Stock derivatives trade until **15:45 IST** including expiration.
- Index derivatives ordinarily trade until **15:45 IST**, but expiring index derivatives cease at **15:30 IST**.
- Stock and index derivative expiry settlement is based on the **last 30 minutes of underlying cash continuous-trading VWAP**, NOT the final CAS close.
- Remaining iceberg/limit order transfer changes start only **February 8, 2027**, not December 7.

The new rules apply only to covered instruments, including phase-one CAS-eligible F&O stocks in cash. That stock eligibility must be verified from actual NSE source documentation for each session. Not all HG009 original 300 companies should be assumed to have the CAS close regime.

## What the code actually does

The RM001 CAS future module computes a **forward-only 18-session conflict list** using original frozen NSE FY27Q2 calendar SHA-256 2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce. From December 7 to 31, the old calendar's 15:30 UTC-converted close timestamps are not sufficient to prove final CAS quotes. The 15:40 timestamp is a **conservative full-order-window elapsed reference**, not the earliest physically possible publication time. SEBI permits random order-entry closure between 15:38 and 15:40, after which matching and dissemination can commence. The code requires instrument-kind and independently confirmed CAS stock eligibility. When unknown, it blocks inference rather than guessing. It reports derivatives expiry timing separately from auction price.

Importantly: **nothing in the original calendar, T012, H002, H021, HG009, PF001 paper fund, historic decisions or source ledgers is amended**. The code is a pre-transition risk auditor only. A timestamp at or after 15:40 is at most a lower bound for auction order-entry completion, NOT evidence of final dissemination or of a fill.

Run with:
    python scripts/audit_rm001_cas_future.py
    pytest -q tests/test_rm001_cas_future.py

Before post-Dec7 research predictions depend on a new clock, freeze a separate NSE/SEBI operational-source-backed future regime, append justified source/methodology preregistrations, verify original eligibility and actual data publication, and independently source the calendar through 2027. See issue #521. **Live capital remains disabled**.
