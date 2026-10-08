# HG006-L001-P3-T1 Deterministic 64-Batch Transport v1

Status: **FROZEN AFTER P3 QUEUE PASS, BEFORE FRESH P3 MODEL OUTPUT**  
Frozen: 2026-10-08  
Expanded-population terminal labels opened: no  
Expanded-population completion probabilities assigned: no  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Subdivide the 3,379 frozen HG006-L001-P3 fresh requests into smaller execution bundles
without changing any model input or scientific semantics.

This is transport topology only.

## Frozen queue

Use exactly:

- queue ID: `HG006-L001-P3-v1`;
- workflow run: `37676966302`;
- artifact ID: `11506179774`;
- artifact name: `hg006-l001-p3-queue-37676966302`;
- queue SHA-256:
  `0b93d72fa063c05568cb508b4c4249ad14dff48fa2900209750059a5ca954429`;
- total requests: 4,822;
- P2_VALIDATED_REUSE: 1,443;
- FRESH_MODEL_REQUIRED: 3,379.

Only FRESH_MODEL_REQUIRED rows enter T1 execution batches.

## Existing primary shard

P3 already froze:

`primary_shard = int(request_id[0:8], 16) mod 16`

T1 preserves that primary shard.

## Transport sub-batch

Within each primary shard:

`sub_batch = int(request_id[8:16], 16) mod 4`

Transport batch:

`transport_batch_id = primary_shard * 4 + sub_batch`

Therefore batch IDs are exactly 0 through 63.

No document text, family, symbol, stage, outcome or model field affects batching.

## Frozen batch sizes

The 64 batch sizes are:

```text
00 41   01 49   02 56   03 37
04 63   05 46   06 64   07 42
08 52   09 53   10 58   11 68
12 44   13 52   14 55   15 47
16 57   17 64   18 59   19 56
20 55   21 52   22 53   23 60
24 61   25 58   26 49   27 61
28 55   29 52   30 45   31 59
32 47   33 59   34 44   35 52
36 52   37 42   38 62   39 54
40 55   41 65   42 46   43 53
44 46   45 52   46 52   47 63
48 42   49 36   50 65   51 43
52 59   53 56   54 53   55 57
56 48   57 55   58 43   59 57
60 56   61 41   62 54   63 47
```

Total: 3,379.

These counts may not change after model output begins.

## Model semantics

Every request retains byte-identical:

- request_id;
- prompt_envelope;
- prompt_sha256;
- document_id;
- event IDs;
- symbol;
- family;
- selected segment IDs/text/hashes;
- segment manifest SHA;
- model configuration.

T1 never edits prompt bytes.

## Response bundle

Each batch produces one bundle:

`HG006-L001-P3-T1-BATCH-<00..63>-v1`

Every frozen request in that batch appears exactly once with:

- MODEL_OUTPUT; or
- MODEL_FAILURE.

MODEL_OUTPUT contains only the pre-provenance substantive HG006-L001 JSON object.

MODEL_FAILURE contains a non-empty error and no model output.

## Validation

Deterministic ingestion must:

- inject frozen GPT-5.6 Sol provenance;
- validate every evidence reference;
- preserve request/document/event/symbol/family identity;
- reject forbidden completion-probability/return/advice fields;
- retain raw model-response SHA;
- retain validated structured-output SHA.

No request-specific prompt repair is allowed inside T1.

## Completion gate

Full P3 ingestion may begin only after all 64 transport batches are present or explicitly
failed as transport observations.

The existing P3 full-run gates remain unchanged:

- >=95% fresh request validation;
- >=95% evidence-ready chronology validation after reuse + fresh responses;
- exact reuse provenance for all 1,443 reuse rows.

## Scientific boundary

T1 does not:

- change model semantics;
- open historical terminal labels;
- estimate completion probabilities;
- use stock returns;
- create expected return;
- create portfolio eligibility;
- authorize live capital.
