# SS001-D007 R001 Manual Hosted LLM Shard Runbook v1

Status: **EXECUTION PATH PREPARED; NO HOSTED MODEL INFERENCE RUN**
Prepared: 2026-10-09
Portfolio, valuation and share-capital eligibility: disabled

## Purpose

Expose the already-validated R001 append-only LLM transport through an explicitly
triggered GitHub Actions workflow. This is a transport/deployment change, not a
revision to the frozen D007 queue, prompt, source cohort, semantic audit contract or
investment hypotheses.

Workflow:
`.github/workflows/ss001-r001-manual-llm-shard.yml`

The source queue remains exactly:

- source run `37884584355`;
- artifact `11595955883`;
- queue `SS001-D007-L001-P2-v1`;
- queue SHA `59929004bcc5a5eae4491cadc237aa1bb26b822102d56b5b50cf61fb6b667618`;
- 1,240 original page requests in 16 fixed shards.

The earlier GPT-5.6 Sol native P1/P2-P0 pilots are not relabeled as API
inference. An API endpoint/model is a distinct runtime cohort.

## Required repository configuration

In the GitHub repository's **Settings > Secrets and variables > Actions**:

Repository variables:

- `SS001_R001_MODEL_ID`: exact supported model identifier at the designated
  OpenAI-compatible Chat Completions endpoint.
- `SS001_R001_API_ENDPOINT`: a trusted **HTTPS** Chat Completions URL that you
  operate or authorize.
- `SS001_R001_TOKEN_PARAMETER`: `max_completion_tokens` (default when unset)
  or `max_tokens`, depending on that specific provider.

Repository secret:

- `MARKETLAB_LLM_API_KEY`: secret used by the designated provider.

Do not place secrets in repository variables, action inputs, source files,
logs or artifacts.

A hosted GitHub runner cannot contact your own machine's
`127.0.0.1`/localhost LLM server. To use LM Studio or another local
OpenAI-compatible server without a separately authorized HTTPS gateway,
run the existing `scripts/run_ss001_l001_batch.py` locally instead.

A ChatGPT subscription is not an API key. Provider API calls can incur charges.

## Safe manual sequence

1. Open **Actions > SS001 R001 manual evidence-bound LLM shard > Run workflow**.
2. First choose `preflight` (default). This verifies the exact frozen
   source queue and pins the model configuration **without any inference call**.
3. Review the preflight artifact and configuration SHA. The selected model
   must support OpenAI-compatible Chat Completions and JSON object responses.
4. To make paid model calls, explicitly choose `infer`, choose a frozen
   `shard_id` (0 through 15), and set `max_requests` (1 through 78).
   Default is **5** new attempts per run, not the full 1,240.
5. Download the `ss001-r001-<run_id>` output artifact. It contains immutable
   per-request attempts plus the current collection status.
6. For the next run, supply the preceding `previous_run_id` to restore
   the same model cohort's receipts. The next run verifies all restored
   identities and the pinned configuration before making calls.
7. A malformed response is preserved as a failed attempt. Retrying it
   requires manually setting `retry_failed=true`; no automatic retry
   or silent overwrite occurs.
8. The full collection is complete only when all **1,240 exact request IDs**
   have one valid accepted response and none are missing.

Multiple runtime/model configurations must use separate artifact chains.

## Safety and cost controls

- No periodic or push trigger can make model calls.
- Default mode is preflight and executes **zero** model requests.
- A single manual run is bounded at **78** new model calls.
- Hosted workflow requires HTTPS and does not follow provider redirects.
- API credentials are read from GitHub Actions secrets only.
- Results are validated against the frozen SS002-L001 fact contract.
- Every request remains source-hash and segment-ID bound.
- Artifact retention is 30 days; export the evidence chain before expiry.
- Artifacts contain raw model outputs; restrict repository access appropriately.

## Scientific interpretation

Even a fully completed R001 collection is initially only:

`COMPLETE_VALIDATED_PENDING_SEMANTIC_AUDIT`

It cannot certify the accuracy of the extracted legal/economic meaning.
An independent document-level semantic audit and the already-frozen
D007-L002 issuer evidence assembly must happen before any issuer
share-count adjudication.

No market-capitalization value, expected return, stock recommendation, ADO,
PF001 eligibility or live capital is authorized by the transport.
