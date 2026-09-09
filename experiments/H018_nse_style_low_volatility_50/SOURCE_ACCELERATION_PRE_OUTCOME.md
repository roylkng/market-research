# H018 static-source acceleration freeze before first outcome

Status: **FROZEN BEFORE ANY H018-v1 SELECTION OR OUTCOME IS OPENED**

This note permits an acquisition-only acceleration for unresolved H018 calendar dates. It changes no H018-v1 research semantics, selection rule, score, universe rule, execution convention, benchmark identity, comparator, random seed, friction, or success gate.

## Rationale

The official-source probe run `34326782646` established that representative 2014, 2015 and 2016 daily index snapshots are available as stable static files and are byte-identical across the tested official NSE/Nifty archive hosts. The frozen H018 parser repair separately resolves the documented `CNX 500` to `Nifty 500` label change before 2015-11-09.

The existing checkpoint fetcher is intentionally conservative and may perform multiple retries per URL. That behavior protects against transient exchange-host failures but is unnecessarily slow for a large historical static-file range.

## Frozen acceleration rule

An acceleration job may restore the retained checkpoint corpus from run `34265875607` and operate only on dates that do not already have a complete H018 checkpoint.

For each unresolved date:

1. Request the exact frozen legacy NSE bhavcopy URL and exact frozen NSE daily index-snapshot URL.
2. The primary host is `archives.nseindia.com`. The only fallback host allowed is `nsearchives.nseindia.com`, using the identical path.
3. A source is successful only on HTTP 200 with non-empty bytes.
4. A date may be classified `NO_SESSION` only if both the bhavcopy and index resources return HTTP 404 on **both** official hosts.
5. A common-session checkpoint may be written only if both source bytes are available and pass the existing frozen parsers for the requested date exactly.
6. Exact bytes are retained content-addressed and their SHA-256/byte-size metadata are written using the existing H018 checkpoint format.
7. Any timeout, 403, 429, 5xx, redirect outside the two allowed hosts, parse error, one-sided source availability, or otherwise ambiguous response writes no completed checkpoint. Such dates remain unresolved for the conservative existing acquisition path.
8. Existing completed checkpoints are never overwritten by the acceleration job.

The acceleration job is source acquisition only. It must not import or execute H018 selection/evaluation functions and must not create `point-in-time-selections.json`, `challenge-summary.json`, or `selected.csv`.

## Promotion integrity

All accelerated checkpoints remain subject to the same exact-source SHA-256 verification before a future H018 challenge may use them. Acceleration therefore changes only wall-clock acquisition cost, not evidence or market semantics.
