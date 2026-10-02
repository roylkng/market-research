# RM001 D015-R1 Nifty Total Market Series Semantics Diagnostic v1

Status: FROZEN BEFORE R1 EVIDENCE ACCESS
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

RM001-D015-v1:
- result SHA-256:
  `dcee31853fcd2f2a61832af19c61722e13ca7f3776c01bee798e859fe71326b9`
- status:
  `FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY`
- exact source raw SHA-256:
  `c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f`
- row count: 755
- EQ row count: 745
- non-EQ row count: 10
- all parent gates passed except frozen minimum EQ-series coverage 99%.

D015 remains failed regardless of R1 outcome.

## Objective

Determine whether the 10 D015 non-EQ rows are explicitly and independently
confirmed by the official NSE Security File as outside the pre-existing AE001
main-board `EQ` universe.

R1 is source-semantics research only.

It opens:
- no returns;
- no alpha outcomes;
- no RM001 factor fit;
- no PO001 result.

R1 does not lower or reinterpret D015's 99% gate.

## Frozen parent bytes

R1 MUST consume the exact D015 raw CSV retained by workflow run:

- run ID: 37036816006
- artifact ID: 11240785634
- artifact name: `rm001-d015-37036816006`
- expected raw SHA-256:
  `c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f`

No current re-download may substitute for the parent bytes.

## Independent official series source

Latest completed NSE CM session before the 2026-10-02 diagnostic:

    2026-10-01

Official NSE CM MII Security File:

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_01102026.csv.gz

Exact response bytes must be retained and SHA-256 hashed.

## Frozen Security File schema

Required fields:

- TckrSymb
- SctySrs
- ISIN
- FinInstrmNm
- DelFlg

R1 parses ALL series. It must not use D007's EQ-only parser for the semantic
comparison.

Identity:

    uppercase(trim(TckrSymb)) + uppercase(trim(ISIN))

No fuzzy company-name matching.

## Frozen correspondence

For every one of the 755 parent rows:

1. find exact Symbol + ISIN in the Security File;
2. require exactly one Security File row for that identity;
3. compare:
   - D015 Series
   - Security File SctySrs
4. exact uppercase series equality is required.

No symbol-only fallback.

## Frozen gates

R1 passes only if ALL are true:

### Parent integrity
- exact D015 raw SHA matches the frozen parent SHA;
- parent row count = 755;
- parent EQ count = 745;
- parent non-EQ count = 10.

### Security source
- Security File is downloadable and parser-valid;
- zero duplicate Security File Symbol+ISIN identities;
- exact parent identity join coverage = 100%.

### Series semantics
- series agreement coverage = 100%;
- all 745 parent EQ rows map to Security File EQ;
- all 10 parent non-EQ rows map to a Security File non-EQ series;
- zero parent EQ -> security non-EQ conflicts;
- zero parent non-EQ -> security EQ conflicts.

### Projected EQ subset
After filtering the parent file with the literal rule:

    Series == "EQ"

the retained set must have:
- exactly 745 rows;
- exactly 745 unique Symbol+ISIN identities;
- zero duplicate identities;
- zero symbol/ISIN conflicts;
- 100% non-empty Industry;
- 100% non-empty ISIN;
- 100% non-empty Symbol and Company Name.

No other filter is authorized.

## Result

Pass status:

    PASS_EQ_PROJECTION_SEMANTICS

A pass authorizes only:

    RM001-SC002_NIFTY_TOTAL_MARKET_EQ_INDUSTRY_PROSPECTIVE_CAPTURE

The future SC002 design must:
- capture the full official source first;
- retain exact full raw bytes;
- record all series;
- derive the RM001 common-equity classification panel only by literal
  `Series == EQ`;
- retain excluded-series diagnostics;
- bind Symbol + ISIN within the same snapshot;
- never backfill current labels into history.

R1 does NOT:
- make D015 pass;
- authorize historical sector backfill;
- add a sector factor to RM001;
- claim non-EQ securities are economically invalid investments;
- change the AE001 universe contract.

## Failure

Failure status:

    FAIL_EQ_PROJECTION_SEMANTICS

Sector/industry prospective capture remains unauthorized from this source.

No gate may be weakened after R1 evidence is opened.

No live-capital implication.
