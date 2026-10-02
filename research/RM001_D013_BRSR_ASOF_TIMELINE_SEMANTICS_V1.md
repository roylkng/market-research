# RM001 D013 BRSR Period-Keyed As-Of Timeline Semantics v1

Status: FROZEN BEFORE D013 API / TIMELINE SOURCE INSPECTION
Frozen: 2026-10-02
Live capital: DISABLED

## Parent authorization

Parent diagnostic:

- RM001-D010-R2-v1
- workflow run: 37012161546
- result SHA-256:
  18741e771f314c91e895c4c017e2f079553292b9c30991ffe0a432cf4e5f87d5
- status: PASS_PERIOD_PARTITION_SEMANTICS
- D013 authorized: true

D010 remains FAIL_SOURCE_FEASIBILITY.
D010-R1 remains FAIL_DUPLICATE_SEMANTICS.

D013 does not alter either parent result.

## Objective

Determine whether the official NSE BRSR annual exports plus the official NSE
BRSR public-filings API can support a deterministic historical point-in-time
regulatory-industry timeline.

D013 must establish, without stock-return inspection:

1. which explicit annual-export financial-year fields represent the BRSR report
   period;
2. whether annual TLA_SUBMITTED_DT dates are tied to NSE public filing dates;
3. whether a filing can be joined point in time to exact NSE symbol + ISIN;
4. a deterministic multi-NIC exposure transformation.

D013 opens no stock-return labels and fits no risk or portfolio model.

## Exact annual archives

FY2023-24:

URL:
https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip

SHA-256:
f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef

FY2024-25:

URL:
https://nsearchives.nseindia.com/web/mediaattachment/2026-04/BRSR_DUMP_FY24-25_20260414130852.zip

SHA-256:
c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42

No alternate or revised archive may substitute.

## Already-opened official NSE web contract

D010 Phase A/B run 37007303564 retained exact official NSE BRSR page/script
bytes.

Frozen D010 Phase A/B result SHA-256:

64a0ec350f76ba3413d037fc8b3bd234dd9389be915032a5048f9526cd3e444b

Captured NSE page JavaScript SHA-256:

b12ac5ec04f5a407f861cf308231673656e902bdf1e35720927c18124f5ea240

That exact official script references:

Public API:
https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy

Table configuration:
https://www.nseindia.com/json/CorporateFiling/CF-bussinesssustainabilitiyreports.json

D013 freezes those URLs before either response is inspected for D013.

## Phase A: report-period semantics

### Frozen annual fields

Entity table:
brsr_general.xlsx

Required fields:

- APP_ID;
- TLA_SUBMITTED_DT;
- SYMB_SYMBOL;
- CIN;
- Current Financial Year start date;
- Current Financial Year end date;
- Previous Financial Year start date;
- Previous Financial Year end date;
- Prior to Previous Financial year start date;
- Prior to Previous Financial year end date.

Candidate report period is frozen BEFORE D013 measurement as:

    Previous Financial Year start/end

Rationale comes only from already-opened taxonomy/schema evidence:

- NSE taxonomy contains
  "Details of financial year for which reporting is being done";
- annual export separately carries Current, Previous and Prior-to-Previous FY
  fields;
- R2 proved the Current FY pair can differ across filings for the same company
  without relational ambiguity.

D013 tests this candidate. It does not select whichever period fits best after
measurement.

### Frozen target report periods

FY2023-24 archive target:

    2023-04-01 through 2024-03-31

FY2024-25 archive target:

    2024-04-01 through 2025-03-31

### Phase-A gates

Across BOTH required archives:

1. >=99% of filing rows have parseable Current / Previous /
   Prior-to-Previous start/end dates;
2. >=99% have annual Previous FY length between 330 and 370 days;
3. >=99% have annual Current FY length between 330 and 370 days;
4. >=99% satisfy:
       Previous FY end + 1 day == Current FY start;
5. >=99% satisfy:
       Prior-to-Previous FY end + 1 day == Previous FY start;
6. >=95% of filing submission calendar dates fall within the explicit Current FY;
7. each archive has >=90% of stable identities with at least one filing whose
   Previous FY equals the archive's frozen target period;
8. grouping by:
       stable identity + Previous FY start/end
   leaves every multi-filing period group deterministically ordered under R1
   APP_ID/timestamp/NIC gates.

Stable identity remains:

1. normalized CIN;
2. otherwise normalized NSE symbol.

No new company-identity heuristic is introduced.

## Phase B: frozen regulatory NIC exposure transform

The already-opened NSE taxonomy explicitly defines the product/service table as:

    products or services sold by the entity accounting for ninety percent
    of the turnover

Source table:

BRSR_GENERAL_PRODUCT_SERVICES_SOLD.xlsx

Frozen per-filing transformation:

