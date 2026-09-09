# H019 Accounting Ledger v1 Run 1 Result

Status: **IMPLEMENTATION FAILURE AFTER COHORT FREEZE**

Run: `34363988787`
Job: `102507884699`
Partial artifact: `h019-accounting-ledger-v1-34363988787`
Artifact ID: `10109147020`
Artifact SHA-256: `491d3a77d7bc63935db42d4672fca92638fbc14ad8628c47e6ddeb6e80755ba0`

This run is not a coverage pass or failure. It completed the frozen symbol sample and annual-report metadata selection, then aborted during report parsing because a malformed PDF structure triggered an uncaught `pypdf` `TypeError`.

No market price, return, benchmark return, portfolio, H019 feature weight, investment score, or live-capital outcome was opened.

## Frozen source evidence completed before the crash

The partial artifact is authoritative for the cohort and metadata selection and must be reused rather than regenerated.

- 2018 reporting population: 1,610
- 2020 reporting population: 1,613
- survivor-proxy population: 1,486
- exit-proxy population: 124
- new-proxy population: 127
- frozen sample: exactly 100 distinct symbols
  - SURVIVOR_PROXY: 50
  - EXIT_PROXY: 25
  - NEW_PROXY: 25
- annual-report API metadata success: 100/100 symbols
- usable annual-report metadata rows: 409
- metadata-frozen report records: 157
- symbols with two frozen report years: 76
- symbols with one frozen report year: 5
- symbols with zero eligible report years at the 2020-10-01 cutoff: 19
- symbols with at least one eligible report year: 81
- report records by lifecycle proxy:
  - SURVIVOR_PROXY: 100
  - EXIT_PROXY: 47
  - NEW_PROXY: 10
- frozen report years:
  - FY2019: 75
  - FY2018: 74
  - FY2017: 6
  - FY2020: 2
- latest accepted `available_at`: `2020-09-29T20:57:12+05:30`, before the frozen cutoff

## Frozen partial-artifact file hashes

- `frozen-symbol-sample.json`: `0b46d031d76ed3d7db3ff47a9aeabf8973e0cc017e429d0b5f0ccc703f12675a`
- `listing-manifest.json`: `164d5d84abcf4bc440487e5482cd7d02df738fb00bb95670795690208dd0bb31`
- `annual-report-api-manifest.json`: `f45be1b5c343a781f489379136f38dd39dcc4fe7ba2479a1a09e30da504659c7`
- `annual-report-metadata.json`: `e71bb11d7cb46a2970d5f8a9b10a2547ede09ccfea9305306120e245fab36b07`
- `metadata-frozen-report-selection.json`: `b61333133ee1c9191b524b058ebaacca989cef862a9063168928b6314d53586e`
- canonical JSON SHA-256 of the frozen 157-record selection: `8c61746c48efabc7bbeb54dd3dcf5f998042432edd34099fb8edd9ffbdca9cd1`

## Failure

The run progressed through metadata acquisition and into the fixed report loop, reaching roughly 120 report parses. One report then caused:

`TypeError: 'DictionaryObject' object cannot be converted to 'DictionaryObject'`

inside `pypdf` font-resource handling called by text extraction.

The ledger protocol already requires failed or non-machine-readable reports to fail closed without substitution. Aborting the entire 157-report audit on one parser exception was therefore an orchestration defect, not a reason to replace the report or change the frozen sample.

## Decision

Do not re-query the listing populations, do not re-sample symbols, and do not re-freeze annual-report metadata.

Resume from the exact partial artifact above. Reacquire exactly its 157 metadata-frozen report URLs. Convert report-level deterministic parser exceptions into explicit fail-closed report statuses and continue the remaining frozen reports. Keep H019 numeric parser v3 unchanged.