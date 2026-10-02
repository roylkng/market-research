# RM001 D010 Phase C P1 Relational Coverage Contract

Status: FROZEN BEFORE FORMAL PHASE C COVERAGE CALCULATION
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

Phase A/B:
- run 37007303564
- result SHA-256:
  64a0ec350f76ba3413d037fc8b3bd234dd9389be915032a5048f9526cd3e444b
- Phase A PASS
- Phase B PASS_URL_DISCOVERY

Phase C0:
- run 37008138534
- FY2023-24 archive SHA-256:
  f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef
- FY2024-25 archive SHA-256:
  c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42
- annual dumps are relational XLSX collections.

The parent D010 coverage thresholds are unchanged.

## Frozen table selection

For each required year, Phase C uses exactly:

### Entity table

Workbook whose basename normalizes to:

    brsr_general.xlsx

For FY2023-24, a single trailing export suffix such as
`brsr_general 1.xlsx` is considered the same frozen table.

Required entity fields:
- APP_ID;
- TLA_SUBMITTED_DT;
- SYMB_SYMBOL;
- Name of The Company;
- Corporate Identity Number (CIN) of the Listed Entity;
- Current Financial Year start date;
- Current Financial Year end date.

### NIC table

Workbook whose basename contains:

    BRSR_GENERAL_PRODUCT_SERVICES_SOLD

Required fields:
- APP_ID;
- SYMB_SYMBOL;
- Product/Service sold by the entity;
- NIC Code sold by the entity;
- Percentage(%) of total Turnover contributed sold by the entity.

No Principle-2 lifecycle-assessment NIC field may substitute for the frozen
general product/service NIC table.

## XLSX extraction

Only the `Export Worksheet` sheet is used.

Values are read from the XLSX XML structure deterministically. The SQL sheet is
ignored.

No formulas or display formatting are used to infer missing values.

## Entity identity

Each nonblank entity-table row is a filing record.

Stable identity priority:

1. normalized non-empty CIN;
2. otherwise normalized non-empty NSE symbol.

Stable identity coverage:

    filing records with a stable identity / parseable filing records

Unique entity count:

    count(distinct stable identity)

CIN coverage and NSE-symbol coverage are reported separately.

## Duplicate identity rate

For every stable identity with n filing records in the same annual dump,
duplicates contribute max(n - 1, 0).

    duplicate_identity_rate =
        duplicate_filing_records / parseable filing records

No duplicate is silently dropped for the coverage calculation.

## Reporting-year coverage

A filing record has explicit reporting-year coverage only when both:

- Current Financial Year start date;
- Current Financial Year end date

are non-empty.

The parser does not force March year-end or require the archive label to equal
the entity's fiscal-year end.

## NIC join

NIC rows join to filing records only by exact normalized APP_ID.

A stable entity has explicit NIC coverage when any APP_ID belonging to that
entity has at least one non-empty explicit NIC code in the frozen NIC table.

No NIC is inferred from:
- CIN digits;
- company name;
- business activity narrative;
- product description;
- another BRSR principle;
- current NSE industry labels.

## Multiple NIC reporting

For each stable entity report:
- count of distinct explicit NIC codes;
- whether more than one NIC is present;
- whether every retained NIC row has a parseable turnover-share value.

D010 does not choose a dominant or weighted industry exposure.

## Coverage gates

The original D010 gates remain:

For BOTH FY2023-24 and FY2024-25:

- unique entities >= 500;
- explicit NIC coverage >= 90%;
- stable identity coverage >= 90%;
- duplicate identity rate <= 1%;
- reporting-year coverage >= 99%.

Across both years:
- required NIC-table semantic headers must be present and compatible.

## Source-completeness / fixed-cap gate

D010 has no independent filing-count denominator in the frozen source family.

Therefore Phase C reports archive/table row counts and whether required-year
entity counts are exactly equal, but does not declare the fixed-cap gate passed
solely from the dump itself.

Promotion to a historical factor requires either:
- all coverage gates pass AND no suspicious cap pattern is observed; or
- a separately frozen official completeness diagnostic resolves any cap
  ambiguity.

A failed NIC/identity/year gate is sufficient to fail D010 regardless of cap
status.

## Result semantics

PASS_SOURCE_FEASIBILITY may authorize D011 only.

FAIL_SOURCE_FEASIBILITY leaves sector/industry deferred.

No returns, RM001 fit, covariance comparison, PO001 result or live capital.
