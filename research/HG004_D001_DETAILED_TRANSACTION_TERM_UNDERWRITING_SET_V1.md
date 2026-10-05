# HG004-D001 Detailed Transaction-Term Underwriting Set v1

Status: **FROZEN BEFORE DETAILED TERM EXTRACTION**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Expand every currently active or procedurally unresolved special-situation thread inside
the fixed 28-name HG002 hidden-gem cohort into its complete official-document history
within the frozen SS002 event window.

HG004-D001 is a document-selection contract. It does not estimate intrinsic value,
completion probability or expected return.

## Frozen source chain

Use exactly:

- HG003-L002-v1;
- workflow run: `37277006068`;
- artifact ID: `11330766430`;
- synthesis SHA-256:
  `ebe3b8f666a83b18695eca69c649ab6c66d721f157ebe6ed0d61e71ef4f937ea`;

and:

- SS002-D001-P2-v1;
- workflow run: `37203696204`;
- artifact ID: `11303667832`;
- census SHA-256:
  `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`;

and:

- SS002-D003-v1;
- workflow run: `37213853198`;
- artifact ID: `11309315028`;
- corpus SHA-256:
  `92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce`.

No later rerun may be substituted under HG004-D001-v1.

## Frozen company states admitted

Exactly HG003-L002 companies whose state is:

- `ACTIVE_DIRECT_CATALYST`; or
- `PROCEDURAL_DIRECT_REVIEW`.

Expected symbols:

- ANANTRAJ
- AXITA
- DATAMATICS
- DEVX
- FCL
- INOXGREEN
- NPST
- SAMBHV
- SANDESH
- SUVIDHAA
- TREL

No completed, cancelled, indirect/context-only, or text-pending company enters D001.

## Frozen semantic clusters admitted

For every admitted company, retain every HG003-L002 cluster whose latest relevance group
is `CURRENT_ECONOMIC_RELEVANCE` and whose stage group is one of:

- `ACTIVE_FORWARD_STAGE`;
- `PROCEDURAL_STAGE`.

Expected semantic-cluster count: **13**.

No cluster may be removed because its economics appear unattractive.

## Full thread expansion

For each admitted HG003 semantic cluster:

1. read its exact `member_thread_ids`;
2. each member thread ID is exactly `<SYMBOL>::<UPSTREAM_CATEGORY>`;
3. from SS002-D001-P2 retain every event satisfying all:
   - exact current symbol match;
   - `mapping_state == CURRENT_INVESTABLE_IDENTITY`;
   - upstream `special_situation_categories` contains the member thread category;
4. require the event's approved attachment URL to resolve to a TEXT_READY SS002-D003
   document;
5. retain **all** such event/documents in exchange-publication order ascending.

No "latest only" rule is used in HG004-D001. Earlier originating documents are required
so a monitoring/procedural update cannot hide the transaction's original economics.

Expected expanded event/document count: **26**.

## Prompt materialization

Every selected document receives one standard SS002-L001-v1 prompt envelope with:

- exact document_id;
- all canonical event IDs linked to that document;
- exact symbol set;
- upstream category hints;
- deterministic D003 text segments;
- segment-manifest SHA-256.

The prompt uses the existing evidence-bound L001 contract without family-specific
weakening.

## Detailed extraction scope

HG004-L001, if D001 passes, is authorized to populate all explicit L001 fact families:

- parties;
- security economics;
- consideration;
- entitlement/ratios;
- dates;
- conditions/approvals;
- business economics.

UNKNOWN remains mandatory when a term is absent.

## Frozen feasibility gates

D001 passes only when all are true:

1. exactly 11 admitted symbols;
2. exactly 13 admitted semantic clusters;
3. exactly 26 selected event/documents;
4. every selected document is TEXT_READY;
5. every selected document has a deterministic prompt SHA-256;
6. every admitted cluster retains at least one document;
7. no return, valuation, future-price or portfolio outcome influences selection.

## Promotion

Passing HG004-D001 permits:

- HG004-L001 detailed evidence-bound extraction over all 26 documents;
- deterministic transaction-thread term synthesis;
- family-specific payoff/scenario design after explicit terms are available.

## Scientific boundary

HG004-D001 does not:

- calculate event spread;
- infer probability of completion;
- estimate intrinsic value;
- rank the 11 companies;
- drop a company because terms look poor;
- create ADO/PF001/live-capital eligibility.
