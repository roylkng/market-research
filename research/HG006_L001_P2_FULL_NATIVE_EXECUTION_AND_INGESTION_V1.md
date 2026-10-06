# HG006-L001-P2 Full Native Historical Execution and Ingestion v1

Status: **FROZEN AFTER P0 PASS, BEFORE FULL-QUEUE MODEL OUTPUT**  
Frozen: 2026-10-06  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Execute and ingest the already-frozen 1,448-request HG006-L001-P1 historical stage/anchor
queue after the preregistered 20-request native feasibility pilot passed.

P2 changes execution/ingestion mechanics only.

It does not change:

- the queue;
- any prompt bytes;
- the GPT-5.6 Sol model configuration;
- the HG006-L001 semantic contract;
- the historical calibration cohort;
- family definitions;
- stage/anchor vocabularies;
- terminal-language ontology.

## Frozen authorities

### Queue

- queue ID: `HG006-L001-P1-v1`;
- workflow run: `37416900979`;
- artifact ID: `11391401173`;
- artifact name: `hg006-l001-p1-queue-37416900979`;
- queue SHA-256:
  `6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934`;
- request count: 1,448;
- shard count: 16.

### Model configuration

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- model-config SHA-256:
  `043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d`.

### Passed P0

- result: `HG006-L001-P0-v1`;
- workflow run: `37421844965`;
- artifact ID: `11393655594`;
- selection SHA-256:
  `e39f0baba4d643fcf9a8bc388806f0f799938be3a399f3b09de20306a601962f`;
- run SHA-256:
  `0b606aa4b3c27545d150dd046d3c0f2c5fb68d3380f310095be82754bfca1a79`;
- 20/20 validated;
- full 20-document manual audit passed.

## P0 response reuse

The exact 20 P0 request IDs are part of the 1,448-request full queue.

P2 reuses those validated responses rather than asking the model to answer the same
prompt again.

Reuse is permitted only when all frozen identities match:

- request_id;
- document_id;
- prompt SHA-256;
- model-config SHA-256;
- raw-model-response SHA-256;
- validated structured-output SHA-256.

A mismatch fails closed.

P0 reuse is transport deduplication, not a change to the inference result.

## Remaining full-run requests

Exactly 1,428 queue requests require fresh GPT-5.6 Sol native output.

No request-specific prompt changes are allowed.

No output may use:

- historical terminal labels from D002;
- later documents outside that request;
- current company status;
- stock prices or returns;
- hidden-gem rankings;
- completion probabilities.

## Native raw-response convention

For every fresh model request:

1. the model produces only the HG006-L001 substantive JSON payload;
2. provenance remains host-managed;
3. canonical JSON bytes of the pre-provenance payload are retained as
   `raw_model_response_bytes`;
4. SHA-256 of those bytes becomes `raw_model_response_sha256`;
5. host code injects exact queue/model provenance;
6. `validate_and_seal_response` validates and seals the output.

This is the same convention used by the passed P0 and prior SS002 native pilots.

## Shard response input

Each of the 16 frozen shards has one response bundle.

Bundle identity:

`HG006-L001-P2-SHARD-<00..15>-v1`

Every non-P0 request in that shard must appear exactly once with one state:

- `MODEL_OUTPUT`;
- `MODEL_FAILURE`.

MODEL_OUTPUT carries the pre-provenance substantive JSON object.

MODEL_FAILURE carries a non-empty error description and no model output.

There is no silent omission.

## Validation states

After deterministic ingestion every queue request becomes exactly one:

- `VALIDATED`;
- `MODEL_FAILURE`;
- `VALIDATION_FAILURE`.

A validation failure retains:

- request ID;
- raw payload SHA when available;
- validator error;
- shard ID.

No invalid response is repaired with request-specific hints inside P2.

A later identical-prompt transport retry may be registered separately, but cannot
overwrite the original failed observation.

## Shard gates

Each shard bundle must prove:

1. exact frozen shard ID;
2. exact frozen queue/model hashes;
3. complete accounting of all non-P0 requests belonging to that shard;
4. no request from another shard;
5. no duplicate request ID;
6. P0 seeded rows match exact P0 provenance;
7. zero opened terminal outcome labels or return outcomes.

A shard may be persisted even when some model/validation failures occur.

## Full-run gates

Full HG006-L001 response ingestion passes only when:

1. all 1,448 queue requests are accounted for exactly once;
2. all 16 shard IDs are present exactly once;
3. at least 95% of all requests are VALIDATED;
4. at least 95% of the 298 EVIDENCE_READY chronologies have at least one VALIDATED
   document;
5. zero validated responses contain invalid evidence references;
6. zero validated responses invent event IDs, symbol, family or document ID;
7. zero validated responses contain forbidden probability/return/advice fields;
8. the exact P0 20-response audit sample remains byte/provenance consistent.

If the gate fails, D003 threading may not begin.

## Manual audit

The P1 manual-audit rule was:

- first 10 request IDs lexicographically per family;
- maximum 20 requests.

That set is exactly the P0 sample already audited in full.

P2 therefore reuses the passed P0 manual audit and does not select a different
post-output sample.

## Promotion

Passing P2 permits, in order:

1. HG006-D003 evidence-bound transaction-episode threading;
2. HG006-D002 family-specific terminal outcome labeling;
3. HG006-D004 stage-conditioned historical base-rate estimation.

Terminal labels may not be opened before the P2 full-run ingestion gate passes.

## Scientific boundary

P2 does not:

- label transaction episodes completed/failed;
- estimate historical completion rates;
- estimate current-case completion probability;
- use stock returns;
- calculate expected returns;
- modify current hidden-gem ranking;
- authorize ADO/PF001/live capital.