1. retain every explicit NIC code and its reported
   Percentage of total turnover for product or service sold;
2. NIC must contain at least two leading digits;
3. map each row to NIC2 = first two digits;
4. turnover percentages must be finite and in [0, 100];
5. aggregate turnover percentage by NIC2;
6. total reported turnover percentage must be in [90, 105];
7. normalize aggregated NIC2 percentages by their reported total so exposure
   weights sum to 1.

No missing percentage is imputed.
No company-description NLP is used.
No return data selects NIC granularity.

A filing is EXPOSURE_READY only if all transformation gates pass.

Phase B passes only if >=95% of target-period latest filings in EACH required
archive are EXPOSURE_READY.

"Latest filing" means the maximum parseable TLA_SUBMITTED_DT inside the stable
identity + Previous-FY period group.

The full amendment history is preserved for future as-of construction. Selecting
latest here is only for measuring transform coverage.

## Phase C: deterministic public-time sample

D013 does not query all companies before timing semantics are proven.

For EACH required archive target period:

1. include every stable-identity + Previous-FY group with more than one filing;
2. from remaining single-filing groups, rank by SHA-256 of:
       year | stable_identity | previous_start | previous_end
3. add the lowest hashes until the sample reaches 40 period groups.

If amendment groups alone exceed 40, include all amendment groups.

Sample selection is fixed before API response inspection.

For each sampled period group:

- API symbol = symbol from the earliest annual filing in that period group;
- query window = earliest annual submission date minus 30 calendar days through
  latest annual submission date plus 30 calendar days;
- date format = DD-MM-YYYY;
- endpoint = frozen official BRSR API above.

## Phase D: official table/API semantic mapping

The frozen table-config JSON is authoritative for API field semantics.

D013 must discover exactly one response key for each public-table semantic label:

- Company;
- From Year;
- To Year;
- Original Submission Date;
- Latest Revision Date.

Key names may not be guessed from response values.

The API must return a JSON object containing a data array, matching the already
opened official page JavaScript contract.

For each sampled period group D013 attempts to identify the unique API row whose
From Year / To Year match the frozen candidate Previous-FY report period.

### Timing gates

Across EACH year's deterministic sample:

1. table-config semantic mapping is unique and complete;
2. API request succeeds for >=90% of sampled groups;
3. a unique exact period match exists for >=90% of sampled groups;
4. among exact period matches, API Original Submission Date equals the calendar
   date of the earliest annual TLA_SUBMITTED_DT for >=95%;
5. for multi-filing groups, API Latest Revision Date equals the calendar date of
   the latest annual TLA_SUBMITTED_DT for >=95%;
6. zero sampled group has two API rows with the same symbol/report-period key but
   conflicting original/revision dates.

D013 does not infer a timezone from a date-only or timezone-naive source.

## Conservative historical availability rule

If Phase D passes, a filing's historical market-availability session is frozen as:

    first completed NSE cash-market session STRICTLY AFTER
    the TLA_SUBMITTED_DT calendar date

This intentionally sacrifices same-day information rather than inventing a
timezone/public-dissemination instant.

A later experiment may freeze a sharper timestamp rule only with stronger
official evidence.

## Phase E: point-in-time symbol + ISIN join

For every sampled annual filing whose API timing match passes:

1. resolve the first completed NSE cash session strictly after the filing
   calendar date using official NSE CM UDiFF availability;
2. on that session require exactly one NSE CM STK EQ row for the annual filing
   symbol;
3. record exact symbol + ISIN identity;
4. no today's symbol/ISIN may be projected backward.

Phase E passes only if:

- >=95% of timing-matched sampled filings resolve to exact symbol+ISIN;
- zero sampled filing maps to multiple EQ identities;
- all retained source bytes and hashes are preserved.

Symbol changes for the same CIN are allowed. The as-of identity is whatever exact
symbol+ISIN is observed on the conservative availability session.

## D013 pass

D013 passes only if Phases A, B, D and E all pass.

Success status:

    PASS_ASOF_TIMELINE_SEMANTICS

A pass authorizes only:

    RM001-D014 FULL HISTORICAL REGULATORY_NIC2 TIMELINE MATERIALIZATION

D014 must still:

- materialize every filing/amendment point in time;
- carry the latest known filing forward only after its frozen availability
  session;
- preserve exact symbol+ISIN transitions;
- quantify market-universe coverage through time;
- remain outcome-free until a later risk-factor challenger is separately frozen.

## Prohibitions

D013 must not:

- retroactively change D010, R1 or R2;
- use Current FY as report period if the frozen Phase-A gates fail;
- choose a different FY field after inspection;
- query alternative providers to fill NSE gaps;
- infer NIC from company narrative;
- use today's classifications historically;
- inspect stock-return labels;
- fit RM001 covariance;
- fit PO001;
- authorize live capital.
