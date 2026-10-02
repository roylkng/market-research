# RM001 D010 BRSR/NIC Point-in-Time Industry Source Feasibility v1

Status: FROZEN BEFORE SOURCE ZIP / FILING INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Determine whether official NSE Business Responsibility and Sustainability Report
(BRSR) filings can provide a dated, company-identifiable National Industrial
Classification (NIC) mapping suitable for a future RM001 industry-risk factor.

D010 is source-feasibility research only.

It opens:
- no stock-return outcomes;
- no alpha outcomes;
- no RM001 factor fit;
- no covariance comparison;
- no PO001 portfolio result.

## Motivation

D007 proved that the daily NSE CM Security File is a high-coverage point-in-time
total-market-cap source, but its company-industry fields are not materially
populated.

D008 proved that the sampled NSE Capital Market Exchange Monthly Reports do not
contain a broad company-level industry classification mapping.

D010 therefore tests a different official regulatory source family rather than
weakening D007/D008 gates.

BRSR is filed by listed entities through NSE's structured XBRL compliance
infrastructure. The BRSR form contains NIC-based product/service classification
fields and may therefore support an annual regulatory industry exposure.

D010 does NOT call this an "NSE sector" factor.

If promoted later, the factor name must reflect the source taxonomy, for example:

    REGULATORY_NIC_INDUSTRY

## Frozen official source family

### Current BRSR XBRL utility

https://nsearchives.nseindia.com/web/mediaattachment/2026-03/
NSE_Business_Responsibility__Sustainability_Reporting_20260330194720.zip

### Current BRSR taxonomy

https://nsearchives.nseindia.com/web/mediaattachment/2026-03/
Taxonomy_BRSR_20260330194931.zip

### NSE XBRL taxonomy archives

https://nsearchives.nseindia.com/web/mediaattachment/2026-07/
Taxonomy_Archives_20260731164437.zip

### NSE BRSR corporate-filings surface

https://www.nseindia.com/companies-listing/
corporate-filings-bussiness-sustainabilitiy-reports

### NSE compliance archive surface

https://www.nseindia.com/regulations/listing-compliance

The compliance page explicitly lists annual BRSR bulk datasets for:

- FY 2021-22;
- FY 2022-23;
- FY 2023-24;
- FY 2024-25.

The exact dynamic annual archive download URLs are intentionally NOT guessed
before source inspection.

## Frozen endpoint-discovery rule

D010 may discover the annual BRSR archive URLs only from:

1. exact bytes returned by the official NSE compliance page above;
2. scripts/resources directly referenced by that official page;
3. requests/endpoints deterministically encoded in those official page/script
   bytes;
4. redirects returned by those official NSE endpoints.

Allowed hosts:

- www.nseindia.com
- nseindia.com
- nsearchives.nseindia.com
- www1.nseindia.com
- betanseapi.nseindia.com

No search-engine result, third-party mirror, guessed filename, BSE file, company
website or manually substituted archive may satisfy the D010 source gate.

Every discovered source URL and exact source byte SHA-256 must be retained.

## Phase A: taxonomy/schema feasibility

Inspect the exact current utility, current taxonomy and taxonomy archive ZIP
bytes.

Report:

- ZIP member names and SHA-256;
- XSD/XML/XLS/XLSX member counts;
- BRSR namespace/version identifiers;
- identity concepts/labels;
- financial-year / reporting-period concepts;
- NIC-related concepts/labels;
- product/service description concepts;
- turnover-share / percentage concepts associated with products/services;
- whether NIC is scalar or repeatable;
- whether multiple NIC rows are structurally supported;
- whether the current utility/taxonomy contains direct NSE symbol, ISIN or CIN
  identity fields.

Phase A passes only if:
1. at least one explicit NIC concept exists;
2. company identity includes at least CIN or another stable company identifier;
3. financial/reporting year is explicit;
4. the schema structurally supports deterministic extraction of NIC values.

## Phase B: annual bulk archive discovery

Discover exact official annual BRSR archive URLs for at least:

- FY 2023-24;
- FY 2024-25.

FY 2021-22 and FY 2022-23 are diagnostic extensions if discoverable under the
same frozen rule.

For every discovered archive report:

- exact URL;
- redirect chain;
- file type;
- file size;
- SHA-256;
- ZIP member count if applicable;
- first-level member extensions;
- whether the archive contains XBRL/XML, CSV, XLS/XLSX, PDF or nested ZIP files.

Phase B passes only if both FY 2023-24 and FY 2024-25 are retrieved from exact
official NSE URLs under the frozen discovery rule.

## Phase C: filing-level identity and NIC coverage

If Phase B passes, inspect every parseable structured filing in FY 2023-24 and
FY 2024-25.

Do not parse PDF free text to create a passing classification source.

Structured filing formats allowed:

- XBRL/XML;
- CSV;
- XLS/XLSX where cells correspond to the official BRSR schema.

For each filing/entity extract, when present:

- company/entity name;
- CIN;
- NSE symbol;
- ISIN;
- reporting financial year;
- filing/publication timestamp if carried by source metadata;
- all explicit NIC codes;
- associated product/service descriptions;
- associated turnover-share percentages.

Report:
- unique entity count;
- direct identity coverage;
- NIC coverage;
- entities with one NIC code;
- entities with multiple NIC codes;
- entities with turnover-weighted NIC rows;
- malformed/ambiguous records;
- duplicate identity count.

## Frozen coverage gates

D010 may authorize a successor historical join/timing diagnostic only if BOTH
FY 2023-24 and FY 2024-25 satisfy:

1. at least 500 unique listed entities with structured BRSR filings;
2. at least 90% of parsed entities have at least one explicit NIC code;
3. at least 90% have a deterministic stable identity using one of:
   - ISIN;
   - CIN;
   - NSE symbol from official filing metadata;
4. duplicate stable identity rate is <= 1%;
5. reporting year is explicit for >= 99%;
6. the semantics of NIC extraction are stable across both years;
7. no unexplained fixed row/file cap is present.

## Multiple-NIC rule

D010 does not freeze an RM001 exposure transformation.

It reports the empirical structure only.

A future promotion diagnostic must separately freeze one of:

- dominant NIC by explicitly reported turnover share;
- turnover-weighted multi-NIC exposures;
- another economically justified rule.

D010 must not choose whichever transformation looks best against returns.

## Point-in-time timing gate

D010 itself does not promote a historical point-in-time factor merely because
annual archives exist.

A successor diagnostic must prove when each company filing became public.

Acceptable timing evidence includes:

- NSE filing broadcast/dissemination timestamp;
- source file metadata demonstrably tied to publication;
- another separately frozen official timestamp.

If annual bulk archives lack per-filing publication timestamps, they may still
establish schema/coverage but cannot by themselves establish historical
availability dates.

## Promotion outcomes

### PASS_SOURCE_FEASIBILITY

Authorizes a separately frozen D011 historical identity/timing join diagnostic.

Does NOT add a sector/NIC factor to RM001.

### FAIL_SOURCE_FEASIBILITY

Sector/industry remains:

    DEFERRED_POINT_IN_TIME_SOURCE_NOT_FROZEN

Do not weaken the 500-entity / 90%-coverage gates after source inspection.

## Explicit prohibitions

D010 must not:

- use today's NSE Basic Industry historically;
- infer NIC from company names or narrative business descriptions;
- use PDF/OCR extraction to rescue missing structured NIC;
- substitute index membership for industry;
- use market returns to select NIC granularity;
- fit RM001 or PO001;
- inspect future-return labels.

No live-capital implication.
