# CC001 P013: critical-source qualification diagnostic

## Why classification agreement is not the investment acceptance test

The completed P012 pair produced four model responses in each arm. The 1.5B
model yielded three structurally valid documents and zero of four fixed event
classification matches. The 7B yielded four structurally valid documents and two
matches. Its selected citations still omitted key qualifications, and even
selected source text was sometimes misinterpreted.

The old classification labels and scores are unchanged. A further issue is that
one actor_scope field conflates the consortium receiving an award with whose
portion of the contract an amount describes. Signing an agreement, completing a
transaction, paying consideration and commencing operations are also different
facts. They should not be reduced to one optimistic event-stage label.

## Implemented diagnostic

This read-only module checks an explicitly source-bound set of required passages
against the ranges cited in sealed model predictions. It verifies original file,
reading, text and prediction hashes, security identity, observation cutoff, and
all exact quote offsets. A requirement with two conflicting source statements is
covered only when BOTH are contained in the selected evidence. Adjacent selected
blocks may jointly cover a statement, but missing characters are not bridged.

The output retains four separate concepts:

1. Whether original source evidence is available and intact.
2. Whether the model cited the required source passages.
3. Whether its interpretation follows from those passages, NOT EVALUATED here.
4. Whether an investment has been approved, always false here.

A model can cite the entire document and still give a false interpretation. The
regression suite explicitly tests that case. Complete passage coverage never
changes the output from HOLD_INTERPRETATION_REVIEW_REQUIRED.

The score is not a new model-accuracy percentage, an entailment evaluator or a
return-prediction result. This diagnostic cannot discover all missing caveats
without a source checklist. Its checklist is not automatically authoritative.

## Annotation provenance and replay

The included four-case checklist contains twelve evidence groups, three per
issuer. It was selected AFTER the paired model outputs were inspected. It is
labelled RETROSPECTIVE_SEEN_DEVELOPMENT_DIAGNOSTIC, with independent_labels=false
and requirements_selected_after_predictions=true. It must never be represented
as a new blind holdout or a prompt-improvement success. No inference is rerun.

The source quotations reuse the exact inspected development filings:

- SEAMEC: issuer-specific amount ownership, unconfirmed commencement, and the
  stated completion deadline.
- Dhruv: operations not yet started, conflicting capital-payment statements,
  and the previously disclosed underlying project award.
- Vikran: grade versus outlook, funding/working-capital pressure, and expected
  rather than realized liquidity improvement.
- Prestige: agreement already signed, conflicting completion statements, and
  consideration payable in tranches.

Replay of the sealed final P012 responses found 4/12 required evidence groups
selected by the 1.5B model and 6/12 by the 7B model. Both selected all three groups
for SEAMEC, yet the larger model's narrative still blurred ownership of the
quoted value. This illustrates why coverage is necessary for review but cannot
substitute for correct interpretation. The counts are development diagnostics,
not estimates of generalization.

## Operation

Use a closed, checkpointed copy of the evidence workspace. The diagnostic refuses
nonempty WAL or rollback-journal files rather than silently ignoring committed
changes. It opens SQLite with immutable read-only semantics and checks for
snapshot changes before returning. It does not create review rows or a new
financial extraction. No provider call, external network request or new schedule
is involved. It creates only the requested HTML and JSON output files.

```bash
python -m marketlab.company_change_qualifications \
  --workspace .marketlab/cc001-checkpoint-copy \
  --predictions .marketlab/model-trial/predictions.json \
  --requirements data/fixtures/company_change_critical_qualifications.json \
  --output-prefix .marketlab/exports/critical-qualifications
```

All planned source cases remain in the denominator. Missing predictions,
abstentions and failures get no evidence-coverage credit. Missing originals are
visible. Modified evidence, duplicates, unknown prediction sources or an attempt
to call these retrospective annotations independent fails validation.

## Strategic consequence

Neither tested model is released for autonomous investment analysis. The next
representation should separate legal actor, amount ownership, signing, completion,
payment, operations, prior baseline inclusion and contradictions. Those fields
then need independently reviewed representative labels, including negative cases,
before calibration or deployment. Existing production acquisition, manual
research reviews and frozen H/HG/AE experiments are unchanged.

This module deliberately does not add another model experiment, another provider
or a trade rule. It makes the remaining failure visible and reproducible.

## Verification and references

Twenty-five new regression cases cover exact range unions, both sides of a
contradiction, source integrity, clock/identity checks, missing cases, immutable
snapshot access, provenance, safe rendering and the fact that complete citations
do not approve false interpretations. Local replay uses the original P012
artifacts, not newly generated outputs.

Relevant primary references, not claimed as reproduced evaluations:
- Gao et al., 2023, ALCE separates correctness and citation quality:
  https://aclanthology.org/2023.emnlp-main.398/
- SQLite URI options and immutable-read assumptions:
  https://www.sqlite.org/uri.html
