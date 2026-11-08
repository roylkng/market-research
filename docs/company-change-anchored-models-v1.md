# CC001 P012: source-selection protocol and paired model measurement

## Why the design changed

The two P011 measurements are retained as failures. The first real 1.5B model
run abstained on every positive development case. Adding the output schema to
the model-visible prompt produced event attempts but no usable records: three
failed exact quotation checks and one was truncated. Several raw interpretations
were also wrong. JSON generation and factual reliability are different gates.

Asking a language model to reproduce PDF whitespace is unnecessary. This lane
provides a complete numbered catalog of original text blocks and asks the model
to select evidence locations. The client constructs quotations and offsets from
the original text. No fuzzy matching, whitespace repair or manufactured quote is
used. It does not weaken the existing quote-copy worker or rewrite its results.

## Implemented contract

The catalog contains the whole extracted source, in order, with contiguous exact
character ranges. Blocks are bounded to 600 characters and normally split at a
newline or space. No source sentence or counterevidence is removed. Each block
has a content hash and the catalog binds symbol, ISIN, URL and original/text hashes.
The catalog is reconstructed before accepting a response, not trusted from a caller.

The output is bounded to two proposed events. Each requires category, stage,
economic actor, references supporting the event/stage/actor, counterevidence,
a concise interpretation and a next-check statement. The client rejects unknown
or repeated IDs, missing required evidence, changed catalogs, unsupported fields,
truncation, refusals and tools. Returned quotations use exact original offsets.
The existing assisted-review validator is reused for validation only, not approval.

A real source ID does NOT prove that a claim follows from the passage. Wrong
classification, ignored negation, incorrect actor scope and missing contradictions
can still survive structural validation. Model outputs remain unapproved proposals.
No model output updates accounting facts, investment recommendations or live capital.

## Controlled comparison

The new isolated workflow compares official Qwen2.5-Instruct Q4_K_M weights at
1.5B and 7B sizes, using the same four previously inspected original disclosures,
the same numbered-source protocol, prompt, labels, CPU runtime and output budget.
All model shards use immutable publisher revisions and SHA-256 pins. The 7B
model's two original GGUF shards are separately verified and loaded together.

Both arms use four CPU threads, one slot, a 16,384-token context and a maximum
1,024-token output. No GPU or provider API is provisioned. Each job is limited to
30 minutes and each source request has a 240-second transport timeout. Requests
are reserved durably before execution. A repeated identical request is not retried,
including failed or interrupted requests. No repair prompt is issued.

Plans include model/runtime and code hashes and seal before inference. Only source
identity and the full block catalog enter the model prompt. Expected labels are
loaded during the separate scoring step after predictions seal. Both arms retain
the same four-case denominator. Missing, failed and abstaining cases count.

The scoring reports actual generation, source-location validation and exact
category/stage/actor agreement separately. A completed CI experiment is not a
model-quality pass. Even perfect agreement on these four seen development cases
cannot approve a production model or prove generalization. Human/source auditing
of selected passages and the actual narrative remains necessary.

## Operation and isolation

`CC001 anchored evidence model comparison` runs as a read-only two-job matrix on
manual dispatch or changes to its implementation inputs. It restores an isolated
copy of saved state and replays the four declared source documents. It never
pushes cc001-state, changes daily acquisition budgets or adds a recurring job.
Model binaries and weights are excluded from artifacts. The model server binds
only 127.0.0.1 and terminates at job exit. No provider credential is accepted.

Local module entry points are:

    python -m marketlab.company_change_anchor_trial run --help
    python -m marketlab.company_change_anchor_trial score --help

The workflow provides exact paths and verified runtime inputs. Artifacts contain
source bytes, requests, raw responses, block catalogs, hashes, latency, generation
counts, classifications, code and tests. Original P011 artifacts remain unchanged.
This is an experiment in extraction reliability, not a new return-prediction
experiment, normalized valuation model or trade approval.

## Resource and commercial limits

The pinned historical llama.cpp runtime is for this disposable loopback trial,
not a current security baseline for public hosting. Official model licence terms
do not grant redistribution rights for issuer filings or market data. Independent
labels, a larger representative evaluation, normalized owner earnings, forward
performance, scalable storage and approved commercial operations remain distinct
acceptance requirements.

Primary model pins were read from the official Qwen repositories:
https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF
Runtime schema constraints are documented at:
https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
