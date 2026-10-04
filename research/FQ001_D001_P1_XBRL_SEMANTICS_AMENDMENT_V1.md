# FQ001-D001 P1 XBRL Semantics Amendment v1

Status: **FROZEN AFTER D001 SOURCE DIAGNOSTIC, BEFORE P1 RERUN**
Frozen: 2026-10-04
Return outcomes opened: no
Portfolio eligibility: disabled
Live capital: disabled

## Why this amendment exists

The first FQ001-D001 source-feasibility run completed without opening any return
outcomes or fitting any model, but failed the already-frozen coverage thresholds.

Authoritative first-run evidence:

- workflow run: 37178238198;
- artifact: 11293924321;
- panel SHA-256:
  `487218c747f0a17eed29d0024fd42214ec2b44eb908288b1eb6f92313d58786b`;
- same-basis parsed pair count: 49/100;
- complete six-metric rows: 0/100;
- ROCE proxy coverage: 49;
- CFO/PAT coverage: 49;
- accruals/average-assets coverage: 49;
- net-borrowings/equity coverage: 49;
- PPE-derived metric coverage: 0.

The failure exposed two deterministic parser-semantics defects. It did not expose
stock-return outcomes and therefore does not justify changing the economic metrics,
universe, period pair, or feasibility thresholds.

## P1 correction 1: year-end cash concept

D001 treated the following two XBRL concepts as interchangeable aliases:

- `CashAndCashEquivalents`;
- `CashAndCashEquivalentsCashFlowStatement`.

The raw NSE evidence shows that both concepts may coexist with different values. They
belong to different statement semantics and therefore must not be merged.

For FQ001 net-borrowings calculations, P1 uses only the balance-sheet concept:

`CashAndCashEquivalents`

`CashAndCashEquivalentsCashFlowStatement` is not a substitute and is ignored for this
metric.

## P1 correction 2: PPE purchase taxonomy

The D001 parser looked for generic PPE-purchase concept names that do not match the NSE
Integrated Filing taxonomy used in the downloaded FY25/FY26 XBRL documents.

The exact observed NSE concept is:

`PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities`

P1 adds this exact concept to the frozen PPE-purchase alias set. No substring search,
fuzzy matching, sign inference, or discretionary line selection is introduced.

The metric remains:

`abs(PPE purchases) / revenue`

and the cash-conversion-after-PPE metric remains:

`(CFO - abs(PPE purchases)) / PAT`.

## Deliberately unchanged

P1 does **not** change:

- the 100-name U001 universe;
- the FY26/FY25 period pair;
- same-basis filing selection;
- Consolidated preference;
- any of the six economic metrics;
- missing-value policy;
- the 70 same-basis-pair threshold;
- the 60 complete-row threshold;
- the 60-per-metric coverage threshold;
- portfolio or live-capital eligibility.

## Non-March financial years

The first run also found three filings where 2026-03-31 was not an annual-duration
context. P1 deliberately leaves those rows ineligible.

This amendment does not broaden the period selector after seeing coverage. Supporting
non-March financial years, if needed, requires a separately frozen source-extension
protocol based on each issuer's explicit financial-year endpoint.

## Interpretation boundary

P1 is a source/parser repair only. Passing P1 permits design of a separately frozen
quality scoring stage. It does not establish alpha, expected return, or portfolio
eligibility.
