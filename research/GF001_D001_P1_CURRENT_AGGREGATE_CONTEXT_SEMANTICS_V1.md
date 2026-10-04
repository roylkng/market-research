# GF001-D001 P1 Current Aggregate-Context Semantics Amendment v1

Status: **FROZEN AFTER D001 SOURCE-SCHEMA AUDIT, BEFORE P1 RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why P1 exists

GF001-D001 fetched and parsed all 48 frozen current shareholding XBRLs but failed its
aggregate-family gates because D001 assumed aggregate category contexts would be
non-dimensional.

The exact D001 source audit showed that current NSE shareholding XBRL deliberately uses
the `CategoryOfShareholdersAxis` dimension for its aggregate categories.

D001 remains a failed frozen schema hypothesis.

## Exact current aggregate contexts

P1 recognizes an aggregate only when both context ID and explicit member match exactly
after namespace-prefix removal.

### Promoter / promoter group

Context ID:

`ShareholdingOfPromoterAndPromoterGroup_ContextI`

Required explicit member:

`ShareholdingOfPromoterAndPromoterGroupMember`

### Public shareholders

Context ID:

`PublicShareholding_ContextI`

Required explicit member:

`PublicShareholdingMember`

### Mutual funds / UTI

Context ID:

`MutualFundsOrUTI_ContextI`

Required explicit member:

`MutualFundsOrUTIMember`

The numeric aggregate fact remains exactly:

`ShareholdingAsAPercentageOfTotalNumberOfShares`

No fuzzy context-name matching is permitted in P1.

## Value-scale semantics

P1 resolves aggregate scale from promoter + public current-quarter values.

- fraction semantics when each value lies in [0,1] and their sum lies in [0.95,1.05];
- percentage-point semantics when each value lies in [0,100] and their sum lies in
  [95,105];
- otherwise unresolved.

No historical H023 scale assumption is imported.

## Mutual-fund structural absence

D001 observed `MutualFundsOrUTI_ContextI` in only 27/48 current filings.

P1 does **not** infer zero ownership when the context is absent.

State is:

- `READY` when exact context/member/fact exists;
- `CATEGORY_CONTEXT_ABSENT` when the exact aggregate context is absent;
- `AMBIGUOUS_OR_INVALID` when the context exists but cannot yield one finite aggregate.

Therefore P1 does not require a numeric mutual-fund value in 90% of companies.

## Promoter encumbrance semantics

P1 additionally audits three exact boolean concepts, each required in context `MainI`:

- `WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup`;
- `WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup`;
- `WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup`.

Accepted raw values are exactly case-insensitive `true` or `false`.

These are source facts only. P1 does not yet assign a governance penalty.

## P1 feasibility gates

P1 passes only if:

1. at least 44/48 frozen sample filings are fetched and well-formed;
2. >=90% of successfully parsed June filings expose exact promoter aggregate semantics;
3. >=90% expose exact public aggregate semantics;
4. >=90% expose all three exact promoter encumbrance booleans;
5. every present mutual-fund aggregate context is deterministically parseable;
6. all six September filings satisfy promoter/public/encumbrance core semantics;
7. aggregate scale is resolved for >=90% of all successfully parsed filings.

Thresholds may not be lowered after P1 output is opened.

## Promotion

Passing P1 permits GF001-D002 to parse the full 2,050-company D002 latest-source set
using only the exact current semantics frozen here.

MF/UTI ownership remains optional/missing when the category context is absent.

No governance score is authorized by P1.

## Scientific boundary

No stock returns, price outcomes, valuation ranks or company-quality labels were used to
derive this amendment.
