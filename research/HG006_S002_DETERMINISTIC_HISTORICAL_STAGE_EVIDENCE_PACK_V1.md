# HG006-S002 Deterministic Historical Stage-Evidence Pack v1

Status: **FROZEN BEFORE HG006-L001 HISTORICAL MODEL OUTPUT**  
Frozen: 2026-10-06  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Reduce the exact HG006-D001B historical text corpus into a compact, deterministic
evidence pack suitable for full-cohort HG006-L001 stage/anchor extraction.

S002 is a retrieval/routing layer only. It does not decide stage, completion, failure,
episode identity, probability or return.

## Frozen sources

### Historical calibration cohort

Use exactly HG006-S001-v1:

- workflow run: `37412353114`;
- artifact ID: `11389870466`;
- selection SHA-256:
  `4bc9659c1111f0694bbbec8754b6193116871367b78f126c39e09bc329c961f5`;
- exactly 300 selected chronologies.

### Historical source census

Use exactly HG006-D001-v1:

- workflow run: `37347148756`;
- artifact ID: `11361421023`;
- census SHA-256:
  `a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5`.

The D001 event timestamps are used only to order evidence in time.

### Selected historical text

Use exactly HG006-D001B-v1:

- workflow run: `37413266182`;
- combined artifact ID: `11390596323`;
- corpus SHA-256:
  `4f841df6599d4836b1a7798439f69eb889690da19942cf48f41d4752b57d4ce9`;
- 1,607 selected documents;
- 1,599 TEXT_READY documents;
- 15,066 deterministic text segments;
- 298/300 chronologies with at least one TEXT_READY document.

The eight exact D001B text-shard artifacts from the same run are the authoritative text
payloads.

## Core principle

Evidence compression must be independent of historical success/failure labels.

S002 may select text because it contains generic transaction-stage, approval, anchor or
terminal vocabulary frozen below.

It may not prefer a document because a human/model has already decided that the
transaction succeeded or failed.

## Frozen phrase groups

All matching is case-insensitive Unicode-NFKC text matching after collapsing whitespace.

### Terminal-language group

- completed
- completion
- consummated
- implemented
- became effective
- effective from
- effective date
- has become effective
- made effective
- withdrawn
- withdrawal
- cancelled
- canceled
- cancellation
- terminated
- termination
- abandoned
- not proceeded
- not proceed
- rejected
- rejection
- forfeited
- forfeiture
- extinguishment
- extinguished

### Approval / stage group

- board of directors
- board meeting
- board approved
- shareholders approved
- shareholder approval
- special resolution
- voting results
- scrutinizer
- in-principle approval
- in principle approval
- stock exchange approval
- no objection
- no-objection
- nclt
- national company law tribunal
- tribunal
- sanctioned
- sanction
- regulatory approval
- record date
- offer opens
- offer opening
- offer closes
- offer closing
- allotment
- allotted
- issue and allot
- conversion
- converted
- exercise of warrants
- exercise warrant
- registrar of companies
- roc filing
- filed with roc

### Scheme anchor group

- scheme of arrangement
- composite scheme
- demerger
- de-merger
- amalgamation
- merger
- transferor company
- transferee company
- resulting company
- appointed date
- exchange ratio
- share entitlement ratio
- case number
- company petition

### Preferential / warrant anchor group

- preferential issue
- preferential allotment
- preferential basis
- convertible warrant
- warrants
- warrant
- issue price
- exercise price
- allottee
- allottees
- promoter group
- consideration
- number of warrants
- number of securities
- conversion price
- balance consideration

These phrases are frozen before S002 output is opened.

## Document ordering

For each selected chronology:

1. use D001 canonical events belonging to that chronology;
2. map D001B documents through exact canonical event IDs;
3. document chronology time = earliest linked canonical event timestamp inside that
   chronology;
4. tie break by document_id.

No inferred filing date or document text date is used for ordering.

## Document retention

For a chronology with TEXT_READY documents retain the union of:

1. earliest TEXT_READY document;
2. latest TEXT_READY document;
3. every document containing at least one terminal-language-group match;
4. top four additional documents by:
   - number of distinct frozen phrase groups matched;
   - then total frozen phrase occurrences;
   - then earlier chronology time;
   - then document_id.

Maximum non-terminal/top-ranked additions: four.

Terminal-match documents are never dropped solely to satisfy a document-count cap.

This rule may therefore retain more than six documents when terminal vocabulary appears
in several documents.

## Segment retention inside a retained document

Retain the union of:

1. first non-empty segment;
2. last non-empty segment;
3. every segment containing terminal-language-group vocabulary;
4. top four additional segments by:
   - distinct frozen phrase groups matched;
   - total frozen phrase occurrences;
   - segment order;
   - segment_id.

Maximum non-terminal/top-ranked additions: four.

Terminal-match segments are never dropped solely to satisfy a segment-count cap.

## Output

Each chronology evidence row retains:

- chronology_id;
- symbol;
- frozen family;
- source event count;
- source document count;
- TEXT_READY source document count;
- retained document IDs in deterministic order;
- for each retained document:
  - exact event IDs;
  - chronology timestamp;
  - exact selected segment IDs;
  - exact text SHA-256s;
  - exact selected text;
  - frozen phrase-hit metadata;
- chronology evidence SHA-256.

Chronologies without TEXT_READY evidence remain explicit TEXT_UNAVAILABLE.

## Feasibility gates

S002 passes only if:

1. exactly all 300 S001 chronologies are accounted for;
2. every evidence document belongs to the same exact symbol/family chronology;
3. every selected segment exists in D001B and its text SHA-256 validates;
4. every chronology with D001B TEXT_READY coverage has at least one retained document;
5. the two D001B text-unavailable chronologies remain explicit and are not imputed;
6. no historical terminal label, probability, market return or current-case result
   participates in ranking/selection;
7. all evidence rows and their ordering are deterministic.

## Promotion

Passing S002 permits HG006-L001 model extraction for the exact 300-chronology cohort.

The model may interpret stage/anchors/terminal language only from S002-selected exact
segments.

## Scientific boundary

S002 does not:

- classify terminal outcome;
- decide whether explicit completion language satisfies family-specific completion;
- thread transaction episodes;
- estimate completion probability;
- use historical stock returns;
- compare current-company outcomes;
- create ADO/PF001/live-capital eligibility.
