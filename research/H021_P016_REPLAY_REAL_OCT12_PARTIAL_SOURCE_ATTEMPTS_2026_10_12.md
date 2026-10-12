# H021-P016: Independent Replay of Original 12 October Source Attempts

Status: **original-source partial/full evidence retention, no performance**.
Protocol added on 12 October 2026 after the market close. The first
H021 selection and intended entry were frozen on 9 October; this change
does not revise either one.

## Original first real capture

The first postclose P004 acquisition was run by GitHub Actions on
12 October 2026 at approximately **17:33 IST** (run 38246531921,
attempt 1). It retained the exact NSE CM UDiFF equity bhavcopy:

- Official source URL:
  https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261012_F_0000.csv.zip
- HTTP status 200, original ZIP 207,055 bytes.
- SHA-256: 818f673b3cdb96ae8ec4e466c7c4fd3a28d035482173a675dd24f9437a3ecd99.
- All **ten** immutable October H021 symbol/ISIN matched EQ rows parsed,
  including valid observed open/high/low/close.
- Original attempted complete packet SHA:
  c314c0f001476f9ff221ca5055fb6b185702f862d4a455c5f0bb0e2f151dacbd.

The **official Nifty 500 index CSV returned HTTP 404** for that
particular initial attempt. We do not infer that it never publishes
later, nor treat a third-party index screenshot as an official receipt.
P004 correctly marked the first attempt
PARTIAL_OR_BLOCKED_SOURCE_OBSERVATION.

Original source evidence:
research/prospective/h021/entry-observations/attempts/38246531921-1.json

The original NSE stock ZIP remains under
research/prospective/h021/entry-observations/raw/sha256/.

## Recovery gap addressed

The original P004 collector stores the SHA-pinned stock source
bytes and original attempt receipt even when the index isn't ready,
but only publishes the canonical
2026-10-12-first-entry-v1.json upon verifying **both** stock and
index reports. The already existing H021-P015 independent source
replay also intentionally requires that canonical complete packet
and both raw originals.

P016 does not weaken either gate. Instead, it independently
**reconstructs every original attempted P004 source packet** from
the exact SHA-checked bytes and receipts, including the first
10-stock-plus-missing-index source observation.

Each reconstructive test verifies the reproduced packet SHA-256
matches the *original* Git-sealed P004 attempt. The independently
reparsed stock prices cannot be invented or edited without breaking
the retained first-attempt digest.

P016's independent per-attempt output lives under:

research/prospective/h021/entry-observations/reconstructed-attempts/

A source-incomplete attempt remains incomplete and NEVER substitutes
for the canonical first-entry full packet, the P015 full replay, or
a completed Nifty 500 price-index benchmark.

The custom workflow runs once when the P016 source-replay contract
is merged into main, again after any later first-entry source
attempt is recorded, and has an end-of-day catch-up schedule.
The original attempt files, source bytes and derived replay packets
are never overwritten. Any concurrent source/contract mutation
fails rather than changing research outcomes silently.

## Still blocked

- Canonical H021 first complete source observation requires
  verified official Nifty 500 price-index source bytes.
- The original first open is a historical official OHLC **proxy**,
  not actual 09:15 auction execution, liquidity or order fill.
- Dividends, raw versus TRI benchmark treatment, corporate actions,
  Muhurat trading and 2027 official calendar remain independent gates.
- No 20/60-session future investment return, gain or loss is opened.
- No company selection, weights, expected return, trading or
  live capital is authorized.

Reproduce the original source attempt:

    python scripts/replay_h021_entry_attempts.py

Run the targeted regression:

    pytest -q tests/test_h021_entry_attempt_replay.py

All original-source and no-return flags remain false. This is
an **evidence-custody** improvement, not an investment edge.
