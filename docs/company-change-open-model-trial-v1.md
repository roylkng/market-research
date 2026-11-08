# CC001 P011: actual open-model inference measurement

The next acceptance question is whether the semantic worker works with a real
model, rather than only a controlled test transport. This change runs one pinned
small open model on CPU in a disposable, loopback-only research workspace.

## Locked resources

- Official Qwen/Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M.
- Model revision 91cad51170dc346986eccefdc2dd33a9da36ead9.
- Original weights SHA-256 6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e.
- Original bytes: 1,117,320,736.
- llama.cpp source revision 053b1539c02617eff744f89525ee57497c3c1fbe.
- Four CPU threads, one inference slot, 16,384-token context, 1,536-token output
  request cap, greedy decoding through the existing semantic worker.

This is a deliberately small, reproducible engineering baseline, not a claim
that this is the newest or best investment-analysis model. It uses no paid model
API, API key, hosted provider account, private source document or broker. The
public GitHub Actions job uses the repository's existing CI compute. Its lifetime
is bounded to 30 minutes. The local server is terminated at the end of the job.
Model weights and runtime binaries are excluded from the delivery artifact.

The runtime source is a fixed historical revision selected for this bounded
loopback experiment, not a supported public-serving security baseline. The model
publisher labels its official repository Apache-2.0. That licence does not confer
commercial redistribution rights over issuer filings or market data.

## Input, generation and scoring

The trial uses the four already inspected SEAMEC, Dhruv, Vikran and Prestige
source documents. They are seen development cases, not independently labelled or
representative holdout cases. Their source URL, symbol, ISIN, original-byte hash
and extracted-text hash must match. Missing sources remain in the denominator.

A sealed plan records the cases, worker code hash, model/runtime pins and runtime
receipt BEFORE model execution. The runner passes only source identity and full
original text to the existing semantic worker. Expected category/stage/actor
labels and assisted interpretations are not inserted into model requests.

The exact P010 source-quotation and schema validation remains unchanged. There is
no retry with a more convenient prompt, no quotation cleanup, and no automatic
review approval. Every raw completion, failure reason and measured latency is
retained. Predictions are sealed before the separate scoring phase loads labels.
The before/after counts of accepted reviews and financial decision tables must
match. No production research branch is written by this workflow.

Three questions are reported separately:

1. Did the real model generate a response for every planned case?
2. How many outputs passed the unchanged source and schema checks?
3. How many emitted category/stage/actor triples match the development labels?

A job can successfully COMPLETE A MEASUREMENT even when every model output fails
quality checks. Its score must say so. Workflow success never sets a production
approval flag. Missing, failed and abstaining cases remain in scoring. All model
outputs remain proposals and live capital stays disabled.

## Running and reproducing

The read-only `CC001 actual local model measurement` workflow is manual or triggered
by changes to its four implementation inputs. It builds the pinned runtime,
verifies the exact official weights, restores a copy of cc001-state, retrieves
the four original development documents, starts the server on 127.0.0.1, then runs:

    python -m marketlab.company_change_model_trial run ...
    python -m marketlab.company_change_model_trial score ...

The workflow supplies all paths and local endpoint configuration. The score and
its original evidence are in the artifact `cc001-actual-local-model-evidence`.
The plan, runtime receipt and predictions are immutable within a run directory.
A second run needs a separate output directory. The existing semantic worker
reuses identical requests in the same evidence workspace, including failed ones.

No recurring job is added. Existing daily operations and frozen H-series/HG009/
AE001 experiments, cohorts, outcomes and financial trading gates are unchanged.

## Acceptance boundaries

An actual runtime result can close the previous no-live-inference gap. It cannot
establish independent semantic quality, normalized issuer earnings, forecast
outperformance, production serving readiness or commercial permissions. Release
status remains HOLD until separately designed quality and operating gates pass.
The narrow category/stage/actor score also does not measure the correctness of
narrative interpretation, amount attribution or omitted events.

Primary configuration sources:
- https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF
- https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/raw/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf
- https://github.com/ggml-org/llama.cpp/tree/053b1539c02617eff744f89525ee57497c3c1fbe
