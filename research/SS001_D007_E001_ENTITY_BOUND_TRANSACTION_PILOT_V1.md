# SS001-D007-E001 Entity-Bound Transaction Thread Pilot v1

Status: **FROZEN BEFORE FIRST MACHINE-READABLE CASE MATERIALIZATION**
Frozen: 2026-10-09
Research only; not issuer share-count adjudication

## Purpose

Demonstrate a rigorous, source-bound entity/transaction boundary for multi-entity
Indian special situations. The first case is the existing independently reviewed
INOXGREEN document-level example:

`research/SS001_ILLUSTRATIVE_CASE_INOXGREEN_2026_10_09.md`.

The input is NOT the still-unexecuted 1,240-page D007 R001 cohort. E001 is a
single illustrative, manually evidence-checked specimen and a generalizable
validation contract. It does not alter the frozen 12-issuer queue, approve any
outstanding shares or authorize a market-cap calculation.

## Problem being prevented

An issuer may disclose:

- shares **issued by another legal entity** to the issuer's holders;
- an acquisition approved by a court but awaiting definitive agreements;
- one subsidiary buying operating assets while another group entity buys
  unrelated power-generation assets.

Keyword-only processing can easily misattribute all three to the listed
issuer. A company-level flat event bag loses the economically decisive identities.

## Frozen data model

### Document/source authority

The document registry contains exact **official NSE** source URLs, SHA-256 document
identities, disclosed publication dates, and permitted page-segment IDs.

Each EXPLICIT fact must identify:

- exact registered `document_id`;
- exact registered `segment_id`;
- `subject_entity_id`;
- typed `value`, `unit`, and `qualifier`.

A listed issuer's stock symbol is never substituted for the legal entity that
issued the security or owned the disclosed asset.

The validator verifies provenance identity and internal semantics. It does
**not** independently verify that the model/researcher read or interpreted the
cited PDF correctly; a separate source-level audit remains mandatory.

### Thread identity

Each event thread has:

- a unique stable `thread_id`;
- a primary `economic_family`;
- `transaction_stage` with legal-stage semantics;
- a distinct `subject_entity_id`;
- `security_issuer_entity_id` when share issuance is disclosed;
- `issuer_security_effect` for the listed issuer;
- nonempty, cited, typed facts;
- explicit unresolved questions.

Do not merge threads merely because they were announced by the same listed
company or have an NCLT reference.

### Frozen security-effect states

- `OTHER_ENTITY_SHARES`: explicitly disclosed share issuance/allotment is
  by a **different** identified legal entity.
- `NO_ISSUER_CHANGE_EVIDENCED`: no direct listed-issuer share change is
  evidenced by the cited terms. This is **not** proof of unchanged capital.
- `DIRECT_ISSUER_CHANGE_REQUIRES_CAPITAL_RECONCILIATION`: a direct issuer
  share issuance/reduction has explicit evidence, but no share-count clearance.
- `UNRESOLVED`: identity or economic effect is insufficiently evidenced.

`OTHER_ENTITY_SHARES` is valid only when the security issuer differs from
the frozen listed issuer.

`NO_ISSUER_CHANGE_EVIDENCED` never means `NO_SHARE_CHANGE` or
`CAPITALIZATION_ALLOWED`.

### Frozen stages

- `PROPOSED`
- `COURT_OR_REGULATOR_APPROVED_PENDING_EXECUTION`
- `RECORD_DATE_FIXED`
- `SECURITIES_ALLOTTED_BY_SUBJECT_ENTITY`
- `EXECUTED_AND_CLOSED`
- `CANCELLED`
- `UNKNOWN`

Approval is explicitly weaker than closing. For the E001 P0 case, a WWIL
resolution-plan order cannot be labeled `EXECUTED_AND_CLOSED`.

### Typed economic terms

Facts may be:

- explicit date (ISO YYYY-MM-DD);
- explicit integer share count;
- explicit ratio text;
- stated revenue/consideration (INR crore);
- stated capacity (GW/MW);
- concise explicit event/condition text.

Mandatory `qualifier` is one of:

- `EXPLICIT_FINAL`: definitive explicit disclosure, not a prediction;
- `PROVISIONAL_UNAUDITED`;
- `UPPER_BOUND_PROPOSED`;
- `EXPECTED_NOT_COMPLETED`;
- `CONDITIONAL_ORAL_APPROVAL`;
- `DESCRIPTIVE`.

Proposed cash consideration cannot be silently converted to a closed
transaction price. Anticipated deadlines cannot be converted to actual closing
dates, and issuer/other-entity shares are not interchangeable.

## INOXGREEN P0 scope

Exactly three legally/economically separated evidence threads:

1. IRSL share entitlement and IRSL's subsequent allotment of 48,982,030
   IRSL shares to eligible INOXGREEN holders. The beneficiary being an
   INOXGREEN holder does **not** make these newly issued INOXGREEN shares.
2. WWIL O&M business acquisition proposed by INOXGREEN/group, subject to
   NCLT scheme implementation and agreements: up to ₹550 crore proposed cash
   consideration, ~4.5 GW service portfolio, provisional FY26 turnover
   ₹579.77 crore.
3. INEL's distinct ~600 MW IPP interest under the WWIL resolution plan.
   It is another group entity's prospective asset and not automatically
   an INOXGREEN O&M asset.

No other securities or company economics are inferred.

## Frozen output safety

Every accepted E001 pack must declare:

- `full_d007_l002_coverage=false`;
- `semantic_audit_complete=false`;
- `share_action_clearance_proven=false`;
- `market_capitalization_calculated=false`;
- `expected_return_calculated=false`;
- `portfolio_eligibility_allowed=false`;
- `live_capital_allowed=false`;
- `return_outcomes_opened=false`.

Those are not status placeholders that may be flipped within E001. Any future
share-count continuity assertion must use a separately frozen D007-A001
protocol *after* a complete, independently checked L002 evidence assembly.

## Promotion boundary

Passing this case validates only the **entity boundary / provenance contract**
for later issuer review. No hidden-gem claim, valuation, ranking, probability,
buy/sell/hold or current market-cap eligibility follows.
