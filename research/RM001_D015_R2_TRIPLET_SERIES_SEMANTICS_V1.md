# RM001 D015-R2 Symbol+ISIN+Series Correspondence Diagnostic v1

Status: FROZEN BEFORE R2 EVIDENCE ACCESS
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

D015:
- status: FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY
- report SHA-256:
  `dcee31853fcd2f2a61832af19c61722e13ca7f3776c01bee798e859fe71326b9`
- exact constituent raw SHA-256:
  `c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f`
- rows: 755
- EQ rows: 745
- non-EQ rows: 10.

D015-R1:
- status: FAIL_EQ_PROJECTION_SEMANTICS
- report SHA-256:
  `dc34d7ed90decb4c7c89a74b6c32a574ce25813777d7c240aed15cfce7cad6b1`
- exact 2026-10-01 NSE Security File SHA-256:
  `0dab1d451f2ab9015671bba26e1bc441d3d5569528e64150b5700a5772fbd786`
- failure reason:
  Security File contains multiple series rows for one Symbol+ISIN, so the R1
  Symbol+ISIN uniqueness assumption was too coarse.

D015 and R1 remain failed regardless of R2 outcome.

## Objective

Determine whether the exact official constituent row can be independently
corresponded to the exact official Security File row by the finer frozen key:

    Symbol + ISIN + Series

R2 is source-semantics research only.

It opens no:
- stock-return labels;
- alpha outcomes;
- risk-model fit;
- portfolio optimization.

## Frozen evidence

R2 uses only retained source bytes.

### Parent constituent CSV
Workflow run:
- 37036816006
Artifact:
- 11240785634
Expected raw SHA:
- c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f

### Security File
Workflow run:
- 37037983177
Artifact:
- 11240643411
Session:
- 2026-10-01
Expected raw SHA:
- 0dab1d451f2ab9015671bba26e1bc441d3d5569528e64150b5700a5772fbd786

No re-download may substitute for either source.

## Frozen key semantics

Parent key:

    uppercase(trim(Symbol))
    + uppercase(trim(ISIN Code))
    + uppercase(trim(Series))

Security File key:

    uppercase(trim(TckrSymb))
    + uppercase(trim(ISIN))
    + uppercase(trim(SctySrs))

No symbol-only fallback.
No ISIN-only fallback.
No company-name matching.

## Frozen gates

R2 passes only if ALL are true.

### Evidence integrity
- parent constituent raw SHA exact;
- Security File raw SHA exact;
- parent rows exactly 755;
- parent EQ rows exactly 745;
- parent non-EQ rows exactly 10.

### Triplet correspondence
For every parent row:
- exactly one Security File row with identical Symbol+ISIN+Series;
- triplet join coverage = 100%;
- zero ambiguous exact triplet matches;
- zero missing exact triplet matches.

### Parent EQ subset
For all 745 parent EQ rows:
- exact Security File EQ triplet exists;
- no EQ row requires any alternate series;
- Industry non-empty;
- ISIN non-empty;
- Company Name and Symbol non-empty.

### Parent non-EQ subset
For all 10 parent non-EQ rows:
- exact Security File triplet exists;
- matching Security File series equals the parent non-EQ series;
- none require Security File EQ as a fallback.

### Literal projected common-equity subset
Using only:

    Series == "EQ"

the projected set must retain:
- exactly 745 rows;
- exactly 745 unique Symbol+ISIN identities;
- zero duplicate identities;
- zero symbol-to-multiple-ISIN conflicts;
- zero ISIN-to-multiple-symbol conflicts;
- 100% Industry coverage;
- 100% ISIN coverage;
- 100% Company Name and Symbol coverage.

## Result

Pass status:

    PASS_TRIPLET_EQ_PROJECTION_SEMANTICS

A pass authorizes only:

    RM001-SC002_NIFTY_TOTAL_MARKET_EQ_INDUSTRY_PROSPECTIVE_CAPTURE

SC002 must separately freeze:
- capture schedule;
- actual capture timestamp;
- exact raw-byte retention;
- complete full-source snapshot;
- literal Series == EQ projection;
- excluded-series diagnostics;
- append-only classification snapshots;
- same-snapshot Symbol+ISIN identity;
- classification-change detection;
- live RM001-universe overlap diagnostics.

R2 does NOT:
- change D015 or R1 status;
- authorize historical backfill;
- create an RM001 sector factor;
- infer a four-tier taxonomy;
- open returns.

## Failure

Failure status:

    FAIL_TRIPLET_EQ_PROJECTION_SEMANTICS

No threshold or key may be changed after R2 evidence is opened.

No live-capital implication.
