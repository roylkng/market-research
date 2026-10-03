# H015 legacy Nifty index-date source audit

Recorded: 2026-09-08 before H015 point-in-time selections or outcomes were produced.

Status: **SOURCE-PARSER REPAIR ONLY. H015 SIGNAL/GATES UNCHANGED.**

The first H015 execution stopped during market acquisition, before `point-in-time-selections.json` existed. Three official Nifty index snapshot files were retained and parsed successfully as CSVs but did not match the requested session date under the normal `DD-MM-YYYY` interpretation:

- archive `ind_close_all_06042023.csv` contains `Index Date = 04-06-2023` on all 106 rows,
- archive `ind_close_all_10042023.csv` contains `Index Date = 04-10-2023` on all 106 rows,
- archive `ind_close_all_11042023.csv` contains `Index Date = 04-11-2023` on all 106 rows.

Each file contains exactly one `Nifty 500` row, and the archive filename itself encodes respectively 2023-04-06, 2023-04-10 and 2023-04-11. Interpreting the internal date token as `MM-DD-YYYY` yields exactly that source-file date for these three files.

The repair is therefore narrowly frozen as follows:

1. First use the repository's existing strict Nifty 500 parser.
2. Only if it fails to match the expected source session date, locate the unique `Nifty 500` row.
3. Interpret that row's `Index Date` as `MM-DD-YYYY` only as a fallback.
4. Accept the row only if the fallback date equals the independently known session date encoded by the retained archive URL/request.
5. Require finite positive Nifty 500 open and close values exactly as in the normal parser.
6. Otherwise fail closed.

This does not infer or interpolate any index value, does not alter the session calendar, and does not use H015 rankings or returns. The three affected source files were discovered before any H015 selection or outcome was opened.
