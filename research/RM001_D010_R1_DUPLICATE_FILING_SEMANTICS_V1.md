# RM001 D010-R1 BRSR Duplicate Filing Semantics v1

Status: FROZEN BEFORE DUPLICATE-ROW INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Parent result

Parent experiment:

- RM001-D010-v1
- Phase C run: 37010062836
- Phase C result SHA-256:
  21aff20c7c3300ecf104d049fdbcad3749bb160735f478643a40bab36618a976
- parent status: FAIL_SOURCE_FEASIBILITY
- D011 authorized by parent: false

The sole failed parent gate was FY2023-24 duplicate stable-identity rate:

    2.408637873754153%

versus the frozen maximum:

    1%

R1 does not weaken or reinterpret that gate.

## Objective

Determine whether duplicate stable identities in the exact frozen BRSR annual
archives are deterministic re-filings/amendments that can be represented as an
as-of filing timeline.

R1 is source-semantics research only.

It opens:
- no return labels;
- no RM001 factor fit;
- no covariance result;
- no PO001 result.

## Exact frozen archives

FY2023-24:

https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip

SHA-256:

f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef

FY2024-25:

https://nsearchives.nseindia.com/web/mediaattachment/2026-04/BRSR_DUMP_FY24-25_20260414130852.zip

SHA-256:

c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42

No alternate archive may substitute for these bytes.

## Frozen relational tables

Reuse the exact D010 Phase C P1 tables and semantics:

Entity table:
- brsr_general.xlsx, allowing the already-frozen single trailing export suffix;
- APP_ID;
- TLA_SUBMITTED_DT;
- SYMB_SYMBOL;
- company name;
- CIN;
- current financial-year start/end.

NIC table:
- BRSR_GENERAL_PRODUCT_SERVICES_SOLD.xlsx;
- APP_ID;
- SYMB_SYMBOL;
- explicit NIC code;
- product/service text;
- turnover-share field.

Stable identity remains:

1. normalized CIN when present;
2. otherwise normalized NSE symbol.

No new identity heuristic is introduced.

## Duplicate group

A duplicate group is a stable identity with more than one entity-table filing
record in the same annual archive.

Every record remains visible. No duplicate is dropped for R1 metrics.

## Submission timestamp parser

R1 attempts deterministic parsing in this order:

1. ISO-8601 via datetime.fromisoformat;
2. DD-MON-YYYY HH:MM:SS;
3. DD-MON-YYYY HH:MM;
4. DD-MM-YYYY HH:MM:SS;
5. YYYY-MM-DD HH:MM:SS;
6. numeric Excel serial date/time using epoch 1899-12-30.

The raw timestamp is always retained.

R1 does not assign a timezone to timestamps that do not contain one. Timezone /
public-dissemination semantics are deferred to D012.

## Frozen amendment-chain gates

For each duplicate group in BOTH required years:

1. every filing record has non-empty APP_ID;
2. APP_ID is unique within the stable identity;
3. every filing record has a parseable TLA_SUBMITTED_DT;
4. submission timestamps are unique within the stable identity;
5. all records carry identical current financial-year start/end values;
6. every filing APP_ID joins to at least one explicit NIC row;
7. every product/NIC row used by the group maps to exactly one stable identity;
8. no same-timestamp competing filing exists for the stable identity.

Symbol changes for the same CIN are reported but do not fail R1 by themselves.
They may represent ticker changes while CIN remains the frozen stable identity.

NIC changes across temporally ordered filings are reported and do not fail R1 by
themselves. They are exactly the kind of revision an as-of timeline must
preserve.

## Year-level pass

A required year passes R1 only if:

- at least one duplicate group exists;
- 100% of duplicate groups satisfy all amendment-chain gates;
- 100% of duplicate filing records have parseable submission timestamps;
- 100% of duplicate filing records have at least one explicit NIC row;
- zero timestamp collisions;
- zero APP_ID-to-multiple-identity conflicts.

## R1 pass

R1 passes only if BOTH FY2023-24 and FY2024-25 pass.

Status:

    PASS_DUPLICATE_SEMANTICS

authorizes only:

    RM001-D012 historical as-of filing-timeline diagnostic

R1 does NOT:
- change D010 from FAIL to PASS;
- authorize D011;
- add a sector/NIC factor to RM001;
- choose dominant-NIC versus multi-NIC exposure semantics.

## D012, if authorized

D012 must separately prove:

- the interpretation/timezone of TLA_SUBMITTED_DT;
- whether that timestamp is tied to public filing availability;
- deterministic point-in-time symbol/ISIN joining;
- annual filing carry-forward rules;
- missing-period behavior;
- multi-NIC exposure semantics.

No returns may be opened until those source/timing rules are frozen.

## Failure

If any duplicate chain is not deterministically orderable under the frozen rules,
R1 fails and BRSR/NIC remains unsuitable for historical RM001 sector-risk use
under this path.

No threshold may be weakened after duplicate inspection.
