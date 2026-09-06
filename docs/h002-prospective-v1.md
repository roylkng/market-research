# H002-D prospective cohort runner v1

## Objective

H002-D turns the already-frozen FY27-Q2 expectation panel into an automatic, reconstructable prospective experiment. It does not change H002-R001, H002-X001, U001, or any signal threshold.

The canonical operational rule is `H002-D001` in `registry/h002_runner_rule.yaml`.

Canonical runner-rule SHA-256:

`fdf174f2a0e848356e29cff3ba3fdc8f7f674836a77c4ef6065e5ca72360d238`

## Frozen first-event rule

For each of the 100 U001 members, the runner looks only for the target period ending `2026-09-30` and the accounting basis already frozen in that company's expectation record.

If multiple official NSE Integrated Filing records exist, the economically relevant event is the **earliest official publication** for that symbol, target period and frozen accounting basis. Later revisions are retained as evidence but never create a second signal or paper position.

This prevents revision hindsight from changing the result that would have been observable after the first filing.

## Expectation evidence

The runner consumes only the externally anchored bundle at:

`research/prospective/preparation/FY27-Q2-2026-09-06/expectation-bundle.json`

Expected bundle SHA-256:

`33ecb6496f02adc9d856aeeeee1e624df83e03d9e00a204c0c6ace26ee06b3b3`

The companion `run-metadata.json` must attest the same bundle and manifest. The anchor, manifest freeze and individual expectation capture must all predate an actual filing before that expectation may be used.

The frozen panel contains 98 numeric `READY` expectations and two terminal pre-filing `NO_SIGNAL` records, ADANIENT and LTM. Those two remain in the cohort denominator.

## Market-data sources

The historical NSE JSON endpoints were live-probed from GitHub Actions on 6 September 2026. They returned an NSE anti-bot HTML document with HTTP 200 and are therefore not used.

H002-D instead uses exact official report archives:

- Stock open/close: **CM-UDiFF Common Bhavcopy Final** ZIP.
- Benchmark open/close: **Indices Daily Snapshot** CSV.
- Session holidays: **NSE trading holiday master** exact JSON bytes.

These source shapes were measured against 20-Aug-2026 and 04-Sep-2026 files before the parser contract was written. The hosted contract probes were runs `34045633552` and `34045749836`; the second run verified both UDiFF and index snapshot headers and exact daily archive access.

No nearby close, adjusted web chart, OHLC inference or alternate data vendor is substituted if an official archive is unavailable.

## Calendar

Execution still consumes an explicit, versioned `TradingCalendar`. The calendar snapshot builder turns the exact CM holiday master into a committed session list using the regular NSE cash-market 09:15-15:30 Asia/Kolkata session.

Special sessions are never guessed. The 2026 holiday master marks 8-Nov-2026 `Diwali Laxmi Pujan*`. Until exact Muhurat session times are explicitly registered, any event whose reference or 20-session execution window depends on that date is held as `CALENDAR_PENDING`, rather than receiving a potentially wrong session count.

## Append-only observation ledger

Each company/event has a stable observation id and an append-only chain of state snapshots. Snapshots are SHA-256 addressed and parent-linked. Repeating an identical state is idempotent.

Typical states are:

- `EVENT_CAPTURED`
- `CALENDAR_PENDING`
- `PRICE_REFERENCE_PENDING`
- `SIGNAL_SCORED`
- `PENDING`
- `SKIPPED`
- `UNRESOLVED_EXIT`
- `COMPLETED`
- `ERROR`

Exact source hashes are retained separately and referenced by snapshots.

## Evaluation

Periodic reports read only the latest state of each observation.

Return statistics use **COMPLETED positions only**. PENDING, skipped, unresolved and error states remain visible in denominator/status counts but cannot leak partial future returns into the statistics.

Reports include raw and Nifty-50-relative summary statistics, benchmark hit rate, a deterministic bootstrap confidence interval when there is enough data, winner concentration, frozen 0/25/50-bps cost sensitivity, pre-registered signal-bucket summaries and the Nifty 200 Momentum 30 comparison.

MAE/MFE is explicitly `NOT_CAPTURED_V1`; H002-D does not fabricate an intraday path from daily OHLC.

All reports state `paper_only: true` and `live_capital_allowed: false`.

## Active window

The first runner is active from `2026-10-01` through `2027-01-31`. Running outside that window must not manufacture observations.

A change to event selection, target period, market-data source, execution semantics, or evaluation inclusion rule requires a new operational rule version and can apply only to future observations.
