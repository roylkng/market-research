# AE001 D011 NSE Historical Mutual-Fund Ownership Source Feasibility v1

Status: FROZEN BEFORE SOURCE ACCESS
Frozen: 2026-10-01
Live capital: DISABLED
Return outcomes: PROHIBITED

## Objective

Determine whether official NSE shareholding-pattern master records and XBRLs
provide enough historical point-in-time Mutual Fund ownership observations to
justify a separate future AE001 ownership-alpha trial.

D011 is a source/data diagnostic only.

It does not:
- fit an alpha model;
- open stock returns;
- reinterpret H023;
- promote any ownership signal into AB001.

## Source contract

Reuse the already frozen H023 official NSE source semantics:

Master endpoint:

    https://www.nseindia.com/api/corporate-share-holdings-master

Approved filing content:

    https://nsearchives.nseindia.com/
    https://archives.nseindia.com/

Frozen Mutual Fund fact:

- context: MutualFundsOrUTI_ContextI
- concept: ShareholdingAsAPercentageOfTotalNumberOfShares
- unit: pure
- value: fraction of total shares, converted to percentage points by * 100
- context instant must equal selected report date

Official NSE broadcastDate is the point-in-time availability timestamp.

## Diagnostic universe

Source-only stratified sample from the already frozen H023 universe:

    research/prospective/universes/FY27-Q2-2026-09-06.json

Select exact H023 ranks:

    1, 5, 9, 13, 17, 21, 25, 29, 33, 37,
    41, 45, 49, 53, 57, 61, 65, 69, 73, 77,
    81, 85, 89, 93, 97

Sample count: 25.

This sample is for source feasibility only. It is NOT an authorized historical
return universe.

## Historical report dates

Audit these standard quarter ends:

- 2024-03-31
- 2024-06-30
- 2024-09-30
- 2024-12-31
- 2025-03-31
- 2025-06-30
- 2025-09-30
- 2025-12-31
- 2026-03-31
- 2026-06-30

For each symbol/report date, the current source is the first official NSE
broadcast for that report date.

## Adjacent-quarter context

For every target current quarter from 2024-06-30 through 2026-06-30:

- prior report date = immediately previous standard calendar quarter end;
- prior source = latest protocol-valid official revision for the prior report
  date whose broadcastDate is <= current source broadcastDate.

A later prior-quarter revision cannot be used retrospectively.

## Exact evidence

For every selected source retain:

- symbol;
- report date;
- record ID;
- official broadcast timestamp;
- approved XBRL URL;
- master-row/source identity;
- XBRL SHA-256;
- parse status;
- Mutual Fund ownership percentage if READY.

No alternate provider may fill an NSE gap.

## Frozen source-feasibility metrics

Report:

- sample symbol count;
- expected symbol-quarter count;
- first-broadcast current-source coverage;
- current XBRL parse-ready coverage;
- adjacent prior-context coverage;
- adjacent current+prior parse-ready pair coverage;
- unique selected XBRL count;
- source and parser rejection reason counts;
- earliest/latest broadcast timestamps.

## Promotion gates

D011 passes only if ALL are true:

1. every one of the 25 sample symbols has a valid NSE master response;
2. first-broadcast current-source coverage >= 90% across the 250
   symbol-quarter opportunities;
3. current XBRL parse-ready coverage >= 90%;
4. adjacent current+prior parse-ready pair coverage >= 80% across the 225
   adjacent-quarter opportunities;
5. no duplicate official record ID/source identity ambiguity exists;
6. no unexpected XBRL Mutual Fund axis/concept/unit drift is observed among
   READY sources.

## Promotion

A passing D011 may justify a NEW trial/design phase for historical ownership
features.

D011 itself cannot authorize:
- T011;
- an H023 historical return backtest;
- AB001 promotion;
- live capital.

Any future ownership-alpha trial must separately freeze:
- a point-in-time historical universe;
- feature definitions;
- horizons;
- folds;
- success criteria;
- multiple-testing count;
before opening returns.
