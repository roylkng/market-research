# AE001 D010 Protocol Amendment P1: Official Archive Resolution

Frozen: 2026-10-01
Status: FROZEN AFTER P0 SOURCE-DISCOVERY FAILURE, BEFORE P1 PROBE
Live capital: DISABLED

## P0 result

Frozen D010-P0 workflow run:

    36875456154

P0 report SHA-256:

    eee104e4c41a28170f20fbfdd4f0821a865ccef9404b69a6b0ada0e52b5a0363

P0 opened:

- zero return labels;
- zero predictive models;
- zero alpha outcomes.

Both source families failed because none of the frozen static URL candidates
resolved on all three probe dates.

This is classified as:

    SOURCE_LOCATION_DISCOVERY_FAILURE

It is NOT evidence that NSE did not publish the reports.

## New public source-location evidence

After P0 completed, independent public NSE downloader documentation/code exposed
the NSE archive route used for CM Short Selling:

    https://nsearchives.nseindia.com/archives/equities/shortSelling/
    shortselling_DDMMYYYY.csv

P1 may test this exact route on the original three frozen P0 sessions.

The P0 result remains immutable.

## Official NSE Daily Reports metadata discovery

NSE exposes the web JSON endpoint:

    https://www.nseindia.com/api/daily-reports

P1 uses this only as a discovery/metadata interface.

Frozen query keys:

- CM
- SLB
- SLBS

No other key may be added after the P1 run begins.

For every returned JSON object, P1 recursively records objects containing any of:

- fileKey
- filePath
- fileActlName
- displayName
- tradingDate

Candidate metadata objects are selected only when their combined text contains
case-insensitive terms relevant to:

### Short selling

- SHORT
- SELL

### SLB open positions

- SLB
- OPEN
- POSITION

Raw JSON bytes and SHA-256 are retained for every successful query key.

## P1 source questions

### CM Short Selling

Question 1:

Does the newly resolved static archive pattern return parser-valid CSV on all
three original frozen P0 probe sessions?

If yes, short selling may proceed to D010-P2 full historical coverage/identity
audit.

### SLB Daily Open Positions

Question 2:

Does official Daily Reports metadata identify a unique NSE file/download path for
the SLB daily open-position report?

P1 does NOT infer a historical SLB archive path unless the official metadata
itself makes the archive directory/filename convention explicit enough to form a
single deterministic date pattern.

If the metadata is insufficient, SLB remains source-location deferred and must
receive another source-only amendment.

## Metadata download safety

Any resolved download URL must use one of:

- www.nseindia.com
- nsearchives.nseindia.com
- archives.nseindia.com

No third-party data bytes are eligible.

## Scientific boundary

P1 remains source-only.

- no return labels;
- no model fit;
- no stock-ranking metric;
- no alpha promotion.

Historical archive availability still does not establish publication time.

Any future alpha trial needs a separately frozen prospective source-timing gate.

No live-capital implication.
