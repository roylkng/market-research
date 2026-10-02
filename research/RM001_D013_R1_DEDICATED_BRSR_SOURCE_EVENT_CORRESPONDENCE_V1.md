# RM001 D013-R1 Dedicated BRSR Source-Event Correspondence Diagnostic v1

Status: FROZEN BEFORE R1 SOURCE DISCOVERY
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

RM001-D013-v1:
- result SHA-256:
  `1132cd63b0a7da1a8eae96acc5e7ef73d3a9ed9a0846be7a36bb713bb676a5f3`
- status: `FAIL_PERIOD_PARTITIONED_ASOF_TIMELINE`
- D014 authorized: false.

D013 remains failed regardless of D013-R1 outcome.

## Why R1 exists

D013 tested the structured BRSR archive's `TLA_SUBMITTED_DT` against NSE's
generic corporate-announcement feed.

That frozen mapping failed:

- FY2023-24 sample match fraction: 27.5%;
- FY2024-25 sample match fraction: 30.0%;
- IST median absolute delta: 1,233 seconds;
- IST p95 absolute delta: 54,809 seconds.

Independent official NSE evidence shows that BRSR has its own dedicated corporate
filings surface:

`https://www.nseindia.com/companies-listing/`
`corporate-filings-bussiness-sustainabilitiy-reports`

NSE's BRSR filing guidance states that BRSR filings are displayed on that
surface.

D013-R1 therefore tests whether the failed parent used the wrong exchange event
surface.

## Objective

Determine, without return labels, whether the dedicated NSE BRSR corporate
filings surface exposes a deterministic machine endpoint and metadata that
corresponds to the frozen BRSR structured archive.

R1 may discover source correspondence only.

It may not:
- alter D013 thresholds;
- open identity/timeline phases;
- alter NIC transformation rules;
- fit RM001;
- open stock returns;
- run PO001.

## Frozen archive/sample

Reuse D013 exactly:

- FY2023-24 archive SHA:
  `f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef`
- FY2024-25 archive SHA:
  `c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42`
- 40 deterministic eligible filings per year;
- identical D013 SHA256 sampling rule.

No sample may be changed based on source-match success.

## Phase A: discover the dedicated BRSR machine surface

Page:

`https://www.nseindia.com/companies-listing/`
`corporate-filings-bussiness-sustainabilitiy-reports`

R1 fetches and retains:
- exact page HTML;
- every first-party JavaScript asset referenced by that page that is successfully
  fetched.

First-party script hosts:
- `nseindia.com`;
- any hostname ending `.nseindia.com`.

### Candidate endpoint extraction

From retained first-party JavaScript, extract every literal path beginning:

`/api/`

For each literal endpoint occurrence retain:
- endpoint path;
- script URL;
- script SHA-256;
- 600-character source neighborhood centered on the occurrence.

BRSR relevance tokens, case-insensitive:

- `brsr`;
- `business responsibility`;
- `sustainability`;
- `sustainabilitiy`.

Candidate endpoints are those whose 600-character neighborhood contains at
least one relevance token.

Candidate order is deterministic:

1. descending count of distinct relevance tokens in the neighborhood;
2. endpoint path ascending;
3. script URL ascending.

If no candidate endpoint is discovered, R1 fails source discovery.

No endpoint may be manually inserted after source discovery begins.

## Phase B: frozen endpoint query variants

For each discovered candidate endpoint and each sampled filing, R1 tries these
parameter variants in this exact order until the endpoint returns a JSON payload
without HTTP/parser failure:

1. `index=equities, symbol, from_date, to_date`
2. `symbol, from_date, to_date`
3. `index=equities, from_date, to_date`
4. `from_date, to_date`

Date window:

- raw TLA calendar date - 1 day;
- through raw TLA calendar date + 1 day.

Date string format:
`DD-MM-YYYY`.

All successful exact response bytes and SHA-256 values are retained.

An endpoint is structurally eligible only if at least one successful response
contains a row object with:

- an exact symbol-like field;
- at least one BRSR/XBRL/filing-specific metadata field.

## Phase C: generic row normalization

R1 recursively discovers row objects from successful JSON payloads.

Normalized key matching is lowercase alphanumeric only.

### Symbol-like fields

Accepted normalized keys:
- `symbol`;
- `symbsymbol`;
- `tckrsymb`;
- `symbolname`.

Exact symbol equality is required.

