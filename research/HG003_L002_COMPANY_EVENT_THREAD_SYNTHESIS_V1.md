# HG003-L002 Company-Level Special-Situation Thread Synthesis v1

Status: **FROZEN BEFORE COMPANY-LEVEL CATALYST MATERIALIZATION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Collapse the validated HG003-L001 thread-level relevance/stage outputs into one
deterministic special-situation state per company in the fixed 28-name HG002 hidden-gem
underwriting cohort.

L002 prevents duplicate keyword families from making one transaction appear like several
independent catalysts and prevents stale offer-open documents from overriding later
completion evidence.

L002 is a research-routing state, not an expected-return model.

## Frozen source chain

Use exactly:

- HG003-D001-v1;
- selection SHA-256:
  `ebc543464475ff9e409b1795c02272a818a3062cef8ad2bafcfafb5fcc30b536`;
- workflow run: `37267831741`;
- artifact ID: `11327057449`;

and:

- HG003-L001-GPT56SOL-NATIVE-v1;
- run SHA-256:
  `ce03af24e2bfa807f619a0db4db562d35cc96748cb0c5f75a1e1d7338c66809a`;
- result SHA-256:
  `c8a41e7484a9ef0497ba3a764d8b801aecdda0d01362ec7fe3f3378564f6f693`;
- workflow run: `37275845301`;
- artifact ID: `11330650650`.

No later rerun may be substituted under L002-v1.

## Economic relevance groups

### CURRENT_ECONOMIC_RELEVANCE

L001 economic relevance is one of:

- `DIRECT_LISTED_SECURITY`;
- `LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR`.

These threads may represent a current economic catalyst or a completed economic event.

### INDIRECT_RELEVANCE

L001 economic relevance:

- `SUBSIDIARY_OR_INVESTEE_ONLY`.

The event is retained as company context but is not treated as a direct listed-security
special-situation catalyst.

### CONTEXT_ONLY

L001 economic relevance:

- `OTHER_CORPORATE_CONTEXT`.

The upstream special-situation keyword does not create a current transaction catalyst.

## Frozen semantic transaction clusters

Each validated L001 thread maps to exactly one primary semantic cluster using its
corrected transaction families.

Priority is deterministic and does not depend on company name:

1. if family contains `BUYBACK` or `TENDER_OFFER`:
   `BUYBACK_TENDER`;
2. if family contains `INSOLVENCY_RESOLUTION`:
   `INSOLVENCY_ACQUISITION`;
3. if family contains `RIGHTS_ISSUE`:
   `RIGHTS_ISSUE`;
4. if family contains `PREFERENTIAL_WARRANT`:
   `PREFERENTIAL_WARRANT`;
5. if family contains `FUND_RAISE_OTHER`:
   `FUND_RAISE_OTHER`;
6. if family contains `SCHEME_REORGANISATION`:
   `SCHEME_REORGANISATION`;
7. otherwise:
   `OTHER`.

`ACQUISITION_INVESTMENT` is retained as a secondary family and does not create a
separate cluster when paired with CIRP/rights evidence.

## Latest-evidence rule within a cluster

For each symbol + semantic cluster:

1. retain every exact HG003 thread assigned to the cluster;
2. sort by selected exchange publication timestamp descending;
3. tie-break by thread_id ascending;
4. the first row is the cluster's current stage/relevance authority.

This deliberately allows:

- a later buyback-completion filing to supersede an earlier tender-offer-open filing;
- an independent CIRP acquisition cluster to remain active even when a separate scheme
  cluster at the same company is already complete.

No LLM call is made in L002.

## Frozen stage groups

### ACTIVE_FORWARD_STAGE

- PROPOSAL
- BOARD_APPROVED
- SHAREHOLDER_APPROVED
- REGULATORY_OR_COURT_APPROVED
- PUBLIC_ANNOUNCEMENT
- OFFER_OPEN
- RECORD_DATE_FIXED

### COMPLETED_STAGE

- OFFER_CLOSED
- ALLOTMENT_COMPLETED
- TRANSACTION_COMPLETED

### CANCELLED_STAGE

- CANCELLED_OR_WITHDRAWN

### PROCEDURAL_STAGE

- PROCEDURAL_UPDATE

`UNKNOWN` is not expected under the passed HG003-L001 gate; if present, fail closed.

## Company-level catalyst state

Using latest authority for every semantic cluster:

### ACTIVE_DIRECT_CATALYST

At least one CURRENT_ECONOMIC_RELEVANCE cluster is in ACTIVE_FORWARD_STAGE.

### PROCEDURAL_DIRECT_REVIEW

No active direct cluster exists, but at least one CURRENT_ECONOMIC_RELEVANCE cluster is
PROCEDURAL_STAGE.

This state explicitly requires deeper thread reconstruction before payoff modeling.

### COMPLETED_DIRECT_EVENT_ONLY

No active/procedural direct cluster exists, but at least one CURRENT_ECONOMIC_RELEVANCE
cluster is COMPLETED_STAGE.

Completed events remain important for earnings/assets but are not treated as a live
special-situation catalyst.

### CANCELLED_DIRECT_EVENT_ONLY

No active/procedural/completed direct cluster exists, but at least one
CURRENT_ECONOMIC_RELEVANCE cluster is CANCELLED_STAGE.

### INDIRECT_OR_CONTEXT_ONLY

No CURRENT_ECONOMIC_RELEVANCE cluster exists, but one or more indirect/context clusters
exist.

### TEXT_PENDING

No validated L001 output exists because the exact frozen thread remains text unavailable.

Expected frozen pending case:

`HINDCOPPER::OFFER_FOR_SALE`.

## Detailed-term routing

Detailed evidence-bound L001 term extraction is authorized next only for:

- ACTIVE_DIRECT_CATALYST clusters;
- PROCEDURAL_DIRECT_REVIEW clusters where thread reconstruction shows a still-live
  underlying transaction.

COMPLETED_DIRECT_EVENT_ONLY may receive historical/earnings impact analysis but not a
current event-spread model.

INDIRECT_OR_CONTEXT_ONLY is removed from current special-situation payoff modeling but
remains in HG002 because earnings and asset lanes are independent.

## Output

For each of 28 HG002 symbols retain:

- every frozen HG003 thread;
- corrected relevance/families/stage;
- semantic cluster;
- latest-authority flag;
- cluster current state;
- company catalyst state;
- direct active cluster count;
- completed direct cluster count;
- indirect/context cluster count;
- unresolved text thread count.

## Gates

L002 passes only if:

1. exactly 28 HG002 symbols are retained;
2. all 35 frozen HG003 threads remain accounted for;
3. all 34 TEXT_READY threads resolve to one validated L001 output;
4. HINDCOPPER::OFFER_FOR_SALE remains the only TEXT_PENDING thread;
5. every validated thread maps to exactly one semantic cluster;
6. every cluster has exactly one latest authority;
7. no return/price/valuation data enters synthesis.

## Scientific boundary

L002 does not:

- estimate intrinsic value;
- estimate completion probability;
- calculate event spread;
- rank companies;
- remove a company from HG002;
- change EI001/HA001/GF001 evidence;
- create ADO/PF001/live-capital eligibility.
