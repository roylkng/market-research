# H021-P011: Original NSE Source Format Rehearsal Before First Open

**FROZEN BEFORE THE PLANNED 12 OCTOBER 2026 H021 OPEN.**
Scope is source-format readiness, NOT alpha, trade execution, or a source
for H021 price returns.

## Why

The first H021 comparison and ten-company membership were frozen after
9 October 2026, with an unexecuted planned 12 October 09:15 IST open.

An original **9 October NSE EQ UDiFF ZIP** was already collected by
SS002/HG007 and permanently retained in:
research/hg007/oct09-five-case-market/original/

Its verified SHA-256 is:
8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c
and size is 206,974 bytes.

The source was not created, edited or selected for H021-P011.
It is the exact official complete-market prior-session file, and
provides a fully realistic check of source schema/ISIN identity without
peeking at any 12 October or later market observation.

## Before-entry tests

P011 uses precisely the same instrument parsers and original frozen
9 October H021 first-entry intent as the post-close collector:

- all **10** original NSE EQ symbol/ISIN pairs must parse individually
  from the exact 9 October official 206,974-byte UDiFF ZIP;
- the source date must be precisely 9 October, not a later session;
- the Nifty 500 price index source is the exact NSE daily index CSV for
  9 October 2026, with index name/date/positive open/close validated;
- no alternate index, inferred prices, vendor API, ex-post symbol
  substitution or actual 12 October market observation is permitted.

The 9 October Nifty 500 file may be acquired directly from:
https://archives.nseindia.com/content/indices/ind_close_all_09102026.csv

A 403/429/401, 404, malformed CSV or schema mismatch remains an
explicit blocked source state. The preflight does not evade access
controls or treat synthetic fixtures as real. Only successful original
source bytes carry SHA-256 and can be permanently retained.

**No market open/close number appears in the preflight report.**
It records source identity and schema state only. This is not a
benchmark-excess return, cost estimate or fill simulation.

## Operational timing

The on-merge probe and one supplementary early-morning 12 October
GitHub Actions attempt are independently time-fenced before
12 October 2026 **03:45 UTC / 09:15 IST**.

No run at or after that open may retrospectively claim this was
pre-entry readiness evidence. An unavailable pre-open source remains
missing. The workflow records append-only attempts, and only a
fully real-stock+real-index-validated result is sealed.

The separate scheduled first-entry collector still acquires the
**actual 12 October** source after close at 15:30 IST. This rehearsal
is not its substitute and does not prove Monday liquidity, book
spread or tradable opening auction fills.

## Reproducibility

- Source validation:
  src/marketlab/h021_real_source_rehearsal.py
- Runner:
  scripts/rehearse_h021_original_market_sources.py
- Tests:
  tests/test_h021_real_source_rehearsal.py
- Workflow:
  .github/workflows/h021-original-market-source-preflight.yml

An offline test without fresh index acquisition:

    pytest -q tests/test_h021_real_source_rehearsal.py

The regression tests use the original exact archived 9 October stock
ZIP and a **clearly synthetic** index fixture to check parsing. Only
the live GitHub Actions rehearsal may claim real index-source
validation, and only if the actual NSE bytes were retrieved before
the future 12 October open.

All experiment selection, 20/60-session return evidence, corporate
actions, dividends, PF001 and live-capital permissions remain
unchanged and disabled.
