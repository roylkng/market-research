# HG005-D002B P1 Time-Ordered State-Fact Synthesis Amendment v1

Status: **FROZEN AFTER FIRST D002B EXTRACTION, BEFORE P1 SYNTHESIS RERUN**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P1 exists

The first HG005-D002B evidence-bound extraction run passed all source/evidence gates:

- 19/19 frozen sources validated;
- 47 explicit facts;
- zero unsupported material facts;
- zero material payoff facts missed in manual audit.

However, deterministic cross-source synthesis classified five lanes as
`SOURCE_CONFLICTING` because it treated normal time-ordered state progression as a
value contradiction.

Observed examples:

- DEVX: Winston "signed in Q4 FY26" versus Q1FY27 "ongoing/no delay";
- INOXGREEN: successful bidder -> NCLT approval -> certified-order/IMC stage;
- SAMBHV: board-approved proposal -> EGM/procedural stage -> September in-principle
  exchange application.

These are not competing same-date economic values. They are successive official states.

No return, valuation, target-price, probability or portfolio outcome was opened.

## Frozen P1 change

Only the following exact fact names receive time-order semantics:

- `winston_project_status_text`;
- `wwil_acquisition_stage_text`;
- `financing_stage_text`.

For these names:

1. retain every explicit source fact unchanged;
2. require every competing value to carry a canonical ISO effective/reporting date;
3. order values by date;
4. use the latest-dated explicit value as the current state;
5. do not label differing older values as a source conflict;
6. if two different values have the same latest date, retain `SOURCE_CONFLICTING`;
7. if any competing value lacks a canonical date, retain `SOURCE_CONFLICTING`.

All non-temporal fact names retain the original exact value-conflict rule.

## Deliberately unchanged

P1 does not change:

- any of the 19 D002A sources;
- any extracted D002B fact/value/unit/date/evidence segment;
- any source priority;
- any lane readiness requirement;
- any missing-input list;
- any valuation or payoff assumption.

The original D002B extraction/result remains preserved.

## Expected scientific interpretation

After P1:

- stage evolution may no longer create false conflicts;
- a lane becomes SOURCE_READY only if its original frozen readiness conditions are met;
- otherwise it remains SOURCE_PARTIAL / SOURCE_NOT_FOUND / SOURCE_CONFLICTING.

In particular, P1 does not create missing WWIL funding or normalized earnings facts.

## Scientific boundary

P1 is deterministic synthesis repair only. It does not estimate returns, probabilities,
multiples, target prices or portfolio actions.
