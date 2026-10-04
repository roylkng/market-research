# SS002-D001 Current Special-Situation Announcement Census v1

Status: **FROZEN BEFORE SOURCE ACQUISITION**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Build the first source-only special-situation event census across the broad SS001 market.

The purpose is to find current corporate events that can create non-standard valuation
or payoff structures, then hand only the resulting candidates to later document/LLM
underwriting.

D001 does not decide whether an event is attractive.

## Frozen market universe

Use exactly the passed SS001-D001 census:

- run: `37197575401`;
- artifact ID: `11301695772`;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- 2,319 current NSE EQ identities.

## Official source and acquisition mode

Official NSE corporate-announcement endpoint:

`/api/corporate-announcements?index=equities&from_date=<DD-MM-YYYY>&to_date=<DD-MM-YYYY>`

The existing AE001-D003 source audit already established that daily whole-market queries
reconstruct the audited whole-window source exactly.

Authoritative audit:

- `research/ae001-d003-result-v1.json`;
- report SHA-256:
  `7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f`.

D001 therefore queries exactly one whole-market response per calendar date.

## Frozen source window

Acquire every calendar date from:

- 2026-04-01 through
- 2026-10-04 inclusive.

Empty daily responses are valid evidence.

Every response's exact bytes are retained and SHA-256 bound.

## Canonical announcement identity

Reuse `marketlab.alpha_announcements.canonical_announcement` unchanged.

Identity includes:

- symbol;
- NSE seq_id;
- official exchange dissemination timestamp;
- desc;
- attchmntText;
- attchmntFile.

Rows lacking canonical identity fail the D001 source run closed.

The same canonical announcement ID may not occur in two daily responses.

## Frozen special-situation taxonomy

Match case-insensitive normalized:

`desc + attchmntText`

One event may match multiple categories.

### BUYBACK

Tokens:

- buyback;
- buy back.

### OPEN_OFFER_CONTROL

Tokens:

- open offer;
- change of control;
- substantial acquisition of shares;
- takeover offer.

### DELISTING

Tokens:

- delisting;
- delist.

### SCHEME_REORGANISATION

Tokens:

- scheme of arrangement;
- merger;
- amalgamation;
- demerger;
- de-merger;
- spin off;
- spin-off.

### RIGHTS_ISSUE

Tokens:

- rights issue;
- right issue;
- rights entitlement.

### PREFERENTIAL_WARRANT

Tokens:

- preferential issue;
- preferential allotment;
- preferential basis;
- warrants;
- warrant allotment.

### ASSET_SALE_DIVESTMENT

Tokens:

- slump sale;
- divestment;
- divestiture;
- sale of undertaking;
- sale of business;
- asset sale;
- disposal of undertaking.

### INSOLVENCY_RESOLUTION

Tokens:

- insolvency;
- cirp;
- resolution plan;
- nclt;
- liquidation.

### CAPITAL_REDUCTION

Tokens:

- reduction of capital;
- capital reduction.

### OFFER_FOR_SALE

Tokens:

- offer for sale;
- ofs by promoter;
- promoter ofs.

### TENDER_OFFER

Tokens:

- tender offer;
- tendering of shares.

These are semantic event buckets, not bullish/bearish labels.

An announcement matching at least one category is a `SPECIAL_SITUATION_CANDIDATE`.
Otherwise it is out of D001's candidate event set.

## Current-identity mapping

Candidate announcements are mapped to the frozen current SS001 universe only by exact
current NSE symbol.

No fuzzy company-name matching is permitted.

If the event symbol does not map to a current D001 identity, retain it as
`CURRENT_IDENTITY_UNMAPPED` rather than dropping it.

For mapped rows retain D001 context:

- current ISIN;
- listing date/age;
- median 20-session traded value;
- observed session count;
- existing-U001 overlap.

D001 does not use those fields to rank candidates.

## Feasibility gates

D001 passes only when:

1. every calendar date in the frozen source window is successfully queried;
2. every source row has a valid canonical announcement identity;
3. no canonical identity is duplicated across daily responses;
4. all mapped candidate identities are exact symbol matches;
5. at least 90% of candidate events map to current SS001 identities.

The 90% mapping threshold is a source-identity completeness gate, not an investment rule.

## Output

Produce:

- exact daily source manifest/hashes;
- all canonical special-situation candidate events;
- taxonomy counts;
- distinct candidate symbols;
- mapped/unmapped counts;
- current D001 context for mapped names;
- attachment metadata/URL as supplied by NSE.

## Promotion

Passing D001 permits separately frozen:

- SS002-D002 candidate attachment acquisition;
- LLM extraction of transaction terms, dates, dependencies and documents;
- deterministic scenario/payoff modeling per event family.

The LLM is not permitted to invent transaction terms that are absent from source
documents.

## Explicit exclusions

D001 does not:

- download attachment bodies;
- use LLM classification;
- estimate completion probability;
- value consideration;
- calculate arbitrage spread;
- use future returns;
- rank candidates;
- create ADO/PF001 eligibility;
- authorize live capital.
