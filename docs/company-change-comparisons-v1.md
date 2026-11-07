# CC001 P005: reported-business changes, not a stock-ranking claim

The operational workspace previously displayed individual financial facts, not
what changed in the reported business. This layer adds source-bound comparisons
to the existing daily workflow without training another model or opening outcomes.

## What it computes

A card belongs to one symbol, ISIN and accounting scope. It selects an exact
three-calendar-month period from that scope's latest reporting end date. It never
relabels a half-year or full-year as a quarter or annualizes interim figures.

For the previous quarter, it prefers an exact comparative period in the same
original disclosure. When the disclosure contains only the current quarter and
its exact enclosing half-year, it derives the prior quarter's additive flows:

    previous-quarter revenue = half-year revenue - current-quarter revenue

The same operation is permitted for disclosed PBT, other income, taxes, total
profit and explicitly attributed profit. Each derived value retains the input
values, formula, original file hash, extraction IDs, periods and observation
clocks. Missing inputs remain missing. Derived numbers inherit source rounding
and are not presented as independently reported or independently validated.

EPS, share counts, paid-up capital and balance-sheet stocks are NEVER subtracted.
No owner-PAT substitution, after-tax exceptional adjustment or sustainable EPS
estimate is introduced. Direct quarterly amounts that do not sum to an available
half-year are shown with a reconciliation warning, not silently repaired.

Prior-year comparisons require the exact year-ago quarter in the same retained
disclosure. When it is absent, the card states that seasonality is unresolved.
The first operational XML sample contains current quarters and half-years but
no year-ago income-statement context. No fabricated year-over-year result fills
that gap. Historical backfill is still needed for those comparisons.

Growth percentages require a strictly positive base. A negative-to-positive
PBT change is described as a reported turnaround, not a misleading growth
percentage. Negative derived revenue requires accounting review. Monetary units,
issuer identities, scope, document identity and observation clocks must agree.

## What a review cue means

Fixed, unvalidated attention thresholds are 10% sequential revenue change and
2 percentage points of reported PBT-margin change. They are transparent defaults,
not optimized stock-selection factors. Cards are alphabetical, not ranked by
expected return, success probability or quality. Both accounting scopes remain
visible rather than being mixed into one synthetic company history.

Each card separates reported improvement/deterioration, mixed changes, accounting
review, missing comparisons and no threshold crossed. Source rejection or an
attribution/reconciliation warning takes precedence over an improvement label.
Other income at least equal to PBT and nonzero pretax exceptional items generate
additional caveats. Other income is not automatically non-recurring or deducted
as though it were an after-tax owner adjustment.

All source reviews remain unchanged. Unreviewed evidence is clearly identified.
No buy recommendation, current-price claim, cash-conversion assessment, diluted
share reconciliation, portfolio execution or predictive edge follows from a card.
A seasonally stronger quarter is not by itself evidence of a lasting inflection.

## Operation

```bash
python -m marketlab.company_change_comparisons \
  --workspace .marketlab/cc001 \
  --output-prefix .marketlab/cc001-exports/business-changes
```

The explicit output prefix writes latest-view JSON and HTML exports. These
exports may be replaced when regenerated. Underlying source records are not
modified, and the JSON includes its own content hash and input snapshot hash.

The existing daily operations workflow now generates `business-changes.json`
and `business-changes.html` alongside the research desk. They are preserved in
the dedicated `cc001-state` branch and in the daily artifact. Its cadence,
40-document acquisition cap and original-data checkpoint format are unchanged.
The existing pipeline still surfaces network/parse failures after saving useful
work. A source failure is not hidden to make a workflow green. If a comparison
fails, the original-data checkpoint is still persisted before the run reports a
failure. The latest-state metadata marks the comparison FAILED and clears its
current counts and hash. An older dated comparison export is not a fresh result.

## Verification boundaries

Unit/regression tests cover same-source arithmetic, direct comparisons, exact
periods, issuer/scope isolation, missing and nonfinite values, nonpositive bases,
future observations, negative derived revenue, conflicting direct/cumulative
periods, rejected evidence, deterministic output, HTML escaping and workflow
export paths. The resumed real workspace was replayed separately.

The analysis is a seen-development accounting calculation, not independently
labelled extraction accuracy or prospective investment performance. No model
endpoint, paid service, new schedule, trade action or frozen experiment was
introduced. Existing H-series, HG009 and AE001 remain untouched.
