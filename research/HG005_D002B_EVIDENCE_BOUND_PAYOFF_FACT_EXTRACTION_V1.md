# HG005-D002B Evidence-Bound Payoff Fact Extraction v1

Status: **FROZEN BEFORE D002A SOURCE CORPUS OUTPUT IS OPENED**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Apply the existing SS002-L001 evidence-bound extraction discipline to the frozen
HG005-D002 payoff-enrichment source corpus and synthesize only explicit source facts
required by the five family-specific payoff lanes.

HG005-D002B does not assign valuation multiples, transaction-completion probabilities,
expected returns, target prices or portfolio weights.

## Frozen upstream

Company set exactly:

- ANANTRAJ
- DEVX
- INOXGREEN
- NPST
- SAMBHV

Payoff source design:

- `research/HG005_D002_FAMILY_SPECIFIC_PAYOFF_SOURCE_ENRICHMENT_V1.md`
- `research/hg005/hg005-d002-source-manifest-v1.json`

Expected source manifest:

- manifest_id: `HG005-D002-SOURCE-MANIFEST-v1`
- exactly 19 source specifications.

D002B may run only when a passed HG005-D002A corpus is available under the frozen
D002A protocol.

## Extraction boundary

Every READY_TEXT D002A source is processed independently.

The model receives only:

- source_id;
- symbol;
- source type;
- required fact groups;
- exact document_id / raw SHA-256;
- deterministic text segments and segment hashes;
- source URL.

No web search, market price, prior valuation conclusion or unsupported company memory
may be supplied to the model.

## Evidence rule

Every material extracted fact must carry:

- status: EXPLICIT / UNKNOWN;
- typed value or null;
- unit;
- one or more exact D002A segment IDs when EXPLICIT.

UNKNOWN must remain null.

Arithmetic derivation is forbidden inside the LLM extraction step.

## Frozen company/lane fact requirements

### ANANTRAJ — DEMERGER_ENTITLEMENT

Extract when explicit:

- demerger exchange ratio;
- Ashok Cloud / separated-business FY26 revenue;
- separated-business EBITDA;
- separated-business EBIT;
- separated-business PAT;
- transferred assets;
- transferred liabilities / debt;
- operating data-centre capacity;
- capacity under construction / planned;
- scheme stage;
- record date;
- effective date;
- residual/stub business financial facts when explicitly separated.

### DEVX — CAPITAL_DEPLOYMENT_MONITOR

Extract when explicit:

- preferential equity/warrant cash received;
- cumulative deployed proceeds;
- unutilized proceeds;
- object-wise use of proceeds;
- Winston security-deposit amount and amount funded;
- Winston project area / contracted space;
- lease tenure;
- rent-free / fit-out period;
- project commencement / operational date;
- current operating seats / area / capacity;
- management-disclosed revenue, margin or cash-flow consequence directly tied to funded
  deployment.

### INOXGREEN — ACQUISITION_ECONOMICS

Extract when explicit:

- latest/final Wind World O&M purchase consideration;
- adjustment mechanism;
- acquisition funding source;
- incremental debt / financing amount;
- explicit financing rate or interest burden;
- target O&M revenue history;
- target EBITDA;
- target PAT;
- target cash flow;
- O&M MW/GW under management;
- current acquisition stage;
- conditions precedent / remaining approvals.

### INOXGREEN — DEMERGER_ENTITLEMENT

Extract when explicit:

- Resco / resulting-company exchange ratio;
- separated Power Evacuation business revenue;
- EBITDA;
- PAT;
- cash flow;
- transferred assets;
- transferred liabilities;
- operating assets/capacity;
- scheme stage;
- record date;
- effective date.

### NPST — CAPITAL_DEPLOYMENT_MONITOR

Extract when explicit:

- original raise amount;
- cumulative deployed amount;
- unutilized amount;
- object-wise deployment;
- acquisitions funded from proceeds;
- product/infrastructure spend;
- overseas/global-expansion spend;
- current acquisition/product/global-expansion state;
- explicit operating/revenue/cost consequences management directly links to deployed
  capital.

### SAMBHV — DILUTION_FINANCING / CAPEX_DEPLOYMENT

Extract when explicit:

- warrant count;
- issue price;
- face value;
- conversion mechanics;
- upfront cash received;
- total expected proceeds;
- object-wise use of proceeds;
- capex allocation;
- working-capital allocation;
- subsidiary investment;
- capacity baseline;
- capacity expansion;
- capex commissioning timeline;
- control/dilution statements;
- shareholder approval stage.

## Cross-source precedence

For the same fact:

1. later official effective/transaction document supersedes earlier proposal terms when
   the newer document explicitly changes the term;
2. otherwise retain all differing explicit values as a conflict;
3. do not choose the most favorable value;
4. source publication/effective dates must be retained.

## Deterministic synthesis states

For each company/lane, downstream deterministic code assigns only:

- SOURCE_READY
- SOURCE_PARTIAL
- SOURCE_CONFLICTING
- SOURCE_NOT_FOUND

The exact D002 family-specific readiness criteria remain authoritative.

## Model/runtime

D002B may use the existing SS002-L001 contract and validator.

Provider/model provenance must be retained exactly as required by SS002-L001.

A native GPT-5.6 Sol execution may be used for the first frozen run, matching the
evidence-bound approach used by HG004-L001.

## Mechanical gates

D002B passes only if:

1. every D002A READY_TEXT source has exactly one validated extraction output;
2. zero unsupported evidence segment references;
3. zero new symbols/source IDs;
4. zero forbidden investment/valuation/advice fields;
5. all five mandatory anchor sources have validated outputs;
6. every synthesized explicit fact retains at least one source_id and evidence segment;
7. no arithmetic-derived value is relabelled as explicit.

## Promotion

A passed D002B permits HG005-D003 family-specific scenario/payoff frameworks.

D003 may define valuation equations and bear/base/bull assumption variables, but
subjective valuation assumptions must be explicit, sensitivity-tested and separated
from source facts.

## Scientific boundary

D002B does not:

- set valuation multiples;
- estimate completion probability;
- estimate expected return;
- rank the five companies;
- create target prices;
- create ADO/PF001 eligibility;
- authorize live capital.
