# HG006-L001-P1 Sharded Historical Inference Queue v1

Status: **FROZEN BEFORE HISTORICAL MODEL OUTPUT**  
Frozen: 2026-10-06  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Materialize the exact model-request queue for HG006-L001 historical stage/anchor
extraction over the passed HG006-S002 evidence pack.

P1 changes execution topology only. It does not change the frozen HG006-L001 semantic
contract, stage vocabulary, anchor vocabulary, terminal-language ontology, or evidence
rules.

## Frozen source

Use exactly HG006-S002-v1:

- workflow run: `37416075608`;
- artifact ID: `11390794744`;
- artifact name: `hg006-s002-37416075608`;
- pack SHA-256:
  `e99f270bf48b76bb72f3e2734abddd34bcc580cb1583086cc73e50759e23766e`;
- 300 selected chronologies;
- 298 EVIDENCE_READY;
- 2 TEXT_UNAVAILABLE;
- 1,448 retained chronology-document rows;
- 6,767 retained source segments.

## Request unit

Exactly one request is created for every retained document inside every EVIDENCE_READY
chronology.

Request identity:

`request_id = SHA256("HG006-L001-P1-v1|" + chronology_id + "|" + document_id)`

The same document appearing in two chronologies creates two request identities because
the allowed event set and chronology context may differ.

TEXT_UNAVAILABLE chronologies create no model request and remain explicit source states.

## Frozen model configuration

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- semantic temperature target: 0.0;
- semantic top_p target: 1.0;
- maximum structured-output budget: 4096 tokens per request;
- contract: `HG006-L001-v1`;
- structured output mode: JSON object.

A later provider/runtime may replay the same queue only under a separately identified
model configuration. It may not overwrite this run.

## Prompt

Every request contains:

- request_id;
- chronology_id;
- document_id;
- exact event IDs;
- exact symbol;
- exact frozen family;
- exact chronology timestamp;
- exact selected segments, IDs and text hashes;
- source segment-manifest SHA;
- frozen HG006-L001 output template.

The system instruction is fixed:

> Extract only explicit historical transaction stage, terminal-language and transaction
> anchor facts from the supplied official source segments. Use no outside knowledge,
> market prices, later company status, historical returns or current hidden-gem
> conclusions. Every explicit claim must cite supplied segment IDs. Preserve the frozen
> family; if document economics conflict, emit family_semantic_conflict with evidence.
> Do not group transaction episodes and do not estimate completion probability.

## Sharding

`shard_id = int(request_id[0:8], 16) mod 16`

Shard IDs are 0 through 15.

Sharding changes transport topology only. Prompt bytes and request identities are
invariant to execution order.

## Response ingestion

Every response must pass the existing deterministic
`marketlab.hg006_stage_contract.validate_extraction` validator.

Additionally, response ingestion must prove:

- exactly one response per request_id;
- response document/event/symbol/family identity matches the queue;
- prompt SHA and model-config SHA match the frozen request;
- no request from a TEXT_UNAVAILABLE chronology is invented;
- raw model-response SHA is retained;
- validated output SHA is retained.

Failed/invalid responses remain explicit and may not be silently replaced.

## P1 execution gate

The historical run may proceed to D003 threading only after:

1. every queue request is accounted for as VALIDATED or explicit MODEL/VALIDATION_FAILURE;
2. at least 95% of requests are VALIDATED;
3. at least 95% of EVIDENCE_READY chronologies have at least one VALIDATED document;
4. zero validated outputs contain invalid evidence references;
5. zero validated outputs invent event IDs, symbols or families;
6. zero forbidden probability/return/advice fields appear.

No request-specific prompt amendment is allowed inside P1 after outputs are inspected.

## Manual audit

Before D003 threading, manually audit a deterministic sample:

- first 10 request_ids lexicographically per family;
- maximum 20 audited requests total.

Audit against exact cited source segments for:

- stage support;
- terminal-language support;
- anchor support;
- retained material ambiguity.

No outcome label is used to choose the audit sample.

## Scientific boundary

P1 does not:

- assign COMPLETED/FAILED episode labels;
- group documents into episodes;
- estimate completion probabilities;
- use stock returns;
- apply current-company outcomes;
- create expected return or portfolio eligibility.
