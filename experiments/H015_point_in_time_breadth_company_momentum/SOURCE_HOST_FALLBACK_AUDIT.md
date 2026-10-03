# H015 official NSE index archive host fallback audit

Recorded: 2026-09-08 before any H015 point-in-time selection or 2023-2024 outcome was produced.

Status: **SOURCE-ACQUISITION REPAIR ONLY. H015 SIGNAL AND GATES UNCHANGED.**

The fourth H015 execution completed static verification and market acquisition but stopped before `point-in-time-selections.json` because the primary `archives.nseindia.com` request for the June 19, 2024 daily index CSV failed during the bulk run and again during its serial retry. The official NSE EQ bhavcopy for that date was available.

A separate pre-outcome source probe then requested the exact same daily index file through both NSE archive hostnames:

- `https://archives.nseindia.com/content/indices/ind_close_all_19062024.csv`
- `https://nsearchives.nseindia.com/content/indices/ind_close_all_19062024.csv`

Both requests returned HTTP 200, `text/csv`, 12,046 bytes and the exact same SHA-256:

`852a79ad330bd3f2cf28b28bfbcd6ccfb0fa6c57beb07cfb9f06d52614b2561c`

Both files contain exactly one `Nifty 500` row for `19-06-2024` with:

- Open Index Value: `22406.3`
- Closing Index Value: `22224.9`

No H015 selection or outcome was available when this source repair was defined.

## Frozen fallback rule

For a date with a successfully retained official NSE equity bhavcopy:

1. request the normal daily index file from the repository's primary `archives.nseindia.com` URL,
2. perform the already frozen serial retry,
3. only if that exact file remains unavailable, request the identical `/content/indices/ind_close_all_DDMMYYYY.csv` path from `nsearchives.nseindia.com`,
4. retain the exact returned bytes and their requested/final URL,
5. apply the same strict Nifty 500 parser and the separately frozen source-date transposition repair,
6. if the alternate official host also fails, stop the replay.

The alternate host may not be used to change a valid primary-host value. No interpolation, ETF proxy, third-party index value or return-based substitution is permitted.
