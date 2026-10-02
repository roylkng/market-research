# RM001 D015 Nifty Total Market Prospective Industry Source Feasibility v1

Status: FROZEN BEFORE SOURCE SCAN
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether the official NSE Indices Nifty Total Market constituent CSV is
a stable, machine-readable, broad company-level classification source suitable
for STARTING a prospective point-in-time industry history.

D015 is source-feasibility research only.

It opens:
- no stock-return labels;
- no alpha outcomes;
- no RM001 factor-return fit;
- no PO001 optimization.

It does NOT authorize historical backfill.

## Why this source

Prior source paths remain failed and unchanged:

- D008 monthly-report classification source: failed broad historical mapping.
- D009 NSE quote industryInfo: automated GitHub acquisition failed with HTTP 403.
- D013/D013-R1 BRSR/NIC public-time correspondence: failed frozen source-time
  correspondence gates and is explicitly stopped.

D015 tests a different official source family.

## Official source

NSE Indices current Nifty Total Market constituent file:

    https://nsearchives.nseindia.com/content/indices/
    ind_niftytotalmarket_list.csv

The public Nifty Total Market page identifies the index as roughly 750 stocks
and exposes an "Index Constituent" download. The page also presents sectoral
distribution and states that displayed sector data are as of the last trading
day of the previous month.

D015 does not infer a historical effective date from that page statement.
The authoritative point-in-time observation for future use is the ACTUAL
capture timestamp of the CSV.

Exact response bytes must be retained and SHA-256 hashed.

## Frozen schema

Required CSV columns after trimming surrounding whitespace:

- Company Name
- Industry
- Symbol
- Series
- ISIN Code

No alternate column may be substituted after source access.

No free-text inference is permitted.

The source's `Industry` value is retained exactly as a categorical NSE Indices
classification label.

D015 does NOT claim that this one column equals the full NSE Indices four-tier
taxonomy.

## Identity rules

For every non-empty row:

- Symbol normalized by trim + uppercase only.
- Series normalized by trim + uppercase only.
- ISIN normalized by trim + uppercase only.
- Industry normalized only by surrounding whitespace trim.
- Company Name normalized only by surrounding whitespace trim.

No fuzzy company-name matching.

Frozen identity:

    Symbol + ISIN

## Frozen promotion gates

The source passes only if ALL are true:

1. HTTP acquisition succeeds and bytes are non-empty.
2. CSV parser sees every required frozen column.
3. total parsed row count >= 700.
4. unique Symbol + ISIN identity count >= 700.
5. duplicate Symbol + ISIN row count = 0.
6. symbol -> multiple ISIN conflict count = 0.
7. ISIN -> multiple symbol conflict count = 0.
8. non-empty Industry coverage >= 99.0%.
9. non-empty ISIN coverage = 100%.
10. EQ-series coverage >= 99.0%.
11. distinct non-empty Industry label count is between 10 and 40 inclusive.
12. every retained row has non-empty Company Name and Symbol.
13. exact raw bytes are retained.

These gates are source-integrity gates only. They are not tuned to return
behavior.

## Promotion meaning

Pass status:

    PASS_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY

A pass authorizes ONLY:

    RM001-SC002_NIFTY_TOTAL_MARKET_INDUSTRY_PROSPECTIVE_CAPTURE

SC002 must separately freeze:

- capture cadence;
- actual capture timestamp semantics;
- append-only content-addressed snapshots;
- same-snapshot Symbol + ISIN identity;
- classification-change handling;
- stale/missing snapshot behavior;
- overlap diagnostics versus the live RM001 universe.

Historical backfill remains prohibited.

A future RM001 categorical industry factor requires a separately frozen
risk-model challenger after sufficient prospective snapshots exist.

## Failure

Failure status:

    FAIL_PROSPECTIVE_INDUSTRY_SOURCE_FEASIBILITY

Failure keeps RM001 sector/industry semantics deferred.

Do not rescue D015 after source inspection by:
- lowering row-count gates;
- accepting non-ISIN fuzzy joins;
- using third-party mirrors as canonical source;
- treating current labels as historical truth;
- mapping unclassified securities with an LLM;
- combining BSE/NSE taxonomies post hoc.

## Interpretation

A successful D015 would solve only one problem:

    a clean prospective classification source from now onward.

It would NOT solve historical point-in-time sector attribution.

No live-capital implication.
