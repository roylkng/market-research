# H021-P013: Original VEDL Dividend Evidence Delta to Frozen P011

Status: **ADDITIVE POST-ENTRY SOURCE RECONCILIATION, NOT A STRATEGY REVISION**.
Prepared 12 October 2026. The original October 9 H021 signal and
October 12 planned next-session open were frozen before this step.

## Source chronology

There are two different, independently verifiable timestamps:

1. The original 8 October NSE announcement for VEDL's ₹5 FY2026–27
   first interim dividend was **publicly broadcast on October 8 at
   07:41:56 UTC**, and the original NSE announcement JSON was captured
   by the repository on **October 9 at 17:28:32 UTC**. The original
   PDF URL appeared within those archived, SHA-verified pre-entry
   source bytes.
2. The *original PDF bytes themselves* were fetched and sealed only
   on **October 12 at 04:50:15 UTC**, AFTER the predeclared NSE
   03:45 UTC first entry proxy. This later source verification is
   therefore not a claim that the PDF was read or captured before
   the first H021 price observation.

The exact original PDF is 464,755 bytes, SHA-256
abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364.

Original document:
https://nsearchives.nseindia.com/corporate/VEDL_08102026131108_SEIntimationOutcomeofBM1stInterimDividendsigned.pdf

Original source receipt:
research/prospective/h021/dividend-evidence/vedl-2026-10-08/source-receipt-v1.json

## Facts confirmed by the original issuer source

Vedanta's original one-page board letter confirms:

- ₹5 dividend per ₹1-face-value ordinary equity share;
- declared/approved on 8 October 2026 at 13:00 IST;
- issuer record date of 14 October 2026.

The board letter does not itself confirm the *ex-date*. The separate
exchange corporate-action calendar is needed for that, including
source bytes and data-release timing.

The original PDF does not prove trade execution, beneficial ownership
on record date, settlement eligibility, actual dividend cash payment,
or a consistent Nifty500 price-index-versus-total-return comparison.

## No post-hoc editing

The original pre-entry P011 warning was source-correct given its
evidence at that time:

research/prospective/h021/pre-entry-risk/2026-10-09-vedl-dividend-alert-v1.json

It contains a publicly known dividend alert but marks the original
PDF review as not yet complete. P013 MUST NOT rewrite that record or
quietly relabel it as pre-entry original-PDF-verified.

Instead P013 creates a new, separate, source-pinned evidence delta,
with both original immutable Git blobs and the real P012 original
PDF SHA. It adds source-verified declaration and record-date fields
to VEDL *in the new overlay only* while leaving the other nine
original names and their unknown corporate actions unchanged.

## Reproducibility

- Module: src/marketlab/h021_p013_dividend_reconciliation.py
- CLI: scripts/build_h021_p013_dividend_reconciliation.py
- Negative tests: tests/test_h021_p013_dividend_reconciliation.py
- Workflow: .github/workflows/h021-p013-dividend-risk-delta.yml
- Source provenance: exact Git blob for original P003 first intent,
  original P011 warning, original P012 source receipt, and original
  PDF SHA-256.

Run from the repository root:

    python -m scripts.build_h021_p013_dividend_reconciliation \
      --out /tmp/h021-p013-vedl-dividend-delta.json

After merge a main workflow appends its immutable result at:

research/prospective/h021/dividend-evidence/vedl-2026-10-08/reconciled-first-cohort-risk-v1.json

The original P003, P011 and P012 source files remain unchanged.

## Remaining true blockers

1. Original NSE corporate-action master confirming VEDL **ex-date**
   and interval-wide cash/split/bonus/rights/merger actions for
   ALL 10 selected stocks, not only one known announcement.
2. Real official post-close 12 October stock-open and Nifty500-index
   source evidence. A quoted opening price is not an executable trade.
3. For any eventual theoretical economic shareholder return, a
   preregistered cash-dividend entitlement/settlement convention,
   price-versus-total-return index baseline and costs.
4. The 8 November NSE Muhurat session and 2027 official calendar
   extension for 20/60-session maturity.
5. Prospectively matured independent monthly-equivalent H021
   cohorts, multiplicity-robust evidence and no hindsight re-ranking.

**No 20/60-session returns or capital allocation are authorized by P013.**
