# HG001-C001 First Convergent Hidden-Gem Deep-Research Cohort v1

Status: **FROZEN AFTER HG001 ROUTER MATERIALIZATION, BEFORE DEEP UNDERWRITING**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Select the first small, high-convergence cohort for full company-level underwriting from
the passed HG001-D001 full-market research router.

C001 is deliberately frozen **after** the HG001 current-evidence router was opened. It is
not a preregistered alpha cohort. Its purpose is to allocate deep-research/LLM effort
before any company-specific valuation conclusion or future-return outcome is opened.

## Frozen source

Use exactly:

- HG001-D001-v1;
- workflow run: `37258053642`;
- artifact ID: `11323461912`;
- artifact name: `hg001-d001-37258053642`;
- router SHA-256:
  `79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff`;
- identity count: 2,319;
- triple-lane count: 79.

No later financial filing, announcement, price movement or return may change C001-v1.

## Frozen selection rule

A company enters C001 only when all are true in the exact HG001-D001 row:

1. `active_opportunity_lane_count == 3`;
2. `in_existing_u001 == false`;
3. `governance_caution_flags` is empty;
4. `asset_caution_flags` is empty;
5. `earnings_negative_flags` is empty;
6. `liquidity_band` is neither:
   - `L6_BELOW_20L`; nor
   - `OBSERVATION_INSUFFICIENT`.

The rule does not use valuation, market capitalization, analyst coverage, future returns,
or discretionary company preference.

## Expected deterministic cohort

Applying the rule to the frozen HG001-D001 artifact must yield exactly 16 symbols:

- ANANTRAJ
- BAJAJCON
- BORORENEW
- DATAMATICS
- DEVX
- EXIDEIND
- GANDHITUBE
- HINDCOPPER
- HTMEDIA
- IBULLSLTD
- MINDACORP
- MMFL
- NIITLTD
- SAMBHV
- SARLAPOLY
- TREL

A different count or symbol set fails closed.

## Why this cohort is small

C001 requires simultaneous current evidence from all three independent opportunity lanes:

- earnings inflection;
- asset/capacity anomaly;
- current special situation.

It then removes names carrying already-observed governance, asset-balance-sheet or
earnings-deterioration cautions, and avoids the thinnest current liquidity band for this
first deep-research cohort.

This does not imply that excluded names are unattractive. They remain in HG001.

## Frozen special-situation document-thread selection

For each C001 symbol and each current SS002-D001-P2 special-situation family attached to
that symbol:

1. retain only `CURRENT_INVESTABLE_IDENTITY` events;
2. require the event's official document to be `READY` in SS002-D003;
3. sort events by exchange publication timestamp ascending, then announcement ID;
4. select the earliest qualifying document for the family;
5. select the latest qualifying document for the family when its document ID differs
   from the earliest;
6. deduplicate identical document IDs across families while preserving all linked
   families/events.

No document is selected because it contains an attractive price, valuation, catalyst or
LLM interpretation.

The result is the C001 special-situation evidence bundle for L001 extraction and L002
transaction threading.

## Underwriting routes

Every C001 company proceeds through:

### Earnings branch
Validate the EI001 inflection with:
- quarterly composition;
- exceptional items;
- operating drivers;
- margin sustainability;
- prior-year base effects;
- management commentary.

### Asset/capacity branch
Validate HA001 flags with:
- annual-report notes;
- investment/subsidiary composition;
- liquidity and accessibility of financial assets;
- investment property/land context where applicable;
- CWIP project identity, commissioning, funding and return economics.

### Special-situation branch
Run evidence-bound L001 extraction and L002 transaction threading on the frozen C001
document bundle.

### Governance branch
Even though C001 has no current frozen GF001 caution, deep research still checks:
- auditor events;
- related-party transactions;
- dilution/warrants;
- promoter behavior;
- capital allocation;
- contingent liabilities.

## Scientific boundary

C001 is a research-effort cohort only.

It does not:

- claim that the 16 names will outperform;
- assign expected return;
- calculate intrinsic value;
- rank the 16 by attractiveness;
- create a buy/sell recommendation;
- create ADO/PF001 eligibility;
- authorize live capital.
