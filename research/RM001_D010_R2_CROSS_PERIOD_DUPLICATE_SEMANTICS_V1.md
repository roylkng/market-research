# RM001 D010-R2 Cross-Period Duplicate Semantics v1

Status: FROZEN BEFORE CONFLICTING-GROUP ROW INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

Parent diagnostic:

- RM001-D010-R1-v1
- workflow run: 37011294647
- result SHA-256:
  eedc9bba0dfcb15a394af800cdc84f2e20ab48b95632d8941e5af169e1291522
- status: FAIL_DUPLICATE_SEMANTICS

R1 established:

- FY2023-24: 27/27 duplicate groups are deterministic amendment chains;
- FY2024-25: 3/4 duplicate groups are deterministic amendment chains;
- exactly one FY2024-25 duplicate group fails only because its filing rows carry
  inconsistent current-financial-year start/end values;
- all duplicate filings have parseable submission timestamps;
- all duplicate filings have explicit NIC rows;
- zero timestamp collisions;
- zero APP_ID-to-multiple-identity conflicts.

R2 does not weaken or reinterpret any R1 gate.

## Objective

Determine whether the sole FY2024-25 reporting-period-conflict group is not a
same-period duplicate at all, but a valid sequence of filings for distinct annual
reporting periods belonging to the same stable company identity.

The candidate identity is not named or inspected before this protocol is frozen.

## Exact source

R2 uses only the exact FY2024-25 archive already frozen by D010/R1:

https://nsearchives.nseindia.com/web/mediaattachment/2026-04/BRSR_DUMP_FY24-25_20260414130852.zip

SHA-256:

c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42

No alternate or revised archive may substitute.

## Candidate selection

R2 first reproduces the exact R1 FY2024-25 analysis.

Candidate groups are exactly those R1 duplicate groups for which:

    reporting_period_consistent = false

Frozen expected candidate count:

    1

Any other count fails closed.

## Stable identity

Unchanged from D010/R1:

1. normalized CIN when present;
2. otherwise normalized NSE symbol.

R2 introduces no new company-identity heuristic.

## Period parser

Each current-financial-year start/end value must parse deterministically using,
in order:

1. ISO-8601 date/datetime;
2. DD-MON-YYYY;
3. DD-MM-YYYY;
4. YYYY-MM-DD;
5. numeric Excel serial date using epoch 1899-12-30.

The raw value is retained.

## Period-keyed semantics

For a candidate stable identity, filings are partitioned by the normalized pair:

    (financial_year_start, financial_year_end)

Each distinct pair is a separate reporting-period key.

R2 passes a candidate only if ALL of the following hold.

### Period validity

- every filing has parseable start and end dates;
- every period has start < end;
- every period length is between 330 and 370 days inclusive;
- at least two distinct reporting-period keys exist;
- distinct reporting periods do not overlap.

Adjacent annual periods are allowed.

### Filing validity inside each period

- every APP_ID is present;
- APP_IDs are unique within the candidate identity;
- every submission timestamp is parseable;
- submission timestamps are unique within the candidate identity;
- every filing has at least one explicit NIC row;
- every filing submission date is on or after its reporting-period end date.

If multiple filings exist for one period, they must therefore form a
deterministically ordered amendment chain under the same R1 semantics.

### Cross-period integrity

- no APP_ID appears in more than one reporting period;
- no submission-timestamp collision exists across periods;
- no period overlap exists.

Symbol changes for the same CIN are reported but do not fail R2.

NIC changes between reporting periods are reported but do not fail R2. They are
legitimate point-in-time classification changes if all other gates pass.

## R2 pass

R2 passes only if:

- the reproduced R1 candidate count equals exactly one;
- that candidate passes every frozen period-keyed gate.

Success status:

    PASS_CROSS_PERIOD_SEMANTICS

A pass authorizes only a separately frozen:

    RM001-D012-PERIOD-KEYED-HISTORICAL-ASOF-TIMELINE-DIAGNOSTIC

R2 does NOT:

- change D010 from FAIL_SOURCE_FEASIBILITY;
- change R1 from FAIL_DUPLICATE_SEMANTICS;
- authorize D011;
- add a NIC/sector factor to RM001;
- select dominant-NIC or multi-NIC portfolio exposures;
- open stock-return labels;
- fit a risk model;
- fit a portfolio.

## Failure

Any malformed, overlapping or temporally impossible period structure leaves the
BRSR/NIC historical sector path blocked under the current source family.

No threshold may be weakened after candidate-row inspection.
