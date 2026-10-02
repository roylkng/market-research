# RM001 D013 Period-Partitioned As-Of BRSR Timeline Diagnostic v1

Status: FROZEN BEFORE D013 SOURCE QUERIES
Frozen: 2026-10-02
Live capital: DISABLED

## Parent evidence

D010 Phase C:
- result SHA-256: 21aff20c7c3300ecf104d049fdbcad3749bb160735f478643a40bab36618a976
- status: FAIL_SOURCE_FEASIBILITY

D010-R1:
- result SHA-256: eedc9bba0dfcb15a394af800cdc84f2e20ab48b95632d8941e5af169e1291522
- status: FAIL_DUPLICATE_SEMANTICS

D010-R2:
- result SHA-256: 18741e771f314c91e895c4c017e2f079553292b9c30991ffe0a432cf4e5f87d5
- status: PASS_PERIOD_PARTITION_SEMANTICS
- D013 authorized: true

D010 and R1 remain failed regardless of D013 outcome.

## Objective

Determine whether the exact frozen NSE BRSR structured archives can be converted
into a deterministic point-in-time company → ISIN → NIC-exposure timeline
without look-ahead.

D013 is source/timeline semantics research only.

It opens:
- no stock-return labels;
- no RM001 factor-return fit;
- no covariance comparison;
- no PO001 result.

## Frozen BRSR archives

FY2023-24:
https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip

SHA-256:
f287b4137b662a2f1cdba54f8d3858f84f09f43e1f0702ad5b2299cde5fb16ef

FY2024-25:
https://nsearchives.nseindia.com/web/mediaattachment/2026-04/BRSR_DUMP_FY24-25_20260414130852.zip

SHA-256:
c5209af34ec21dd76f621f50ca6f8f5f5e07d6d09fb3591a9a636a59e4af0b42

No alternate archive may substitute.

## Frozen filing identity

Reuse D010/R1/R2 unchanged.

Stable identity:
1. normalized CIN when present;
2. otherwise normalized NSE symbol.

Entity/product join:
- APP_ID.

Reporting period:
- explicit current financial-year start date;
- explicit current financial-year end date;
- parsed under the R2 parser only.

Within one stable identity + reporting period:
- filings are ordered by TLA_SUBMITTED_DT;
- latest filing public by an as-of instant supersedes earlier filings in that
  same period.

Across reporting periods:
- the period with the latest period end date wins once at least one filing for
  that period is public;
- a late amendment to an older reporting period cannot supersede an already
  public newer reporting period.

## Phase A: prove TLA_SUBMITTED_DT public-time semantics

D013 MUST NOT assume that a naive TLA_SUBMITTED_DT value is IST.

Independent official timing source:

NSE corporate-announcement endpoint:
    /api/corporate-announcements

Parameters:
- index = equities;
- symbol;
- from_date;
- to_date.

NSE's corporate-filings surface states that company-uploaded information is
displayed on the Exchange website immediately upon receipt. The announcement
feed exposes official exchange dissemination timestamps.

### Deterministic sample

For each required year select exactly 40 eligible filing records, or every
eligible filing if fewer than 40 exist.

Eligible sample record:
- stable identity present;
- APP_ID present;
- NSE symbol present;
- TLA_SUBMITTED_DT parseable under R1;
- reporting period parseable under R2;
- at least one explicit NIC row.

Selection score:
    SHA256(
      year + "|" +
      stable_identity + "|" +
      reporting_period_start + "|" +
      reporting_period_end + "|" +
      APP_ID
    )

Take the lexicographically smallest 40 scores per year.

No observed announcement activity, return, sector result or later coverage may
alter the sample.

### Announcement candidate

For each sampled filing query the filing symbol for:

    raw TLA calendar date - 1 day
    through
    raw TLA calendar date + 1 day

A candidate announcement must:
- have exact symbol match;
- have a parseable official dissemination timestamp;
- contain either:
  - token "BRSR"; or
  - both phrases "Business Responsibility" and "Sustainability"
  in desc + attchmntText.

The filing is matched to the candidate with minimum absolute timestamp distance
under the Asia/Kolkata interpretation of the raw TLA value.

Equal-distance ties fail closed.

The same announcement sequence ID may not match two sampled filings.

### Candidate timezone test

For every matched filing calculate:

1. raw TLA interpreted as Asia/Kolkata;
2. raw TLA interpreted as UTC;
3. official NSE announcement dissemination time in UTC.

Frozen timing gates:

- sample match fraction >= 90% in EACH required year;
- Asia/Kolkata median absolute delta <= 60 seconds;
- Asia/Kolkata p95 absolute delta <= 300 seconds;
- every matched dissemination delta relative to TLA-IST is between
  -60 seconds and +900 seconds;
- UTC median absolute delta >= 14,400 seconds;
- no announcement sequence ID is reused.

D013 passes timestamp semantics only if every gate passes.

