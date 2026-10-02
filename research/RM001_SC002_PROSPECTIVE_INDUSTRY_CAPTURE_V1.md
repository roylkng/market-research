# RM001 SC002 Prospective Nifty Total Market Industry Capture v1

Status: FROZEN BEFORE FIRST SC002 OBSERVATION
Frozen: 2026-10-02
Earliest observation date: 2026-10-02
Live capital: DISABLED

## Objective

Start a clean prospective point-in-time company-industry history using the
official Nifty Total Market constituent file, independently identity-verified
against the official NSE Security File.

SC002 is source capture only.

It does not:
- backfill historical classifications;
- fit a sector/industry risk factor;
- open return labels;
- change any prior failed D015 diagnostic;
- authorize live capital.

## Parent authorization

SC002 is authorized by:

RM001-D015-R3-v1
`PASS_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS`

R3 report SHA-256:

`35d5245283112885670521a4d771fabf33b66b26fc94d8dbfba5dc0ed8e14288`

D015, D015-R1 and D015-R2 remain failed.

## Official sources

### Current classification snapshot

Nifty Total Market constituent CSV:

    https://nsearchives.nseindia.com/content/indices/
    ind_niftytotalmarket_list.csv

Required columns:
- Company Name
- Industry
- Symbol
- Series
- ISIN Code

### Identity/series verification

NSE CM MII Security File for the latest completed eligible AE001-SC001 market
session:

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_DDMMYYYY.csv.gz

The target market session is the latest AE001-SC001 session satisfying:

- eligible_before_cutoff = true;
- session_date <= local observation date.

No calendar-day assumption substitutes for SC001.

## Capture cadence

Approximate Asia/Kolkata times, every calendar day:

- 08:00
- 20:00

Plus manual workflow_dispatch.

Actual post-fetch UTC capture time is authoritative.

The twice-daily calendar cadence deliberately includes weekends and holidays.
This allows detection of constituent/classification file changes between trading
sessions.

## Frozen prospective semantics

The full constituent file and full Security File are always retained.

### Exact security-corresponded row

A parent row is security-corresponded only when exactly one same-snapshot
Security File row matches:

    Symbol + ISIN + Series

after trim + uppercase identity normalization.

### Index-only dummy placeholder

An unmatched parent row may be classified as a documented index-only dummy only
when ALL are true:

1. Series == EQ;
2. Symbol starts exactly with DUMMY;
3. exact Symbol+ISIN+Series Security File match count = 0;
4. same Symbol+ISIN Security File match count across all series = 0.

Future dummy count is variable.

No company-name matching.
No ISIN-only matching.
No symbol-only matching.
No fuzzy fallback.
No alternate dummy prefix.

## Snapshot eligibility

A capture is READY only when ALL are true:

1. both official source files are fetched successfully;
2. both parsers pass frozen schemas;
3. constituent row count >= 700;
4. every non-dummy EQ row has exactly one exact Security File triplet;
5. zero non-dummy EQ missing rows;
6. zero non-dummy EQ ambiguous rows;
7. every unmatched EQ row satisfies the frozen explicit dummy rule;
8. every non-EQ parent row has exactly one exact Security File triplet;
9. projected tradable EQ row count >= 700;
10. projected tradable EQ Symbol+ISIN identities are unique;
11. zero Symbol -> multiple ISIN conflicts;
12. zero ISIN -> multiple Symbol conflicts;
13. Industry coverage = 100% for projected tradable EQ;
14. ISIN coverage = 100% for projected tradable EQ;
15. Company Name and Symbol are complete;
16. every projected Security File row has deletion_flag in {"", "N"}.

Any ordinary non-dummy missing/ambiguous row makes the whole snapshot ineligible.

## Canonical tradable classification snapshot

For each READY capture, retain only the verified tradable EQ mapping in the
canonical compressed snapshot:

- symbol;
- isin;
- company_name;
- industry;
- parent series;
- Security File series;
- Security File deletion flag.

The full excluded dummy and non-EQ diagnostics remain in snapshot metadata.

The one-level `Industry` string is retained exactly from the official
constituent file. SC002 does not infer Sector/Basic Industry/Macro Sector.

## Point-in-time semantics

The authoritative information timestamp is the actual post-fetch
`captured_at_utc`.

A snapshot may only be used by a later risk-model decision whose decision
timestamp is strictly after that capture time.

No snapshot is assigned an earlier effective date from:
- constituent-file content;
- previous-month page labels;
- rebalance assumptions;
- announcement dates.

Historical backfill remains prohibited.

## Content-addressed evidence

Canonical ledger:

    research/prospective/rm001-sc002/source-ledger.json

Derived readiness summary:

    research/prospective/rm001-sc002/readiness-summary.json

Raw sources:

    research/prospective/rm001-sc002/raw/<capture-date>/

Canonical READY mappings:

    research/prospective/rm001-sc002/snapshots/

Each attempt records:
- observation date;
- target Security File session;
- actual capture timestamp;
- constituent URL/SHA/path/status;
- Security File URL/SHA/path/status;
- source-semantics diagnostics;
- mapping snapshot path/hash when READY;
- attempt hash.

Repeated probes with identical observation date, target session and both exact
raw hashes are idempotent.

## Change diagnostics

For each READY snapshot, compare with the immediately preceding READY snapshot:

- added identities;
- removed identities;
- unchanged identities;
- industry-changed identities;
- dummy-count change;
- mapping SHA change.

Changes are recorded prospectively only.

No changed classification is projected backward.

## Operational promotion gate

SC002 source capture is operationally ready only after:

- at least 5 distinct READY observation dates;
- at least 3 distinct READY target market sessions.

Promotion status:

`PROSPECTIVE_INDUSTRY_SOURCE_CAPTURE_READY`

This does NOT automatically enable an RM001 industry factor.

## Next stage

After SC002 operational readiness, a separately frozen RM001 industry-factor
challenger must define:

- categorical encoding;
- factor-return estimation;
- treatment of rare industries;
- covariance integration;
- prospective decision timing;
- comparison against the current RM001 model.

No live-capital implication.
