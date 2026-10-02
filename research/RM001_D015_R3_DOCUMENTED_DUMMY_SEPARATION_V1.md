# RM001 D015-R3 Documented Index-Dummy Separation v1

Status: FROZEN BEFORE R3 EVIDENCE ACCESS
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

D015:
- status: FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY
- exact Nifty Total Market constituent raw SHA-256:
  `c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f`

D015-R1:
- status: FAIL_EQ_PROJECTION_SEMANTICS
- exact 2026-10-01 NSE Security File SHA-256:
  `0dab1d451f2ab9015671bba26e1bc441d3d5569528e64150b5700a5772fbd786`

D015-R2:
- status: FAIL_TRIPLET_EQ_PROJECTION_SEMANTICS
- report SHA-256:
  `71cf04c4ed5c61248a7581bb5c000141150af7ef361dc0493e1510205c3b865b`
- observed 5 missing EQ triplets, all explicit `DUMMY...` identities.

All parent failures remain failures regardless of R3 outcome.

## Independent semantic basis

Nifty Indices' March 2026 equity-index methodology documents dummy symbols as
temporary synthetic index constituents used around demergers. Their prices are
derived/static for index calculation until the spun-off entity becomes listed.

R3 therefore asks a new source-semantics question:

> Can actual tradable EQ constituents be separated from documented index-only
> dummy placeholders using exact same-snapshot Security File correspondence?

R3 does not reinterpret an unmatched ordinary equity as a dummy.

## Frozen evidence

R3 uses only retained parent bytes.

### Parent constituent CSV

Workflow run: 37036816006
Artifact: 11240785634
Expected raw SHA:
`c469467c0e042e71ce566e8f5df1b9e0c081603ee48919db40d56c4beb44034f`

### NSE Security File

Workflow run: 37037983177
Artifact: 11240643411
Session: 2026-10-01
Expected raw SHA:
`0dab1d451f2ab9015671bba26e1bc441d3d5569528e64150b5700a5772fbd786`

No fresh market query may substitute for either source.

## Frozen classification rule

For each parent constituent row:

### Tradable exact-security row

A parent row is security-corresponded only if exactly one Security File row
matches:

    uppercase(trim(Symbol))
    + uppercase(trim(ISIN Code))
    + uppercase(trim(Series))

No fallback is allowed.

### Index-only dummy placeholder

A parent row may be classified as an index-only dummy only if ALL are true:

1. parent Series is exactly `EQ`;
2. parent Symbol starts exactly with `DUMMY`;
3. exact Symbol+ISIN+Series Security File match count is zero;
4. Security File contains zero rows for the same Symbol+ISIN under any series.

No company-name inference.
No ISIN-only inference.
No prefix other than literal `DUMMY`.
No ordinary unmatched EQ row may be excluded.

## Frozen R3 gates

R3 passes only if ALL are true.

### Evidence integrity

- exact parent raw SHA;
- exact Security File raw SHA;
- parent rows exactly 755;
- parent EQ rows exactly 745;
- parent non-EQ rows exactly 10.

### Ordinary EQ correspondence

- exactly 740 non-dummy EQ rows;
- 740/740 have exactly one exact Security File triplet;
- zero ordinary non-dummy EQ missing;
- zero ordinary non-dummy EQ ambiguity.

### Dummy-placeholder semantics

- exactly five parent EQ rows are literal `DUMMY...`;
- all five have zero exact Security File triplet;
- all five have zero same-Symbol+ISIN Security File rows under any series;
- no matched security row is classified as a dummy;
- the five identities equal the five R2 missing identities.

### Non-EQ correspondence

- all 10/10 parent non-EQ rows have exactly one exact Security File triplet.

### Projected tradable EQ subset

Projection rule:

    Series == "EQ"
    AND NOT Symbol startswith "DUMMY"
    AND exact same-snapshot Security File triplet exists uniquely

Required:
- row count exactly 740;
- unique Symbol+ISIN count exactly 740;
- zero duplicate identities;
- zero Symbol -> multiple ISIN conflicts;
- zero ISIN -> multiple Symbol conflicts;
- 100% Industry coverage;
- 100% ISIN coverage;
- complete Company Name and Symbol text.

## Pass status

`PASS_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS`

A pass authorizes only a separately frozen:

`RM001-SC002_NIFTY_TOTAL_MARKET_INDUSTRY_PROSPECTIVE_CAPTURE`

The future capture must retain the full raw constituent file and full raw
Security File, and must apply the following variable-count rule prospectively:

- every non-dummy EQ row must exact-match one Security File triplet;
- every unmatched EQ row must be literal `DUMMY...` and absent from the
  Security File by Symbol+ISIN across all series;
- any ordinary non-dummy missing/ambiguous row makes that capture ineligible.

The future dummy count is NOT frozen to five.

## R3 does not authorize

- historical industry backfill;
- retroactive sector factors;
- return labels;
- risk-model fitting;
- portfolio optimization;
- live capital.

## Failure

`FAIL_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS`

No gate may be changed after R3 evidence is opened.
