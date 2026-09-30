# AE001 D001 NSE Futures Source Discovery v1

Status: SOURCE DISCOVERY ONLY
Created: 2026-09-30
Live capital: DISABLED

## Objective

Verify the exact official NSE historical source and schema required for a future
stock-futures positioning alpha family before any model/outcome protocol is
frozen.

D001 does not compute stock returns, alpha metrics or portfolio results.

## Candidate source

NSE display name:

`F&O - UDiFF Common Bhavcopy Final (zip)`

Official derivatives report archive:

`https://www.nseindia.com/all-reports-derivatives`

Candidate direct archive convention, inferred from the already verified CM UDiFF
convention:

`https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`

## Discovery date

2026-09-25.

This date is used only to verify source/schema mechanics because the corresponding
cash-market source is already a frozen MarketLab reference session.

## Required discovery output

- HTTP/source success;
- exact URL;
- ZIP member count/name;
- CSV header;
- total row count;
- instrument-type counts;
- sample stock-futures row field names/types;
- whether open interest and previous open interest/change fields exist;
- expiry-date representation;
- underlying/symbol representation.

No outcome labels are opened.

## Next gate

Only after D001 succeeds may a separate derivatives-feature trial be frozen.
