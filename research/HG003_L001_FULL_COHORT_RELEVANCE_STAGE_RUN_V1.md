# HG003-L001 Full-Cohort Evidence-Bound Relevance and Stage Run v1

Status: **FROZEN BEFORE CHECKED-IN COHORT MODEL OUTPUT**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Run the already-validated SS002-L001 evidence-bound document-understanding contract
across every TEXT_READY special-situation thread in the fixed 28-name HG002 hidden-gem
underwriting cohort.

HG003-L001 is a transaction-relevance and stage gate. It is not an expected-return
model and does not rank the 28 companies.

## Frozen source

Use exactly:

- HG003-D001-v1;
- workflow run: `37267831741`;
- artifact ID: `11327057449`;
- artifact name: `hg003-d001-37267831741`;
- selection SHA-256:
  `ebc543464475ff9e409b1795c02272a818a3062cef8ad2bafcfafb5fcc30b536`;

containing:

- 28 HG002 symbols;
- 35 symbol×event-family threads;
- 34 TEXT_READY evidence-bound prompt envelopes;
- exactly one TEXT_UNAVAILABLE thread:
  `HINDCOPPER::OFFER_FOR_SALE`.

No later HG003 selection may be substituted under this run.

## Model / contract

Use exactly:

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- semantic temperature target: 0.0;
- semantic top_p target: 1.0;
- SS002-L001-v1 output contract;
- deterministic validator:
  `marketlab.ss002_llm_contract.validate_extraction`.

The model may use only the exact prompt envelope and supplied document segments.

## Frozen scope

Every one of the 34 TEXT_READY HG003 threads receives one validated L001 extraction.

For this first cohort-wide gate, materialize only:

- economic_relevance;
- corrected transaction_families;
- transaction_stage;
- unresolved_questions;
- contradictions_within_document;
- extraction_caveats.

All detailed L001 fact fields remain `UNKNOWN` in this run.

This prevents the first cohort-wide pass from mixing classification/stage validation
with downstream transaction-term valuation.

## Economic interpretation requirement

The model must classify the economics represented by the selected document, not merely
repeat the upstream keyword family.

Examples that must be distinguishable:

- a genuine CIRP acquisition versus an NCLT amalgamation filing containing insolvency
  terminology;
- a listed company issuing rights to its own holders versus a listed parent subscribing
  to a subsidiary's rights issue;
- a direct listed-security OFS versus disposal of an investment in another company;
- a current offer versus a historical call-money/conversion/procedural update;
- a direct listed-company reorganisation versus a subsidiary-only internal scheme.

## Mechanical gates

Promotion requires:

1. exactly 34 model outputs;
2. 100% pass the frozen L001 deterministic validator;
3. zero invalid evidence references;
4. zero invented event IDs or symbols;
5. zero forbidden return/valuation/advice fields;
6. 100% non-UNKNOWN economic relevance;
7. 100% at least one non-UNKNOWN transaction family;
8. at least 90% non-UNKNOWN transaction stage;
9. HINDCOPPER remains outside the model run as TEXT_UNAVAILABLE and is not imputed.

No failed thread may be reprompted with thread-specific special instructions inside v1.

## Frozen manual-audit sample

Audit the lexicographically first two TEXT_READY thread IDs from each of these six
upstream families:

- BUYBACK;
- TENDER_OFFER;
- SCHEME_REORGANISATION;
- PREFERENTIAL_WARRANT;
- INSOLVENCY_RESOLUTION;
- RIGHTS_ISSUE.

Expected audited documents: **12**.

The only HG002 OFS thread is HINDCOPPER::OFFER_FOR_SALE and is TEXT_UNAVAILABLE, so it
is not part of the L001 audit. Its image-document path remains separately pending.

For each audited output verify against the exact cited document segments:

- economic relevance;
- corrected family/families;
- transaction stage;
- every material caveat/ambiguity needed to avoid a misleading interpretation.

Audit states:

- SUPPORTED;
- UNSUPPORTED;
- MATERIAL_CLASSIFICATION_MISSED;
- AMBIGUITY_NOT_RETAINED.

Promotion requires:

- zero UNSUPPORTED;
- zero AMBIGUITY_NOT_RETAINED;
- no more than 2 of 12 with MATERIAL_CLASSIFICATION_MISSED.

## Promotion

Passing HG003-L001 permits:

- L002 company/event-thread synthesis across all HG002 special-situation evidence;
- deterministic identification of which events directly affect the listed security;
- detailed L001 term extraction only for economically relevant active threads;
- family-specific scenario/payoff models after required explicit terms are available.

## Scientific boundary

HG003-L001 does not:

- estimate intrinsic value;
- estimate probability of completion;
- calculate expected return;
- use market price;
- use future stock returns;
- rank the 28 companies;
- drop companies based on model preference;
- create ADO/PF001/live-capital eligibility.
