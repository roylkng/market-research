# OR001-D001 Full-Market Multi-Evidence Opportunity Router v1

Status: **FROZEN BEFORE CROSS-PLANE INTERSECTION OUTPUT IS OPENED**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Join the independent Small-Sum Alpha evidence planes into one transparent full-market
research-routing surface.

OR001-D001 is deliberately not a weighted score. It asks:

> How many independent reasons do we currently have to spend scarce deep-research effort
> on this company?

## Frozen identity spine

Use exactly SS001-D001-v1:

- 2,319 current NSE EQ identities;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`.

## Frozen opportunity planes

### EARNINGS_INFLECTION

EI001-S001-v1:

- router SHA-256:
  `fa1e0df536402088f5c3d822c77295f576f77beba1908155cdfed10f83ca716b`;
- route fires when the symbol has at least one frozen EI001 opportunity flag.

### ASSET_ANOMALY

HA001-D001-v1:

- panel SHA-256:
  `81651ebbac5a3102bb2dda9f2931dc10157583bfe2753cc610585811204f5bb3`;
- route fires when the symbol has at least one frozen HA001 opportunity flag.

### SPECIAL_SITUATION

SS002-D001-P2-v1:

- census SHA-256:
  `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`;
- route fires when at least one CURRENT_INVESTABLE_IDENTITY event exists for the symbol.

All current special-situation event categories are retained. OR001 does not infer that
the event is economically direct; L001 evidence is required for that later.

## Independent route count

For every symbol:

`independent_route_count = number of active opportunity planes among the three above`

Frozen research-priority labels:

- `P0_TRIPLE_EVIDENCE`: count = 3;
- `P1_DUAL_EVIDENCE`: count = 2;
- `P2_SINGLE_EVIDENCE`: count = 1;
- `P3_NO_CURRENT_ROUTE`: count = 0.

This count is research priority, not expected return.

## Governance context

Join GF001-D002-v1:

- panel SHA-256:
  `dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7`.

Retain:

- promoter percentage;
- public percentage;
- MF/UTI percentage/state;
- promoter ownership quarter-on-quarter delta where available;
- pledge boolean;
- NDU boolean;
- other encumbrance boolean.

Frozen governance cautions:

- `PROMOTER_PLEDGE_TRUE`;
- `PROMOTER_NDU_TRUE`;
- `PROMOTER_OTHER_ENCUMBRANCE_TRUE`;
- `PROMOTER_OWNERSHIP_DROP_GE_5PP`.

A governance caution does not automatically reject a company. It must be explained in
deep research.

## Financial caution context

Retain all existing EI001 and HA001 caution flags.

No new financial caution threshold is introduced in OR001.

## Liquidity / execution context

Use SS001-D001 frozen 20-session median traded value and the already-frozen
`SS001-I001-v1` liquidity-band transform.

Liquidity affects execution context only. It does not add or remove opportunity routes.

All 2,319 identities remain searchable.

## Broad-market context

Retain `in_existing_u001`.

Being outside U001 is context only. It is not treated as a positive alpha feature.

## Output views

Produce:

1. one row for every 2,319 identity;
2. counts by independent-route count;
3. counts by exact route combination;
4. counts of governance cautions among routed names;
5. a deterministic multi-evidence research queue containing every P0/P1 name, sorted by:
   - independent_route_count descending;
   - median daily turnover descending when available;
   - symbol ascending.

The sort order is for review convenience only.

## Scientific boundary

OR001-D001 does not:

- weight evidence planes;
- fit a model;
- use future returns;
- infer intrinsic value;
- estimate probability;
- call an LLM;
- exclude illiquid names from research;
- authorize ADO/PF001/live capital.

Promotion beyond routing requires deep research and separately frozen valuation/payoff
logic.
