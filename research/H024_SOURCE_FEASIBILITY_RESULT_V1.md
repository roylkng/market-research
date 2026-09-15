# H024 source-feasibility result v1

Status: **SOURCE GATE PASSED WITH ONE EXPLICIT SOURCE-BLOCKED FILING**

Outcome data inspected: **no**

Live capital: **disabled**

## Scope

This result closes the pre-outcome source/parser gate for H024 direct insider market purchases.

The audited official source family is NSE Regulation 7(2) PIT-GG discovery plus approved NSE archive raw XBRL.

Audit window: 2026-05-01 through 2026-09-15.

## Discovery feasibility

The official PIT-GG discovery feed produced:

- 2,558 total disclosure rows;
- 2,506 eligible Regulation 7(2) Original/Revision raw-XBRL documents in the full audit;
- precise `broadcastDateTime` and `exchdisstime` exchange timestamps;
- raw XBRL and iXBRL archive references;
- Original/Revision labels;
- revision remarks when supplied.

`prevAppId` is not sufficiently populated to serve as a required revision-linkage key, so H024-v1 uses the pre-frozen conservative same-symbol pre-entry revision rule.

## Full raw-XBRL audit

Exploratory full-audit report:

- branch: `research/h024-insider-source-probe-v1-20260915`;
- report path: `research/probes/h024/nse-pit-xml-full-corpus-audit-v2.json`;
- Git blob SHA: `78287cdc6bd323e61a340d5a1956d8b48272f0ec`;
- exact workflow artifact digest: `sha256:87cf351e76ac5c4cde00a6db0c1f111f9142e21d00b86af5aaa64a1111bf92ee`.

The rate-limited V2 transport audited all 2,506 eligible documents:

- 2,501 parsed under the original strict non-derivative contract;
- 5 failed;
- 99.8005% initial full-corpus parse/source coverage;
- 5,449 parsed transaction rows;
- 2,474 parsed Original documents;
- 27 parsed Revision documents.

The five residual failures were classified exactly:

- four PETRONET filings contained valid `Derivative` disclosure contexts that legitimately omit the cash-security holding/value concepts;
- one NURECA raw-XBRL URL returned HTTP 404.

## Derivative-context correction

NSE's rendered iXBRL confirmed that the four PETRONET failures contain derivative rows alongside ordinary equity rows. Derivative rows use the same disclosure typed axis but do not carry the equity holding/acquisition concepts.

H024-v1 already excludes derivatives from the primary signal. The parser was therefore corrected to:

1. require `TypeOfInstrument` in every disclosure context;
2. recognize exact `Derivative` contexts;
3. exclude those contexts from H024-v1 transaction parsing;
4. retain the full original strict concept/unit checks for every non-derivative context.

No Equity purchase condition was relaxed.

The compact closure probe is retained at:

`research/probes/h024-source-closure-v1.json`

All four PETRONET residual cases then parsed successfully and created zero H024 primary purchases.

## Remaining blocked source

NURECA appId `834` still resolves to a raw-XBRL URL returning HTTP 404.

H024-v1 does not substitute the rendered iXBRL or infer missing raw facts. The filing is `SOURCE_BLOCKED` and cannot create a primary H024 event.

The effective explained source/parser resolution is therefore:

- 2,505 of 2,506 eligible documents resolved or semantically closed;
- 1 of 2,506 explicitly source-blocked;
- effective resolution share: approximately 99.96%.

## Event-frequency feasibility

The V2 parsed corpus contained 792 filings and 1,215 transaction rows that met the earlier direct actor + Equity + Buy + Market Purchase filter.

Reapplying the final stricter H024-v1 rules to those sealed parsed transaction records, including positive quantity, positive INR value, and actual NSE/BSE execution, leaves:

- 788 qualifying filings;
- 159 distinct symbols;
- 1,196 qualifying transaction rows;
- approximately INR 33.95 billion of reported qualifying purchase value.

This is pre-outcome frequency evidence only. It is sufficient to make the frozen H024 coverage gate of 100 complete events across at least 50 symbols plausible. It is not evidence that the signal predicts returns.

## Decision

The H024 official source/parser family is feasible for a prospective event-driven experiment.

The source gate is passed subject to these permanent fail-closed rules:

- derivative contexts are recognized and excluded, not converted into cash-security rows;
- unknown non-derivative semantic variants remain parser-blocked;
- transport failure never relaxes parser semantics;
- missing raw XBRL remains source-blocked;
- revisions never create a positive H024-v1 signal;
- no H024 return outcome may alter the frozen source or signal contract.
