# RM001 D010-R2 Cross-Period Filing Semantics v1

Status: FROZEN BEFORE CONFLICT-ROW INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

D010 Phase C:
- run: 37010062836
- result SHA-256:
  21aff20c7c3300ecf104d049fdbcad3749bb160735f478643a40bab36618a976
- status: FAIL_SOURCE_FEASIBILITY

D010-R1:
- run: 37011294647
- result SHA-256:
  eedc9bba0dfcb15a394af800cdc84f2e20ab48b95632d8941e5af169e1291522
- status: FAIL_DUPLICATE_SEMANTICS

R1 established:
- FY2023-24: all 27 duplicate groups are deterministic amendment chains;
- FY2024-25: 3/4 duplicate groups are deterministic;
- the only remaining blocker is one duplicate stable identity with inconsistent
  financial-year start/end values;
- timestamps and NIC coverage remain complete;
- timestamp collisions = 0;
- APP_ID identity conflicts = 0.

D010 and R1 remain failed regardless of R2 outcome.

## Objective

Determine whether the sole R1 reporting-period conflict is evidence that the
FY2024-25 BRSR bulk archive contains filings from multiple explicit reporting
periods for the same stable company identity.

R2 tests whether a future source contract may partition filings by:

    stable identity + explicit reporting period

before amendment-chain logic is applied.

No return labels, RM001 fit, covariance result or PO001 result may be opened.

## Exact source

Only the frozen FY2024-25 archive is inspected:

https://nsearchives.nseindia.com/web/mediaattachment/2026-04/
BRSR_DUMP_FY24-25_20260414130852.zip

SHA-256:

c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42

No alternate/revised archive may substitute.

## Frozen identity and relational semantics

Reuse D010/R1 unchanged:

Stable identity:
1. normalized CIN;
2. otherwise normalized NSE symbol.

Entity/product join:
- APP_ID.

Required filing fields:
- APP_ID;
- TLA_SUBMITTED_DT;
- SYMB_SYMBOL;
- CIN;
- Current Financial Year start date;
- Current Financial Year end date.

Every conflict filing must retain all explicit NIC rows joined through APP_ID.

## Frozen period parser

Financial-year start/end values are parsed only as explicit calendar dates using:

1. YYYY-MM-DD;
2. DD-MM-YYYY;
3. DD-MON-YYYY;
4. ISO-8601 date/datetime via datetime.fromisoformat, date component only.

No inferred fiscal year is substituted for an unparseable value.

## Cross-period conflict group

A cross-period conflict group is an R1 duplicate stable identity containing more
than one distinct (financial_year_start, financial_year_end) pair.

R2 inspects all such groups in the frozen FY2024-25 archive.

## Per-record gates

Every filing record in every cross-period conflict group must have:

1. non-empty APP_ID;
2. parseable unique submission timestamp under R1 rules;
3. parseable financial-year start and end;
4. end >= start;
5. at least one explicit NIC code;
6. APP_ID mapping to exactly one stable identity.

## Per-group gates

Every cross-period group must satisfy:

1. at least two distinct reporting periods;
2. reporting periods are pairwise non-overlapping;
3. within each reporting period, filing timestamps are unique;
4. within each reporting period, APP_IDs are unique;
5. all records remain deterministically ordered by submission timestamp;
6. each reporting-period partition independently forms either:
   - a single filing, or
   - a deterministic amendment chain under R1's gates.

Symbol changes for the same CIN are reported but do not fail the group.

NIC changes across reporting periods or amendments are reported, not suppressed.

## Archive-target period

FY2024-25 archive target period is frozen as:

- start: 2024-04-01
- end: 2025-03-31

R2 reports whether each conflict group contains:
- zero;
- exactly one;
- more than one

filing partition matching that target period.

This is diagnostic only. R2 does not discard non-target periods.

## R2 pass

R2 passes only if:

- at least one cross-period conflict group exists;
- 100% of conflict groups satisfy all per-record and per-group gates;
- zero unparseable period records;
- zero overlapping reporting-period pairs;
- zero APP_ID identity conflicts.

Status:

    PASS_PERIOD_PARTITION_SEMANTICS

A pass authorizes only:

    RM001-D013 PERIOD_PARTITIONED_ASOF_TIMELINE_DIAGNOSTIC

D013 must separately freeze:
- public-time interpretation/timezone for TLA_SUBMITTED_DT;
- point-in-time filing carry-forward;
- period selection rules;
- symbol/ISIN joins;
- multi-NIC exposure transformation.

## Prohibitions

R2 must not:
- change D010 or R1 status;
- reinterpret the parent duplicate threshold;
- delete old-period records from parent metrics;
- select a period based on returns;
- open stock-return labels;
- fit RM001 or PO001.

No live-capital implication.
