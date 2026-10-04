# GF001-D001 Current Shareholding XBRL Schema Audit v1

Status: **FROZEN BEFORE XBRL SOURCE ACCESS**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Determine the exact current NSE shareholding-pattern XBRL concepts, contexts, units and
value semantics needed for a future full-market governance/ownership parser.

GF001-D001 is a source-schema audit only. It does not assign governance quality,
promoter quality, pledge risk or institutional-ownership scores.

## Frozen source spine

Use exactly:

- SS001-D002-v1;
- workflow run: `37198355430`;
- artifact ID: `11302177421`;
- D002 census SHA-256:
  `214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293`.

D002 established:

- 2,050 / 2,319 valid latest standard-quarter shareholding sources;
- 2,032 / 2,319 with an adjacent prior-quarter source.

## Frozen sample

Use exactly:

`research/gf001/gf001-d001-current-schema-sample-v1.json`

Sample size: 48.

The sample includes:

- all six D002 READY symbols whose latest report date is 2026-09-30;
- seven 2026-06-30 symbols from each I001 liquidity band L1-L6;
- within L1, three existing-U001 and four outside-U001 symbols.

The selection is source/liquidity stratified only. No return, valuation or quality
outcome influenced the sample.

## Official filing source

For each sample symbol:

1. take the exact D002 latest source whose report date equals the frozen sample date;
2. require an approved official NSE archive URL;
3. download the exact XBRL bytes;
4. retain exact bytes and SHA-256;
5. parse only XML structure and fact metadata.

No alternate provider may fill a source gap.

## Schema inventory

For each filing inventory:

- all XBRL context IDs;
- context period/instant and dimension presence;
- all fact local names;
- fact contextRef;
- unitRef;
- raw textual value;
- numeric parseability;
- observed numeric range.

In addition, identify candidate facts whose local-name or context ID contains any frozen
case-insensitive token from:

- promoter;
- promoter group;
- public;
- encumber;
- pledge;
- mutual fund;
- uti;
- foreign portfolio;
- fpi;
- insurance;
- institutional;
- significant beneficial;
- shareholder;
- shareholding;
- percentage;
- number of shares.

This token search is an audit aid only. It does not define final semantics.

## Cross-file schema summary

Report for every observed candidate concept/context pair:

- filing count;
- report-date count;
- unitRef values;
- numeric/non-numeric counts;
- minimum/maximum numeric value where applicable;
- sample symbols;
- exact context-ID examples.

Also report exact concepts/contexts that occur in:

- at least 90% of successfully parsed 2026-06-30 filings;
- all successfully parsed 2026-09-30 filings.

## Feasibility gates

D001 passes only when all are true:

1. at least 44 of 48 sample XBRLs are fetched and well-formed;
2. at least 90% of successfully parsed 2026-06-30 filings expose deterministic
   promoter/promoter-group aggregate shareholding evidence;
3. at least 90% expose deterministic public-shareholder aggregate evidence;
4. at least 90% expose a deterministic current-quarter mutual-fund/UTI aggregate
   ownership fact or an explicit structural equivalent;
5. the six 2026-09-30 filings do not introduce an unresolvable schema break in those
   three aggregate families.

The promoter/public/mutual-fund conditions are source-semantic gates only. D001 does not
require a pledge/encumbrance fact to be present for every company because a company may
have zero or non-applicable encumbrance.

## Promotion

If D001 passes, freeze GF001-D002 parser semantics before parsing the full 2,050-company
latest-source set.

GF001-D002 may define exact concepts/contexts for:

- promoter/promoter-group ownership;
- public ownership;
- mutual-fund/UTI ownership;
- FPI/foreign institutional ownership where source semantics are stable;
- promoter pledge/encumbrance where source semantics are stable;
- quarter-over-quarter ownership changes using D002 adjacent sources.

No governance score may be created until GF001-D002 source coverage is measured.

## Explicit exclusions

GF001-D001 does not:

- score governance;
- interpret high promoter ownership as positive or negative;
- interpret institutional ownership as positive or negative;
- infer pledge risk from absent facts;
- use future returns;
- use LLM judgment;
- filter SS001;
- create ADO/PF001 eligibility;
- permit live capital.