### Historical availability time

Only if Phase A passes:

For every archive filing:

    available_at =
      TLA_SUBMITTED_DT interpreted as Asia/Kolkata
      + 15 minutes

The 15-minute buffer is frozen before matching and is intentionally conservative.

If Phase A fails, no full historical as-of timeline is authorized.

## Phase B: point-in-time symbol → ISIN join

Source:

Daily NSE CM MII Security File already accepted by D007:

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_DDMMYYYY.csv.gz

For each filing:
1. convert available_at to Asia/Kolkata calendar date;
2. start at calendar date - 1;
3. search backward at most 10 calendar days;
4. use the first downloadable, parser-valid Security File;
5. require exactly one EQ row for the filing symbol;
6. bind that filing to the row's ISIN.

This deliberately uses a strictly prior completed security-master session.
Same-day end-of-day data is never used to identify an intraday filing.

Symbol changes for one CIN are allowed. Each filing resolves its own symbol
independently.

Frozen join gate:
- exact filing-level symbol→ISIN coverage >= 99%;
- zero ambiguous symbol→multiple-ISIN joins within the selected prior Security
  File;
- zero content-addressed source collisions.

## Phase C: frozen multi-NIC exposure transformation

NIC granularity:
- exact reported NIC code;
- no truncation to section/division/group;
- no return-driven taxonomy choice.

For one filing:

### Single distinct NIC

Exposure:
    NIC = 1.0

Turnover-share completeness is diagnostic only for a single-NIC filing.

### Multiple distinct NICs

Every explicit product/service NIC row must have a finite non-negative
"percentage of total turnover contributed".

Rows with the same NIC code are aggregated.

Let raw weight for NIC j be the sum of reported turnover percentages for that
NIC.

Required:
- every NIC row has a parseable weight;
- every raw weight >= 0;
- total reported weight > 0;
- total reported weight <= 100.5%.

The 0.5 percentage-point allowance is frozen solely for source rounding.

Normalized exposure:

    exposure_j = raw_weight_j / sum(raw_weight)

All normalized exposures must sum to 1 within 1e-12.

Frozen multi-NIC gate:
- 100% of multi-NIC filing records used by D013 must be transformable.

No equal-weight rescue is allowed.

## Phase D: as-of period selection and carry-forward

For an as-of UTC instant:

1. retain filings with available_at <= as_of;
2. partition by stable identity and reporting period;
3. within each period retain the latest available filing by
   (available_at, APP_ID);
4. discard a period after:

       reporting_period_end + 550 calendar days

5. among remaining periods choose the period with latest reporting-period end;
6. selected filing carries its exact symbol, ISIN and normalized NIC exposures.

A late amendment to an older period never displaces an already-public newer
period.

No filing may be carried beyond 550 days after its reporting-period end.

### Determinism audit

D013 evaluates the selector at:
- every filing available_at instant + 1 second;
- every period-expiry instant + 1 second.

Required:
- zero selection ties;
- zero future filing selection;
- zero expired filing selection;
- selected symbol/ISIN exactly equals the selected filing record;
- selected NIC weights sum to 1 within 1e-12.

## D013 pass

D013 passes only if ALL are true:

### Public-time gates
- >=90% announcement match fraction in each required year;
- frozen IST delta gates pass;
- frozen UTC-separation gate passes;
- zero reused announcement sequence IDs.

### Identity gates
- >=99% filing-level prior-session symbol→ISIN coverage;
- zero ambiguous symbol→ISIN joins.

### NIC gates
- explicit NIC filing coverage >=99%;
- 100% of multi-NIC filings are transformable;
- zero invalid normalized exposure vectors.

### Timeline gates
- 100% reporting-period parseability for timeline-eligible filings;
- zero selection ties;
- zero look-ahead selections;
- zero expired selections.

Success status:

    PASS_PERIOD_PARTITIONED_ASOF_TIMELINE

A pass authorizes only:

    RM001-D014_REGULATORY_NIC_EXPOSURE_PANEL_DIAGNOSTIC

D014 must separately freeze:
- daily exposure-panel construction window;
- NIC factor dimensionality / covariance treatment;
- missing/stale exposure behavior in the RM001 cross-section;
- whether the resulting factor set improves risk calibration.

D013 does NOT add a NIC factor to RM001.

## Failure

Any failed gate gives:

    FAIL_PERIOD_PARTITIONED_ASOF_TIMELINE

D010 and R1 remain failed.

No threshold may be weakened after D013 source results are opened.

## Explicit prohibitions

D013 must not:
- infer timezone from return behavior;
- use today's industry labels historically;
- use current quote-page industry labels as historical truth;
- use same-day future EOD security files for intraday identity;
- infer ISIN from company names;
- equal-weight incomplete multi-NIC rows;
- drop old-period filings from source metrics;
- open return labels;
- fit RM001 factor returns;
- run PO001.

No live-capital implication.
