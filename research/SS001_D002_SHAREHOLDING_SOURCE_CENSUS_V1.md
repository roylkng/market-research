# SS001-D002 Full-Market Shareholding Source Census v1

Status: **FROZEN BEFORE SOURCE DIAGNOSTIC**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Extend the passed SS001-D001 full-market census with official NSE quarterly
shareholding-pattern source availability.

D002 is a source-index diagnostic only. It does not parse promoter quality, pledges,
institutional ownership or governance scores.

## Frozen input universe

Use exactly the SS001-D001 census produced by:

- workflow run: `37197575401`;
- artifact ID: `11301695772`;
- artifact name: `ss001-d001-37197575401`;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- current EQ identity count: 2,319.

No security may be added or removed because its shareholding source is easier to acquire.

## Official source

For each D001 NSE symbol query:

`https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=<SYMBOL>`

Reuse the already-audited H023 source acquisition and filing-selection semantics.

Raw master JSON bytes are retained and content-hashed per symbol.

## Frozen filing selection

As of the D002 acquisition timestamp:

1. consider standard calendar quarter-end filings only;
2. for each report date, use the latest publicly broadcast revision;
3. latest source = most recent standard quarter end available;
4. prior source = immediately preceding standard calendar quarter when available;
5. XBRL URL must be on an approved NSE archive host;
6. duplicate/conflicting record identity fails closed.

D002 does not download the XBRL document.

## Output per symbol

Retain:

- source state: READY / NO_STANDARD_QUARTER / REQUEST_FAILED / PARSE_FAILED;
- latest report date;
- latest record ID;
- latest broadcast timestamp;
- latest XBRL URL;
- latest master-row hash where available;
- formal revision state/date where available;
- whether the immediately previous quarter source is available;
- prior report date / record ID / XBRL URL when available;
- raw master-response SHA-256.

## Frozen feasibility thresholds

D002 passes only when:

1. at least 85% of the 2,319 frozen D001 identities have a valid latest standard-quarter
   shareholding source;
2. at least 75% have both latest and immediately prior standard-quarter sources;
3. every successful source uses an approved NSE archive URL;
4. all 2,319 identities are accounted for exactly once as success or explicit failure.

Thresholds may not be lowered after output is opened.

## Promotion

Passing D002 permits a separately frozen GF001 source/parser experiment to download
shareholding XBRL and extract governance/ownership facts such as:

- promoter/promoter-group ownership;
- public ownership;
- promoter pledge/encumbrance;
- FII/FPI ownership;
- DII / mutual-fund ownership;
- ownership concentration and quarter-over-quarter changes.

D002 itself does not define those concepts.

## Explicit exclusions

D002 does not:

- score governance;
- interpret promoter ownership as good or bad;
- parse pledge percentages;
- rank institutional ownership;
- use returns;
- filter the SS001 universe;
- create ADO/PF001 eligibility;
- permit live capital.
