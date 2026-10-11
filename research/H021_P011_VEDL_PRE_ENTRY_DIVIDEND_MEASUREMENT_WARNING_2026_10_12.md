# H021-P011: 12 October H021 Pre-Entry Dividend Return-Basis Warning

Status: **PUBLICLY ANNOUNCED CORPORATE-ACTION RISK, NOT A RETURN/ALPHA TRIAL**.
Original H021 selection snapshot 9 October 2026; source-risk protocol authored
before the planned Monday 12 October 09:15 IST next-open research proxy.

## Measurement issue

The frozen H021 first top decile includes VEDL, which announced a
first interim FY27 cash dividend of **₹5 per share** on **8 October 2026**.
Public corporate-action calendars report **14 October 2026** as the ex
and record date, just two calendar days after the planned 12 October
research entry. This is not hypothetical *forward earnings* and
must not be scored as another EPS revision.

Auditable public evidence (not yet an independently SHA-sealed
original NSE dividend disclosure):

- 8 October dated issuer-quoting report, ₹5 dividend/14 Oct record:
  https://www.businesstoday.in/markets/stocks/story/vedanta-approves-rs-5-interim-dividend-for-fy27-check-record-date-560377-2026-10-08
- Independent VEDL dividend ex/record date calendar:
  https://groww.in/stocks/vedanta-ltd
- The original issuer filing PDF and exchange cash-action record
  remain **not independently audited** under this P011 record.

## Scientific interpretation

The planned 12 October observed NSE opening price is **not a
filled market order**. It cannot by itself prove that a hypothetical
investor acquired the legal right to a cash dividend. The ex date,
actual entitlement, withholding tax, payout, corporate action and
share-status details must be source-reconciled.

A cash dividend can shift raw share price at an ex date. Comparing
VEDL raw-price movement to Nifty 500 PRICE INDEX does **not**
establish total economic shareholder return. The complete 20/60
completed-session corporate-action and dividend census must be
performed for **all ten names**, not just the one publicly
identified declaration.

Do NOT:
- remove VEDL from the first H021 cohort;
- change original 28–35-day EPS signal rank/cutoff;
- use the Oct8 dividend event to claim a successful future return;
- subtract ₹5 from an observed raw price or credit ₹5 to a fake
  broker holding without official entitlement/price adjustments;
- assume all other nine selected names have no corporate actions;
- declare total-return basis ready based on a single source.

This is a **known pre-entry measurement hazard**, not evidence that
VEDL is a better or worse investment.

## Reproducibility

- src/marketlab/h021_p011_dividend_alert.py
- scripts/build_h021_p011_dividend_alert.py
- tests/test_h021_p011_dividend_alert.py
- output:
  research/prospective/h021/pre-entry-risk/2026-10-09-vedl-dividend-alert-v1.json

The code compares byte-level Git hashes for the original H021
9 October selected ten, the original U001 universe, and the
original frozen comparison and calendar. It flags one
known secondary-reported dividend and leaves every original
selected identity untouched.

A GitHub workflow produces an append-only packet only
**before the 12 October 03:45 UTC planned open**, or leaves
a no-promotion diagnostic if the source-review process ran
after this deadline. The actual Git source-commit time, not
a claimed analysis date, determines chronology.

The separately merged H021-P010 full-horizon corporate-action
review requirement remains authoritative. Its outcome gate
is NOT cleared by this annotation.

Portfolio and live capital remain disabled; expected returns
remain uncalculated, and the 20/60 session windows must mature
before independent official evaluation.
