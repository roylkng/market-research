# HG006-S003 Full-Priority Historical Stage-Evidence Pack v1

Status: **FROZEN BEFORE HG006-D001B-P2 OUTPUT IS OPENED**  
Frozen: 2026-10-07  
Expanded-population terminal labels opened: no  
Expanded-population completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Compress the complete HG006 priority-family historical text corpus into deterministic
stage/anchor evidence for all 1,043 PREFERENTIAL_WARRANT and SCHEME_REORGANISATION
chronologies.

S003 is the full-population analogue of HG006-S002.

It changes population size only. It does not change retrieval vocabulary, ranking rules,
LLM semantics, episode threading, terminal labeling or probability estimation.

## Frozen inputs

### Historical source census

HG006-D001-v1:

- run: `37347148756`;
- artifact: `11361421023`;
- census SHA-256:
  `a267dab9cd646ffdc5230f1899a16a4138733413a3f05f438edf639f18ad41a5`.

### Full-priority text corpus

HG006-D001B-P2-v1, produced only under:

`research/HG006_D001B_P2_FULL_PRIORITY_TEXT_CORPUS_V1.md`.

Expected population:

- 1,043 chronologies;
- 1,038 attachment-ready chronologies;
- 5,353 unique document requests.

S003 may run only when D001B-P2 itself passes its frozen feasibility gates.

## Phrase vocabulary

Use exactly the phrase groups frozen in HG006-S002-v1:

### Terminal

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

### Approval/stage

Use exactly the HG006-S002 APPROVAL_STAGE phrase group.

### Scheme anchor

Use exactly the HG006-S002 SCHEME_ANCHOR phrase group.

### Warrant anchor

Use exactly the HG006-S002 WARRANT_ANCHOR phrase group.

No phrase is added after expanded-population text is opened.

## Document ordering

For every chronology:

1. use exact D001 events in that chronology;
2. map documents only through exact canonical event IDs;
3. chronology document timestamp = earliest linked exact D001 event timestamp;
4. tie break by document_id.

## Document retention

Use exactly HG006-S002-v1:

1. earliest TEXT_READY document;
2. latest TEXT_READY document;
3. every document with terminal-language match;
4. top four additional documents by:
   - distinct frozen phrase groups;
   - total phrase occurrences;
   - earlier chronology timestamp;
   - document_id.

Terminal-match documents are not dropped to satisfy the additional-document cap.

## Segment retention

Use exactly HG006-S002-v1:

1. first non-empty segment;
2. last non-empty segment;
3. every terminal-language segment;
4. top four additional segments by:
   - distinct frozen phrase groups;
   - total phrase occurrences;
   - source order;
   - segment_id.

## Chronology states

Exactly:

- EVIDENCE_READY;
- TEXT_UNAVAILABLE.

No unavailable chronology is imputed.

## Feasibility gates

S003 passes only when:

1. all 1,043 priority chronologies are accounted for exactly once;
2. every retained document maps to the same exact symbol/family chronology;
3. every retained segment exists in D001B-P2 and its text SHA verifies;
4. at least 95% of the 1,038 attachment-ready chronologies are EVIDENCE_READY;
5. every retained document has at least one selected segment;
6. no expanded-population terminal label, completion probability, current P001 result or
   stock return enters evidence selection.

## Promotion

Passing S003 permits:

- HG006-L001-P3 full-priority historical inference under the unchanged
  HG006-L001-v1 extraction ontology;
- D003-P3 deterministic episode threading under the unchanged D003-P2 transaction-
  identity rules;
- D002-P2 terminal labeling under the unchanged family ontology;
- D004-P2 expanded competing-risk base-rate estimation;
- P001-P2 rerun with the original current cases and unchanged publication thresholds.

## Scientific boundary

S003 does not:

- assign transaction outcome;
- estimate probability;
- use return outcomes;
- select cases based on completion/failure;
- change current-company payoff values;
- authorize ADO/PF001/live capital.
