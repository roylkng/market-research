# H019 Accounting Ledger v1 Resume Protocol

Status: **FROZEN BEFORE RESUMED REPORT EVIDENCE**

Parent run: `34363988787`
Parent partial artifact: `h019-accounting-ledger-v1-34363988787`
Parent artifact ID: `10109147020`
Parent artifact SHA-256: `491d3a77d7bc63935db42d4672fca92638fbc14ad8628c47e6ddeb6e80755ba0`

The parent run already froze the 100-symbol cohort and the 157 metadata-selected annual-report records. This resume protocol must reuse those exact files and may not regenerate either selection.

## Mandatory parent verification

Before any report is reacquired, verify the GitHub artifact digest and these exact files:

- `frozen-symbol-sample.json`: `0b46d031d76ed3d7db3ff47a9aeabf8973e0cc017e429d0b5f0ccc703f12675a`
- `listing-manifest.json`: `164d5d84abcf4bc440487e5482cd7d02df738fb00bb95670795690208dd0bb31`
- `annual-report-api-manifest.json`: `f45be1b5c343a781f489379136f38dd39dcc4fe7ba2479a1a09e30da504659c7`
- `annual-report-metadata.json`: `e71bb11d7cb46a2970d5f8a9b10a2547ede09ccfea9305306120e245fab36b07`
- `metadata-frozen-report-selection.json`: `b61333133ee1c9191b524b058ebaacca989cef862a9063168928b6314d53586e`
- canonical JSON SHA-256 of the 157-record selection: `8c61746c48efabc7bbeb54dd3dcf5f998042432edd34099fb8edd9ffbdca9cd1`

Also verify:

- exactly 100 distinct frozen symbols = 50 survivor proxy + 25 exit proxy + 25 new proxy;
- 100 annual-report API manifest rows and all are `OK`;
- exactly 157 metadata-frozen report records;
- exactly 81 symbols have at least one selected report record;
- 76 symbols have two report records, 5 have one, 19 have zero;
- no symbol has more than two report records;
- every selected record has `available_at <= 2020-10-01T23:59:59+05:30`.

A verification failure terminates the resume before report evidence.

## Resume execution

The resumed builder must:

1. read the frozen sample, API metadata, and 157 report records from the parent artifact only;
2. make no listing-population request;
3. make no annual-report API metadata request;
4. reacquire exactly the 157 selected report URLs from approved NSE archive hosts;
5. make no fallback or replacement when download, container extraction, PDF text extraction, or accounting parsing fails;
6. use H019 numeric extraction parser v3 unchanged;
7. retain and hash every successfully reacquired report container and PDF;
8. build observations, the as-of resolver, and coverage from all successful fixed-set parses after every report has been attempted.

## Report-level fail-closed rule

The parent run exposed an orchestration defect: one malformed PDF could abort the entire audit.

In the resume, a report may be marked `PARSER_FAILED_CLOSED` when the unchanged v3 parser raises a deterministic document/parsing exception such as:

- `KeyError`
- `OSError`
- `TypeError`
- `ValueError`
- `pypdf.errors.PdfReadError`

The record must retain:

- symbol and lifecycle group;
- report year and URL;
- `available_at`;
- report/PDF hashes when available;
- exception type and bounded error string;
- explicit `fallback_used: false`.

The resume then continues to the next already-frozen report. It may not use OCR, another report year, another company, a manual page override, or parser tuning.

Unexpected process-level exceptions remain fatal rather than being swallowed broadly.

## Parser immutability

Before report execution, hash `scripts/h019_numeric_extraction_audit_v3.py`. Verify the same hash after the run and require an empty Git diff for that file.

No parser change is authorized by this resume protocol.

## Evidence lineage

The resumed artifact must include:

- a parent-artifact-lineage record containing the parent run, artifact ID, artifact digest, and verified frozen-file hashes;
- copies of the five frozen parent JSON evidence files;
- the new 157-attempt report source manifest;
- report extraction statuses including fail-closed records;
- accounting observations;
- as-of resolved facts;
- ambiguity records;
- per-symbol history coverage;
- final ledger coverage summary.

The raw parent API/listing sources may be referenced by their content hashes in the parent artifact. New report sources must be retained in the resumed artifact.

## Integrity gates

Keep the original ledger v1 integrity gates and add:

- parent GitHub artifact digest verified;
- parent frozen-file hashes verified;
- no listing or annual-report metadata API reacquisition;
- all 157 frozen report records attempted exactly once;
- zero fallback/replacement reports;
- fail-closed parser exceptions do not abort the fixed-set run;
- H019 parser v3 unchanged.

There is still no fitted minimum coverage threshold. Measured coverage is evidence for the later H019 data-eligibility decision.

## Prohibited data

The resumed workflow must not access or calculate:

- security prices or bhavcopy data;
- benchmark/index returns;
- future returns;
- portfolio selections or portfolio returns;
- H019 feature weights or investment score;
- live-capital recommendations.

## Decision rule

If all integrity gates pass, accept the resumed ledger architecture and use its measured coverage as the source-side evidence for the next frozen H019 data-eligibility contract.

This does not authorize opening market outcomes or choosing H019 feature weights.