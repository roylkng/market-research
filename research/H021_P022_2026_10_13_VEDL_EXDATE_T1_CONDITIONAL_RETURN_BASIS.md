# H021-P022: Preregistered VEDL 14 October Dividend Return-Basis Hazard

Status: **OUTCOME-BLIND, RESEARCH-ONLY**, prepared after 13 October 2026
cash-market close and **before Wednesday 14 October 2026 ex-date open**.

## What changed since the first H021 decision

H021-P003 froze its first ten candidate names on 9 October, before the
next official 12 October open. VEDL was selected under the unmodified
28-day percentage EPS-revision rule.

All source facts below are already durably present:

- Original issuer 8 October dividend declaration, first publicly
  broadcast before selection/entry: INR 5 per VEDL share; record
  date 14 October.
- Original NSE corporate action row acquired 12 October after
  entry-session close: **ex-date 14 October 2026**, **record date
  14 October 2026**, EQ series and same listed ISIN.
- Original official 12 October H021 entry-source packet: ten
  stock opening prices plus NSE Nifty 500 price index, including
  VEDL 265.95 INR official open as a measurement proxy, not
  actual executable fill.
- Original official 13 October post-close H021 cash-market
  source: all ten original EQ rows, including VEDL.
- The original frozen NSE calendar explicitly includes 12, 13,
  and 14 October as consecutive ordinary cash-market sessions.

All six source artifacts are verified against exact immutable Git
blob hashes. The original EPS rank, source prices and intent are
not rewritten.

## Settlement and the entitlement *conditional*

NSE Clearing's public capital-market equity settlement policy
states the normal settlement cycle is **T+1**, excluding settlement
holidays and allowing for delivery shortages:

https://www.nseclearing.in/clearing-settlement/capital-market/settlement-cycle

The normal corporate-action ex/record-date explanation under T+1
distinguishes buying **before** the ex-date from buying on it:

https://support.zerodha.com/category/console/corporate-actions/ca-others/articles/what-does-ex-date-and-record-date-mean

This gives the following **counterfactual paper-only scenario**:

| Scenario event | Date | Interpretation |
|---|---|---|
| Original precommitted H021 next-open proxy | 12 Oct | Official stock price is not evidence of an actual buy |
| Ordinary T+1 delivery date *if* a buy executed | 13 Oct | Candidate settlement date, not verified demat credit |
| Last cum-dividend regular market session | 13 Oct | Conditional eligible trade date under ordinary T+1 |
| Official NSE ex-date and issuer record date | 14 Oct | Ex-dividend price begins, entitlement determined |

A normally executed and settled hypothetical 12 October buy, held
through the required period, would ordinarily be *eligible for* the
declared INR 5 dividend. This does **not** prove that a participant
could fill at the NSE official open, completed settlement occurred,
any such account held VEDL, or actual dividend proceeds were paid.
No trade or portfolio exists in this experiment.

This paper scenario is **conditional**, not an observed corporate
cash return. There could be a clearing/settlement exception or
short delivery and no independent depository or broker evidence.
The public T+1 web documentation has not been independently
frozen into the original NSE source hash ledger.

## Mathematical and statistical safeguards

- Ex-date share prices and the INR 5 dividend are **not** blended
  into an unapproved price/total-return calculation.
- The frozen H021 20- and 60-session outcomes remain unopened.
- A fall in VEDL's ex-dividend raw price must not be automatically
  scored as realized investment underperformance or alpha.
- Nifty 500 **price index is not Nifty 500 TRI**; stock cash
  dividend/instrument adjustments must be treated coherently
  with benchmark and precommitted holding-interval conventions.
- The other nine H021 companies' corporate action/date/cash
  coverage remains independently required. One VEDL ex-date
  audit cannot certify the complete basket.
- The unresolved 8 November Muhurat and official 2027-session
  calendars still block full 20/60-session exit certainty.
- No realized return, capital allocation, fill, order,
  prospective re-ranking or 50%-annual-return prediction
  is generated.

## Reproducibility

- Model: src/marketlab/h021_vedl_settlement.py
- CLI: scripts/reconcile_h021_vedl_exdate_settlement.py
- Tests: tests/test_h021_vedl_settlement.py
- Workflow: .github/workflows/h021-vedl-pre-ex-settlement.yml

Once merged, the workflow stores a deterministic source-hashed report:

research/prospective/h021/dividend-evidence/vedl-2026-10-08/conditional-t1-exdate-v1.json

The exact Git receipt provenance makes any attempted alteration of
the original P003 decision, source session, issuer amount, NSE
ex-date or review packet fail closed.

**No portfolio eligibility or live capital is authorized.**
