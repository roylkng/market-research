# H021-P015: Independent Official 12 October Entry Source Replay

**Contract frozen on 12 October 2026 prior to completed NSE trading session.**
Purpose: catch malformed or relabelled NSE stock/index prices *even if an
original source-summary JSON hash was recomputed*. Does not trade or
calculate stock-selection performance.

## Why

P003 froze the first ten signals before the 12 October opening.
P011 preflight successfully verified the exact **9 October** prior-session
UDiFF and Nifty500 schema before the first entry. P004 will fetch the
new **12 October** session OHLC after 15:30 IST, with official raw source
bytes and SHA-256 receipts. P014 fixed an unrelated 12 October late
pre-entry no-op failure and made P004 Git writes race-tolerant.

P004's summary packet carries its own SHA. That proves the summary
was unchanged after its packet hash was calculated, **not** that a
reported stock opening price was actually present in the original
NSE market source. An independent second pass is needed.

## Independent replay

The P015 runner only operates if Git contains a previously source-complete
and successfully sealed first-entry P004 packet at:

    research/prospective/h021/entry-observations/2026-10-12-first-entry-v1.json

It will locate exactly the SHA-named **original** official market files:

    research/prospective/h021/entry-observations/raw/sha256/<UDIFF_SHA>.zip
    research/prospective/h021/entry-observations/raw/sha256/<INDEX_SHA>.csv

Recheck from original bytes, rather than trusting stored derived figures:

- the original two NSE URLs, raw SHA-256 and exact byte lengths;
- post-12 October **15:30 IST** source timestamps;
- original pre-open research intent, frozen source comparisons,
  100-name U001 member/ISIN identities and calendar ancestry;
- all **ten frozen primary names in original order** and exact EQ/ISIN;
- re-parse original stock open, high, low and close for each company;
- re-parse Nifty 500 **price index**, not TRI, on the exact date;
- compare *every* stored price and index value to the independently
  reparsed original market file, and reject any discrepancy;
- distinguish official opening price **proxy** from actually executable
  broker fill, order book depth or slippage.

The new SHA-sealed replay stores the original entry packet SHA, both
original market-source hashes, the ten reverified source bars and
Nifty 500 index-source bar, with no capital or future return.

## Trigger and failure modes

A workflow_run after the P004 "H021 first official entry source
observation" workflow, plus a nightly catch-up and manual dispatch,
performs source-only replay. GitHub's ordinary GITHUB_TOKEN-driven
pushes may not trigger downstream push events, which is why the
workflow uses workflow_run and a catch-up schedule.

Until the complete P004 source packet is committed, the P015 gate
returns WAITING_FOR_REAL_OFFICIAL_POST_CLOSE_SOURCES and does not
pretend any Oct12 OHLC prices exist.

Upon successful verification the runner anchors once, append-only:

    research/prospective/h021/entry-observations/replays/2026-10-12-source-raw-replay-v1.json

It refuses changed original records, re-parsing or Git overwrite
conflicts. Non-research Git updates may be rebased with a bounded
five-attempt push retry. An Actions artifact preserves the replay
if a Git race prevents publication. Data are never backdated.

## Explicit still-blocked scientific outcomes

- There was NO actual broker order/fill at the opening price.
- VEDL's already known original dividend announcement around
  14 October creates a cash entitlement/corporate-action issue;
  **actual hypothetical eligibility and total-return cashflows
  are NOT cleared by replay**.
- Additional dividends, splits, demergers, rights and stock identity
  changes require complete official source review for each horizon.
- The Nifty 500 source is a **price** index. Stock dividends and
  Nifty 500 total-return basis still require an independent protocol.
- Unresolved 8 November Muhurat timing and missing official
  2027 NSE sessions block 20/60-session outcome publication.
- Four independent prospective mature cohorts, costs and multiple
  testing gates remain obligatory. HG007 hidden-gem economics are a
  distinct research hypothesis.

The replay is not predictive validation or an alpha feature trial.
All investment recommendations and live capital remain prohibited.

## Local / CI rehearsal

Synthetic source regression tests only; do not fake real prices:

    pytest -q tests/test_h021_entry_replay.py

After the **real post-close P004 source packet is present**:

    python scripts/replay_h021_first_official_entry.py \
      --out /tmp/h021-oct12-independent-source-replay.json

The complete original file hashes and replay result can be
independently reproduced from the repository, including source SHA
verification that survives packet digest recomputation.
