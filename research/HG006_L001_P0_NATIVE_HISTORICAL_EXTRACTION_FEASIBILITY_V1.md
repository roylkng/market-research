# HG006-L001-P0 Native Historical Extraction Feasibility Pilot v1

Status: **FROZEN BEFORE PILOT MODEL OUTPUT**  
Frozen: 2026-10-06  
Historical terminal labels opened: no  
Completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Validate that GPT-5.6 Sol can apply the frozen HG006-L001 evidence-bound historical
stage/anchor contract reliably on a deterministic sample of the already-frozen
HG006-L001-P1 queue before scaling to all 1,448 requests.

P0 is a model-execution feasibility pilot. It does not estimate a base rate.

## Frozen source queue

Use exactly:

- HG006-L001-P1-v1;
- workflow run: `37416900979`;
- artifact ID: `11391401173`;
- artifact name: `hg006-l001-p1-queue-37416900979`;
- queue SHA-256:
  `6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934`;
- model-config SHA-256:
  `043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d`.

## Deterministic sample

For each frozen family independently:

1. take all queue rows for the family;
2. sort by exact request_id ascending;
3. select the first 10.

Families:

- PREFERENTIAL_WARRANT;
- SCHEME_REORGANISATION.

Exactly 20 requests are selected.

No symbol, date, wording, stage, terminal language, outcome, document length or current
company relevance affects selection.

## Model/runtime

Exactly the frozen queue configuration:

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- semantic temperature target: 0.0;
- semantic top_p target: 1.0;
- maximum structured-output budget: 4096 tokens per request;
- contract: `HG006-L001-v1`.

No web search, model memory, market price, later company status, stock return or current
hidden-gem conclusion may enter the extraction.

## Required extraction

For each of 20 prompts return the frozen HG006-L001 structure:

- stage_observations;
- explicit_terminal_language;
- terminal evidence;
- transaction anchors;
- family semantic conflict when required;
- unresolved questions;
- contradictions;
- caveats;
- complete frozen provenance.

Every explicit stage, terminal claim and anchor requires supplied segment IDs.

## Pilot mechanical gates

P0 passes mechanically only if:

1. exactly 20 outputs are present;
2. all 20 pass `validate_and_seal_response`;
3. zero invalid evidence references;
4. zero invented event IDs, symbols, families or document IDs;
5. zero forbidden probability/return/advice fields;
6. at least 18/20 outputs contain at least one explicit information item:
   - non-UNKNOWN stage observation; or
   - explicit terminal language; or
   - transaction anchor.

A genuinely evidence-sparse document may therefore remain sparse without fabrication.

## Full manual audit

All 20 outputs are manually checked against their exact supplied source segments.

For each output record:

- unsupported_explicit_claim_count;
- material_stage_or_anchor_missed;
- unretained_material_contradiction_count;
- audit notes.

Pilot audit passes only if:

1. unsupported explicit claim count = 0 across all 20;
2. unretained material contradictions = 0 across all 20;
3. no more than 2 of 20 have a material stage/anchor miss.

No output may be repaired with request-specific prompt wording inside P0.

## Promotion

Passing P0 authorizes execution of the frozen full HG006-L001-P1 queue without changing
its prompt or model configuration.

Failing P0 requires a separately frozen contract/version before full execution.

## Scientific boundary

P0 does not:

- assign episode-level COMPLETED/FAILED labels;
- group transaction episodes;
- estimate historical completion probability;
- use stock returns;
- change current hidden-gem rankings;
- create expected return, ADO, PF001 or live-capital eligibility.
