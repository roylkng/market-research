# HG003-D001 Cohort Special-Situation Thread Gate v1

Status: **FROZEN BEFORE COHORT-WIDE LLM OUTPUT**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Convert the fixed 28-name HG002 underwriting cohort into a finite, evidence-addressed
special-situation thread set suitable for cohort-wide L001 economic-relevance and stage
validation.

HG003-D001 does not estimate return, completion probability or intrinsic value.

## Frozen source chain

Use exactly:

- HG002-D001-v1;
- workflow run: `37260536415`;
- artifact ID: `11324486396`;
- cohort SHA-256:
  `3937b8cb83ef819ff956af4afebb80cd81d8ef233c1e4dd5b6d3688541a48db1`;

- SS002-D001-P2-v1;
- workflow run: `37203696204`;
- artifact ID: `11303667832`;
- census SHA-256:
  `ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071`;

- SS002-D003-v1;
- workflow run: `37213853198`;
- artifact ID: `11309315028`;
- text-corpus SHA-256:
  `92d785de20af9bcca370c13a9d410fe98f0728518527285fa15d1490dadd32ce`;

- SS002-L001-v1 evidence-bound extraction contract.

No later rerun may be substituted under HG003-D001-v1.

## Frozen thread identity

For each HG002 company and each category in its frozen
`special_situation_categories`, define one thread:

`thread_id = SYMBOL + "::" + SPECIAL_SITUATION_CATEGORY`

The expected frozen cohort contains exactly **35** such threads.

No category may be added from company-name recognition or later document interpretation.

## Frozen text-ready selection rule

For each thread independently:

1. start from P2 `CURRENT_INVESTABLE_IDENTITY` events;
2. require exact symbol match;
3. require the thread category to be present in the frozen P2 event taxonomy;
4. resolve the event to the D003 document manifest by exact canonical
   `announcement_id` membership in `event_ids`;
5. require D003 `extraction_state == READY`;
6. sort qualifying events by exchange publication timestamp descending;
7. tie-break by canonical announcement_id ascending;
8. select the first qualifying event/document pair.

If multiple READY documents contain the same selected event ID, select the
lexicographically smallest document_id and retain the ambiguity count.

No fuzzy URL matching or company-name matching is permitted.

## Unresolved thread state

If a thread has P2 current events but no D003 TEXT_READY document, preserve:

`TEXT_UNAVAILABLE`

along with every exact event/document extraction state explaining the failure.

The company remains in HG002. It is not silently dropped.

Source-only inspection before freezing indicates:

- expected thread count: 35;
- expected TEXT_READY thread count: 34;
- expected unresolved thread:
  `HINDCOPPER::OFFER_FOR_SALE`;
- HINDCOPPER's two exact PDFs are image-only under D003
  (`NO_EXTRACTABLE_TEXT`).

These counts are part of the frozen source expectation, not a return hypothesis.

## L001 prompt envelope

For every TEXT_READY selected document, build exactly one prompt envelope under
`SS002-L001-v1`.

The envelope contains:

- document_id;
- exact source URL;
- all D003 event IDs attached to that document;
- exact symbols attached to that document;
- D003 category hints;
- deterministic text segments;
- segment manifest SHA-256.

The LLM has no access to market price, future returns or HG003 valuation logic.

## D001 output

For every one of the 35 threads retain:

- symbol;
- category;
- thread_id;
- selection state;
- selected announcement_id;
- selected exchange timestamp;
- selected document_id;
- source URL;
- segment count;
- segment manifest SHA-256;
- prompt SHA-256;
- exact candidate event count;
- exact text-ready candidate count;
- unresolved evidence when applicable.

## Frozen gates

D001 passes only if:

1. exactly 28 HG002 symbols are retained;
2. exactly 35 frozen threads are accounted for;
3. exactly 34 threads are TEXT_READY;
4. exactly one thread is TEXT_UNAVAILABLE;
5. the unresolved thread is exactly HINDCOPPER::OFFER_FOR_SALE;
6. every TEXT_READY prompt validates deterministic segment identities;
7. no company is dropped because its event is indirect, procedural or economically weak.

## Promotion

Passing D001 permits:

- HG003-L001 cohort-wide relevance/stage extraction for all 34 text-ready threads;
- a separately frozen image-document path for HINDCOPPER;
- L002 transaction-thread synthesis after L001 outputs exist;
- deterministic family-specific payoff modeling only after economic relevance is known.

## Scientific boundary

HG003-D001 does not:

- decide whether a special situation is attractive;
- create expected-return scores;
- rank the 28 companies;
- drop a company after recognizing its name;
- override EI001/HA001/GF001 facts;
- authorize ADO/PF001/live capital.