### APP-ID-like fields

Accepted normalized keys:
- `appid`;
- `applicationid`;
- `applicationno`;
- `applicationnumber`.

### Reporting-period fields

Start keys:
- `currentfinancialyearstartdate`;
- `financialyearstartdate`;
- `periodstartdate`;
- `fromdate`.

End keys:
- `currentfinancialyearenddate`;
- `financialyearenddate`;
- `periodenddate`;
- `todate`;
- `financialyear`.

### Explicit public-time fields

A timestamp may count as public only if its normalized field name contains one
of:

- `broadcast`;
- `dissemination`;
- `received`;
- `exchange` together with `time`;
- `published`.

Generic `date`, `submitted`, `submission` or `tla` fields do NOT count
as public timestamps by themselves.

### Filing-resource fields

Accepted linkage metadata includes fields whose normalized key contains:

- `xbrl`;
- `xml`;
- `filing`;
- `attachment`;
- `document`;
- `file`.

## Phase D: filing-to-row correspondence

For one sampled archive filing, candidate rows must first have exact symbol
match.

Frozen linkage modes, in priority order:

1. `EXACT_APP_ID`
   - row exposes an accepted APP-ID-like field;
   - normalized row APP ID exactly equals archive APP_ID.

2. `RESOURCE_CONTAINS_APP_ID`
   - an accepted filing-resource field contains archive APP_ID as a complete
     alphanumeric token after removing punctuation.

3. `PERIOD_AND_PUBLIC_TIME`
   - row reporting period exactly equals archive reporting period;
   - row exposes an explicit public timestamp;
   - absolute delta from raw TLA interpreted as Asia/Kolkata <= 900 seconds.

No company-name fuzzy matching is allowed.

If more than one row survives at the same highest-priority linkage mode, the
filing is ambiguous and unmatched.

## Phase E: public-time semantics

For every uniquely matched filing with an explicit public timestamp calculate:

- raw TLA interpreted as Asia/Kolkata;
- raw TLA interpreted as UTC;
- dedicated BRSR row public timestamp in UTC.

Reuse D013 timing gates unchanged:

- match fraction >= 90% in EACH required year;
- explicit-public-time coverage among matched filings >= 95%;
- IST median absolute delta <= 60 seconds;
- IST p95 absolute delta <= 300 seconds;
- every matched public-time signed delta is between -60 and +900 seconds;
- UTC median absolute delta >= 14,400 seconds;
- zero row-identity reuse across two sampled filings;
- zero same-priority ambiguous matches.

A match lacking an explicit public-time field can prove filing correspondence
but cannot prove public-time semantics.

## Endpoint selection

R1 evaluates every discovered BRSR-relevant endpoint.

An endpoint passes only if all Phase E gates pass.

R1 succeeds only if EXACTLY ONE endpoint passes.

If:
- zero endpoints pass, R1 fails;
- more than one endpoint passes, R1 fails ambiguous source correspondence.

No "best coverage" endpoint is selected post hoc.

## Success

Status:

`PASS_DEDICATED_BRSR_SOURCE_EVENT_CORRESPONDENCE`

A pass authorizes only:

`RM001-D013-R2_DEDICATED_BRSR_PUBLIC_TIME_REPLICATION`

R2 must independently reproduce the pass on a disjoint deterministic archive
sample before D013 public-time semantics may be reconsidered.

D013 itself remains failed.

The separate D013 multi-NIC transformability failure remains unresolved.

## Failure

Status:

`FAIL_DEDICATED_BRSR_SOURCE_EVENT_CORRESPONDENCE`

Failure preserves D013 unchanged.

R1 must report:
- page/script source hashes;
- all discovered candidate endpoints;
- successful query variants;
- endpoint response hashes;
- per-year linkage counts;
- linkage modes;
- explicit public-time coverage;
- ambiguity/reuse counts;
- timing distributions;
- failure gates.

## Explicit prohibitions

R1 must not:
- guess a hidden API endpoint after seeing R1 results;
- weaken D013 timing gates;
- use current quote-page industry labels;
- use return behavior to choose an endpoint/timestamp;
- treat submission-only timestamps as public dissemination;
- fuzzy-match company names;
- open symbol→ISIN identity Phase B from D013;
- rescue incomplete multi-NIC filings;
- open stock returns;
- fit risk;
- run portfolio optimization.

No live-capital implication.
