# SS001-D007-L001-R001 Frozen-Queue Preflight — 2026-10-09

Status: **PASSED; NO MODEL INFERENCE EXECUTED**

## Exact evidence

- source queue: `SS001-D007-L001-P2-v1`;
- source run: `37884584355`, artifact `11595955883`;
- source queue SHA: `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`;
- preflight workflow run: `37896262528`;
- preflight artifact: `11600297929`;
- preflight SHA: `5a9369e78e410eeb0a8fc52665febc4340abd2c7da1629a53e8f90d0c6123a23`;
- preflight runtime: `PREFLIGHT_ONLY_NO_INFERENCE`;
- source-model and API model equivalence claimed: **no**.

## Result

The real artifact passed exact queue, page, prompt, request, shard and source-outcome
validation:

- 1,240 exact frozen requests;
- 12 issuers;
- 16 frozen shards;
- shards 0–7: 78 requests each;
- shards 8–15: 77 requests each;
- zero inference calls;
- zero share-count clearance, capitalization or return outcomes.

Normal repository CI and the source-only preflight workflow both passed.

## Wire-serialization compatibility

The P2 producer hashed `shard_request_counts` while its keys were integer
`0..15`. Persisted JSON necessarily converts object keys to strings. Reloading
and hashing the naive JSON representation changes lexical key sort order and
therefore does not reproduce the original canonical SHA.

R001 restores **only** `shard_request_counts` key types to integer in an in-memory
copy used for SHA verification. It also verifies all 16 stored shard totals against
the actual 1,240 requests. The original P2 artifact and frozen SHA are unchanged.

## Remaining execution boundary

The transport is now suitable for an explicitly configured
OpenAI-compatible Chat Completions endpoint. Running the full queue requires a
model endpoint/credentials and creates a **new runtime cohort**. An API model is not
silently substituted for the passed GPT-5.6 Sol native pilot.

Even after 1,240 schema-valid responses, issuer chronology must undergo semantic
auditing. No stock selection or live-capital decision is authorized by this result.


## Provider-free real-artifact revalidation (2026-10-09)

The new default manual preflight path was independently exercised on the **actual**
frozen source artifact, with no provider variables or API secret.

- execution run: `37916267130`;
- successful artifact ID: `11609788569`;
- output: `source-preflight.json`;
- source-preflight SHA-256:
  `ce2d7c89e4d5dcb73639bda6afa8d0d4bcd188e16f579134bc1385703d656bdd`;
- source queue SHA-256 unchanged:
  `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`;
- 1,240 / 1,240 source request identities validated across 16 frozen shards;
- `model_configured=false`;
- `model_inference_executed=false`;
- `share_action_clearance_proven=false`;
- `market_capitalization_calculated=false`;
- `portfolio_eligibility_allowed=false`;
- `live_capital_allowed=false`.

This verifies the deployed source-only transport. It does **not** execute any
inference or replace the independent semantic audit required after inference.
