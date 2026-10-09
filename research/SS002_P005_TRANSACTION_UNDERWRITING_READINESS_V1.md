# SS002-P005 Transaction Underwriting Readiness Gate v1

Status: **FROZEN BEFORE P005 MATERIALIZATION**
Frozen: 2026-10-10 (Asia/Kolkata)
Capital deployment, target prices, expected return and portfolio authority: disabled.

## Purpose

Route every one of the eight source-bound SS002-P004 recent NSE document pilot cases into
a *research* evidence-gap queue. This is a deterministic bridge between LLM fact extraction
and family-specific valuation/red-team work, not a new alpha factor.

## Immutable input

- `SS002-P004-NATIVE-8DOC-v1`;
- GitHub run `37985254672`, artifact `11642638177`;
- pilot SHA `03d8ae16dd642e8e107b62bdb03eb9dc7e178d0327d742586bc35b65de943ff3`;
- canonical summary: `research/ss002-p004-native-result-v1.json`;
- 8 cases, 8 structurally validated, 0 independently semantically audited.

Every input row is retained exactly once. The model's page-cited terms and caveats
may be used for attention routing only. They are not a certified valuation input.

## Frozen precedence order

1. Economic relevance UNKNOWN => `SOURCE_VISUAL_REVIEW`.
2. Economic relevance PROCEDURAL_OR_NEWSPAPER_UPDATE => `PROCEDURAL_MONITOR`.
3. Stage TRANSACTION_COMPLETED => `COMPLETED_EVENT_IMPACT`.
4. Family ACQUISITION_INVESTMENT => `ACQUISITION_DUE_DILIGENCE`.
5. Family BUYBACK => `TENDER_BUYBACK_DUE_DILIGENCE`.
6. Family RIGHTS_ISSUE => `RIGHTS_DILUTION_DUE_DILIGENCE`.
7. Family SCHEME_REORGANISATION => `SCHEME_DUE_DILIGENCE`.
8. Any other row => `MANUAL_TRANSACTION_REVIEW`.

The order is fixed to avoid treating completed or procedural events as fresh
arbitrage opportunities.

## Mandatory evidence families

Every case requires independent semantic review of the original PDF pages, dated
point-in-time issuer/security identity reconciliation, current financial/capitalization
source validation, liquidity/risk review and a separately frozen underwriting model
before an investment conclusion.

Additional family evidence:

- Tender buyback: record/eligibility date, applicable offer/tender timetable,
  shareholder acceptance range, post-tender residual security downside,
  official price at entry, share-capital baseline and tax/fees.
- Rights issue: entitlement value/renunciation, all payment calls, issued/fully paid
  share denominator, promoter participation, use of proceeds, official entry price.
- Acquisition: target independently verified revenue/EBITDA/cash conversion,
  assets/liabilities and contingencies, legal close status, financing/covenants,
  integration economics and minority interests.
- Scheme: exact share exchange/valuation reports, group/related-party shareholding,
  creditor/shareholder votes, court/regulatory approvals and pro-forma liabilities.
- Completed event: distinguish historical capital/share count/cash realization from
  a new actionable catalyst; verify cash/tax and post-event capitalization.
- Procedural update: find original transaction terms before any economic inference.
- Unreadable source: visual/original document review, never infer absent terms.

No assumed probabilities or risk scores are filled from the LLM narrative.

## Acceptance

- exact P004 source SHA, eight cases, unique document IDs;
- every original P004 case retained;
- 8/8 semantic audit states remain pending;
- no case gets `underwriting_ready=true`;
- no case gets `portfolio_eligibility_allowed=true` or live-capital authorization.

P005 readiness is only a triage output. Later independent approval and
scenario valuation must be separately versioned and reviewed.
