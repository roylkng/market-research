# SS002-P001 Append-Only Daily NSE Special-Situation Capture v1

Status: **FROZEN BEFORE FIRST P001 CAPTURE**  
Frozen: 2026-10-09  
No return outcomes, model inference, valuation, portfolio eligibility or live capital.

## Purpose

Move the passed SS002 special-situation source spine from the static
2026-04-01..2026-10-04 historical census to a durable daily surveillance feed.

SS002-P001 captures **every** NSE cash-market corporate announcement, preserving
all nonmatching announcements as well as category-hint candidates. The P2 taxonomy
is used *unchanged* as a coarse source-routing hint, not a fact of economic relevance.

## Frozen source inputs

1. Exact whole-market NSE corporate-announcement JSON, queried with
   `index=equities`, `from_date=D`, `to_date=D`.
2. Exact NSE `EQUITY_L.csv` security master captured at execution time.

Each source's original bytes and SHA-256 are retained as deterministic gzip
(mtime=0), with a SHA of the gzip and a path in the daily manifest.

NSE's `exchdisstime` is treated as exchange-published time, not local ingestion
time. An announcement must fall on day D in Asia/Kolkata under the existing
`normalize_announcement_payload` contract.

## Date and point-in-time rules

- Base completed historical census ends **2026-10-04**.
- First permitted P001 date is **2026-10-05**.
- A date may be acquired only after that India-local calendar date has ended.
- A run may attempt up to seven uncaptured consecutive dates.
- Captures for 2026-10-05 onward performed later are classified
  `HISTORICAL_BACKFILL_CAPTURED_LATER` when the current India date is more than
  one day past source date.
- A one-day-lag capture is `NEXT_DAY_SOURCE_CAPTURE`.
- For backfilled dates, the security master is expressly **as-of ingestion**,
  not reconstructed as-of the historical announcement date.
- Historical returns, prices, company valuations and subsequent outcomes are
  never used in classification.

## Immutable capture semantics

Each D has exactly one `YYYY-MM-DD-v1.json` capture manifest. Re-execution skips
an existing version without fetching and modifying it. Corrections or late-source
changes require a separately versioned, explicitly reasoned protocol; no
silent overwrite is permitted.

When a completed capture is missing a day, the next scheduled execution
attempts the oldest missing day first. A failed source day blocks any false
complete-range claim. Each successful captured day stays intact and auditable.

## Daily source product

- `announcement_count`, all original canonical announcement IDs and descriptions;
- category-hint candidate rows, with **all** P2 category labels retained;
- category counts, approved NSE attachment URLs or explicit absence;
- exact symbol-to-current-master match at capture time;
- current NSE ISIN and name when symbol matches;
- `ARCHIVAL_OR_UNMATCHED_AT_CAPTURE` otherwise;
- exact source hashes, URLs, timestamps, no result or capital claim.

A symbol-only matching EQ security is **not** verification of historical security
identity or evidence of current tradability. Corporate actions and share denominator
must be independently reconciled before price or market-cap calculations.

Every present current security remains in discovery, regardless of liquidity.
Neither a keyword nor an LLM label grants portfolio eligibility.

## Execution

A GitHub Actions workflow:

- runs on a daily UTC schedule corresponding to late morning in India;
- has a manual dispatcher for source-only replay;
- runs one bounded backfill batch per invocation;
- reuses the current official NSE client/session;
- commits source bytes/manifests atomically to the research repo, no force pushes;
- preserves exact event hashes and fails closed on schema/source error.

Workflows cannot execute LLM calls; this capture is an input to the separately
frozen SS002-L001 evidence-bound model contract.

## Feasibility and quality

Each day is `SOURCE_CAPTURE_PASSED` only when:

1. official whole-market announcement bytes were acquired;
2. official current EQ master bytes were acquired;
3. canonical rows have unique identities and valid source-day timestamps;
4. every candidate row has an existing canonical announcement ID;
5. all classified categories came from the frozen P2 taxonomy;
6. no invalid source host is labeled as approved;
7. raw/uncompressed/compressed hashes are deterministic and retained;
8. all outcome and portfolio flags remain false.

This is source acquisition, not a statistical alpha or predictive model.
