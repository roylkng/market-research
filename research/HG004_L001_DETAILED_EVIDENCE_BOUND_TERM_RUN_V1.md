# HG004-L001 Detailed Evidence-Bound Transaction-Term Run v1

Status: **FROZEN BEFORE DETAILED MODEL OUTPUT**  
Frozen: 2026-10-05  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Purpose

Run the frozen SS002-L001 evidence-bound extraction contract over every unique document
selected by HG004-D001-P1 for the currently active/procedurally unresolved hidden-gem
special-situation cohort.

HG004-L001 is a detailed transaction-fact extraction run. It does not estimate intrinsic
value, event completion probability, expected return, or portfolio action.

## Frozen selection

Use exactly:

- HG004-D001-P1-v1;
- workflow run: `37283860083`;
- artifact ID: `11333720723`;
- selection SHA-256:
  `9b82b337b02d5aa2c58164bf888f76ce50fcd34680077f87f13b0ff5cfc7c102`;
- 11 symbols;
- 11 semantic clusters;
- 20 event links;
- 19 unique TEXT_READY documents.

No later rerun may be substituted under HG004-L001-v1.

## Model/runtime

- provider/runtime: `CHATGPT_NATIVE_INTERACTIVE`;
- model: `GPT-5.6 Sol`;
- semantic temperature target: 0.0;
- top_p target: 1.0;
- maximum structured-output budget: 8192 tokens per document;
- output contract: `SS002-L001-v1`.

Only the exact frozen HG004 prompt envelopes may be used.

No web search, market price, analyst estimates, future return, company profile, prior
investment conclusion, or unsupported external context may enter extraction.

## Detailed extraction requirement

Every one of the 19 unique documents receives a validated L001 output.

The run may populate all explicit L001 fact families:

- parties;
- security economics;
- consideration;
- ratios / entitlement;
- dates;
- conditions / approvals;
- business economics.

UNKNOWN remains mandatory when a fact is not explicit in the supplied segments.

The model may correct the upstream family/relevance/stage when the document itself
shows different economics, but it may not alter event IDs, symbols, document IDs or
source provenance.

## Conservative arithmetic boundary

The model does not calculate missing terms.

Examples:

- if number of shares and issue price are explicit but total consideration is not, retain
  total consideration as UNKNOWN;
- if promoter holding before/after can be arithmetically inferred but is not explicitly
  stated, retain it as UNKNOWN;
- if an NCLT order implies likely completion but no effective date is explicit, retain
  expected completion date as UNKNOWN.

Downstream deterministic code may later derive arithmetic from explicit facts.

## Full-document manual evidence audit

All 19 documents are manually evidence-audited against their supplied text segments.

For every audited document retain:

- unsupported explicit-fact count;
- material term missed flag;
- unretained material contradiction count;
- audit notes.

## Mechanical gates

HG004-L001 passes only if all are true:

1. exactly 19 model outputs;
2. all 19 outputs pass `validate_extraction`;
3. zero invalid evidence references;
4. zero new event IDs or symbols;
5. zero forbidden investment/advice fields;
6. every output has non-UNKNOWN economic relevance;
7. every output has at least one non-UNKNOWN transaction family;
8. every output has non-UNKNOWN transaction stage unless the document genuinely lacks
   stage evidence and the manual audit explicitly accepts UNKNOWN.

## Manual-audit gates

HG004-L001 passes only if:

1. all 19 documents are audited;
2. zero unsupported material explicit facts;
3. zero unretained material contradictions;
4. no more than two documents have a material explicit term missed by the model.

## Promotion

Passing HG004-L001 permits:

- HG004-L002 deterministic transaction-thread term synthesis;
- family-specific deterministic payoff/scenario models using explicit extracted terms;
- later red-team underwriting.

## Scientific boundary

HG004-L001 does not:

- calculate event spread;
- estimate probability of completion;
- estimate intrinsic value;
- estimate expected return;
- rank the 11 companies;
- create ADO/PF001 eligibility;
- authorize live capital.
