# HG006-L001-P3 Full-Priority Historical Inference Extension v1

Status: **FROZEN BEFORE FULL-PRIORITY MODEL OUTPUT**  
Frozen: 2026-10-08  
Expanded-population terminal labels opened: no  
Expanded-population completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Extend the already-passed HG006-L001 historical stage/anchor extraction from the original
300-chronology calibration cohort to the complete 1,043-chronology priority-family
population prepared by HG006-S003.

P3 changes population coverage only.

It does not change:

- HG006-L001 semantic contract;
- stage vocabulary;
- transaction-anchor vocabulary;
- terminal-language vocabulary;
- GPT-5.6 Sol model configuration;
- evidence citation rules;
- episode-threading rules;
- terminal-label ontology;
- completion-probability publication thresholds.

## Frozen full-priority source

Use exactly HG006-S003-v1:

- workflow run: `37665220935`;
- artifact ID: `11503965165`;
- artifact name: `hg006-p2-full-priority-37665220935`;
- pack SHA-256:
  `ebd2943f9c41e4eb93fca9039cb73143150d2eb1c8d7b3d101e1fd0f9614dc03`;
- chronology count: 1,043;
- EVIDENCE_READY: 1,032;
- TEXT_UNAVAILABLE: 11;
- retained chronology-document rows: 4,822;
- retained segments: 23,075.

Families remain exactly:

- PREFERENTIAL_WARRANT;
- SCHEME_REORGANISATION.

## Frozen prior inference authorities

### Original queue

HG006-L001-P1-v1:

- workflow run: `37416900979`;
- artifact ID: `11391401173`;
- queue SHA-256:
  `6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934`;
- request count: 1,448;
- evidence-ready chronologies: 298.

### Passed full ingestion

HG006-L001-P2-v1:

- workflow run: `37638982587`;
- artifact ID: `11491395735`;
- ingestion SHA-256:
  `2188bf803f2088cd10f26892f92f1a82fc810543ad9679c4fc20534e2a3e59e6`;
- 1,448 / 1,448 requests VALIDATED.

## Frozen model configuration

Reuse exactly the original configuration:

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- semantic temperature target: 0.0;
- semantic top_p target: 1.0;
- maximum structured-output budget: 4096 tokens;
- semantic contract: `HG006-L001-v1`;
- structured output mode: JSON object.

Model-config SHA-256 remains:

`043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d`

## Exact prior-response reuse

P3 may reuse a P2 validated response only when the S003 chronology-document row is
semantically and evidentially identical to its original P1 request.

All of the following must match exactly:

- chronology_id;
- document_id;
- symbol;
- family;
- event_ids;
- chronology timestamp;
- selected segment objects and order;
- segment_manifest_sha256;
- required-output template semantics;
- model-config SHA-256;
- system prompt.

The corresponding P2 ingestion row must also be VALIDATED.

A changed evidence manifest or any changed prompt field forces fresh inference.

A source-only comparison frozen before P3 model output found:

- original chronology-document pairs retained in S003: 1,448;
- exact reusable prior prompts/responses: 1,443;
- prior pairs requiring fresh inference because provenance changed: 5;
- new S003 chronology-document pairs: 3,374;
- total fresh P3 inference requests: 3,379.

These counts are now frozen.

## Request identity

P3 queue identity:

`HG006-L001-P3-v1`

For a reused request, retain the exact original P1 request_id and prompt bytes.

For a fresh P3 request:

`request_id = SHA256("HG006-L001-P3-v1|" + chronology_id + "|" + document_id + "|" + segment_manifest_sha256)`

Including segment-manifest identity prevents a changed evidence envelope from colliding
with an earlier request for the same chronology/document.

## Fresh prompt

Fresh requests use the exact HG006-L001 system instruction:

> Extract only explicit historical transaction stage, terminal-language and transaction
> anchor facts from the supplied official source segments. Use no outside knowledge,
> market prices, later company status, historical returns or current hidden-gem
> conclusions. Every explicit claim must cite supplied segment IDs. Preserve the frozen
> family; if document economics conflict, emit family_semantic_conflict with evidence.
> Do not group transaction episodes and do not estimate completion probability.

The request payload contains:

- P3 request identity;
- chronology_id;
- document_id;
- exact event IDs;
- exact symbol;
- exact family;
- chronology timestamp;
- exact selected segments and hashes;
- segment-manifest SHA;
- frozen HG006-L001 output template.

## Sharding

Fresh requests only:

`shard_id = int(request_id[0:8], 16) mod 16`

Shard IDs: 0 through 15.

Reused responses do not consume fresh model execution capacity.

## Queue gates

P3 queue materialization passes only when:

1. exactly 1,043 chronologies are accounted for;
2. exactly 1,032 are EVIDENCE_READY and 11 TEXT_UNAVAILABLE;
3. exactly 4,822 chronology-document requests are accounted for;
4. exactly 1,443 rows are P2_VALIDATED_REUSE;
5. exactly 3,379 rows are FRESH_MODEL_REQUIRED;
6. all reused rows match exact original prompt/evidence semantics and a VALIDATED P2 row;
7. all fresh request IDs are unique and do not collide with reused request IDs;
8. all retained segment text hashes verify;
9. no expanded-population terminal label, completion probability, current-case outcome or
   stock return is used.

Counts may not be changed after queue output is opened.

## Full P3 ingestion gate

After fresh inference:

1. all 4,822 requests must be accounted for exactly once;
2. all 1,443 reuse rows must retain exact P2 validated-response provenance;
3. all 16 fresh shards must be present;
4. at least 95% of the 3,379 fresh requests must validate;
5. at least 95% of the 1,032 EVIDENCE_READY chronologies must have at least one VALIDATED
   request after reuse + fresh inference;
6. zero validated responses may invent evidence, symbol, family, event or document identity;
7. zero forbidden probability/return/advice fields may appear.

## Promotion

Passing full P3 ingestion permits, under unchanged downstream rules:

1. deterministic full-population D003 episode threading;
2. full-population D002 terminal labeling;
3. expanded D004 stage-conditioned historical base-rate estimation;
4. rerunning P001 on the same current cases using unchanged publication thresholds.

## Scientific boundary

P3 does not:

- use stock returns;
- choose historical cases based on completion/failure;
- loosen survivor-conditioned support gates;
- introduce parametric survival assumptions;
- alter current payoff calculations;
- create expected return;
- create buy/sell/hold;
- authorize ADO/PF001/live capital.
