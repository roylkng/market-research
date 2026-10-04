# GF001-D002 Full-Market Current Governance/Ownership Parser v1

Status: **FROZEN BEFORE FULL-MARKET XBRL PARSING**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Apply the exact current NSE shareholding semantics that passed GF001-D001-P1 to the
entire SS001-D002 latest-source set and measure real full-market coverage.

GF001-D002 produces governance/ownership facts only. It does not assign a governance
score.

## Frozen source spine

Use exactly:

- SS001-D002-v1;
- workflow run: `37198355430`;
- artifact ID: `11302177421`;
- census SHA-256:
  `214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293`.

D002 source census contains:

- 2,319 frozen SS001 identities;
- 2,050 READY latest standard-quarter shareholding sources;
- 2,032 READY latest sources with an adjacent prior-quarter source.

Only the 2,050 READY latest-source identities enter GF001-D002 parser coverage.
The remaining 269 identities remain explicit source-unavailable states.

## Frozen current parser authority

Use the exact semantics that passed:

- GF001-D001-P1-v1;
- audit SHA-256:
  `0e1c2242575adbd46ca0ea1c7957b5f6420b9797d77b4ba27cf0ba609ad1b7ea`.

### Promoter/promoter-group aggregate

Context:

`ShareholdingOfPromoterAndPromoterGroup_ContextI`

Required exact explicit member:

`CategoryOfShareholdersAxis = ShareholdingOfPromoterAndPromoterGroupMember`

Fact:

`ShareholdingAsAPercentageOfTotalNumberOfShares`

### Public aggregate

Context:

`PublicShareholding_ContextI`

Required exact explicit member:

`CategoryOfShareholdersAxis = PublicShareholdingMember`

Fact:

`ShareholdingAsAPercentageOfTotalNumberOfShares`

### Mutual funds / UTI

Context:

`MutualFundsOrUTI_ContextI`

Required exact explicit member:

`CategoryOfShareholdersAxis = MutualFundsOrUTIMember`

Fact:

`ShareholdingAsAPercentageOfTotalNumberOfShares`

MF/UTI state is explicitly `CATEGORY_CONTEXT_ABSENT` when the exact context does not
exist. Absence is not interpreted as zero ownership.

### Promoter encumbrance booleans

Context: exact `MainI`.

Concepts:

- `WhetherAnySharesHeldByPromotersAreEncumberedUnderPledgedForPromoterAndPromoterGroup`;
- `WhetherAnySharesHeldByPromotersAreEncumberedUnderNonDisposalUndertakingForPromoterAndPromoterGroup`;
- `WhetherAnySharesHeldByPromotersAreEncumberedOtherThanByWayOfPledgeOrNDUForPromoterAndPromoterGroup`.

Accepted raw values are exactly case-insensitive `true` or `false`.

## Value scale

The P1 current-schema sample resolved all 48 filings as fractions in [0,1].

GF001-D002 therefore requires promoter and public aggregate facts to be finite values
in [0,1], and requires:

`0.95 <= promoter_fraction + public_fraction <= 1.05`.

Output ownership values are converted to percentage points by multiplying by 100.

A filing that violates this rule fails closed as `CORE_PARSE_FAILED`; no percentage
point fallback is allowed in GF001-D002-v1.

## Latest filing output

For every D002 READY latest source retain:

- promoter/promoter-group percentage;
- public percentage;
- MF/UTI percentage or structural-absence state;
- pledge boolean;
- NDU boolean;
- other-encumbrance boolean;
- exact report date, source URL and XBRL SHA-256;
- parser status/reason.

A latest source is `CORE_READY` only when promoter, public, scale and all three
encumbrance booleans are deterministic.

## Adjacent-quarter output

When D002 supplies an adjacent prior source, parse it with the same frozen current
semantics.

When both latest and prior are CORE_READY retain:

- promoter ownership delta in percentage points;
- public ownership delta in percentage points.

When MF/UTI is READY in both periods retain its delta; otherwise MF delta is unavailable.

A prior parser failure never invalidates an otherwise valid latest current observation.

## Frozen source-feasibility gates

GF001-D002 passes only if all are true:

1. at least 90% of the 2,050 READY latest sources are CORE_READY;
2. at least 80% of the 2,032 adjacent-source identities have both latest and prior
   CORE_READY;
3. every CORE_READY latest filing has promoter/public sum within the frozen fraction
   tolerance;
4. every CORE_READY latest filing has all three encumbrance booleans;
5. every present exact MF/UTI aggregate context is either deterministically READY or
   explicitly fails closed; structural absence is not counted as parser failure;
6. all D002 identities remain accounted for exactly once as READY/source-unavailable.

Thresholds may not be lowered after full-market output is opened.

## Promotion

Passing GF001-D002 permits:

- a current governance/ownership evidence plane for SS001 deep research;
- GF002 governance-event source work for auditor, related-party, dilution, director and
  capital-allocation risks;
- separately frozen descriptive governance risk flags.

Passing GF001-D002 does **not** authorize a composite governance score by itself.

## Explicit exclusions

GF001-D002 does not:

- infer promoter quality from promoter percentage;
- penalize companies for low MF ownership;
- infer zero MF ownership from absent category context;
- infer pledge percentage from a boolean flag;
- use future returns;
- rank stocks;
- create ADO/PF001 eligibility;
- authorize live capital.
