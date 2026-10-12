# H021-P020: Delayed NSE Daily Source Publication, Bounded Recovery

Frozen change prepared on 12 October 2026 IST, after verified H021-P019
entry-session source collection and before the first subsequent NSE session
on 13 October 2026.

**Classification: source-transport reliability only. No new alpha trial,
signal change, revised stock selection, outcome, or capital authorization.**

## What failed on the first real H021 entry

The frozen original 9 October H021 top-ten research selection received ten
official 12 October EQ/ISIN opening-price observations. The *original*
first attempt at 17:33 IST received HTTP404 NOT_PUBLISHED for the 12 October
Nifty 500 index daily CSV. It was only possible to obtain and independently
verify the official original Nifty 500 price-index CSV later that evening,
with true later acquisition timestamps.

See:
- research/H021_P018_OCT12_OFFICIAL_NIFTY500_SOURCE_RECOVERY_2026_10_12.md
- research/H021_P019_FIRST_FULL_NSE_ENTRY_SOURCE_RECONCILIATION_2026_10_12.md

That is a **market-source publication latency**, not a reason to assume
the official index value at the earlier source timestamp or substitute a
different benchmark.

## Practical risk before 13 October

P008's daily post-close source collector had only 18:15 and 19:15 IST
scheduled checks. Each NSE session received at most three automatic
capture attempts; when the official index CSV appeared too late, the
session could become permanently SOURCE_UNRESOLVED_AFTER_BOUNDED_RETRIES,
even if original-source values were later independently available.

That would bias outcome measurement toward sessions with early publisher
availability, and could leave the prospective holding-price history
unusable even where original data were eventually published.

## Exact P020 operational amendment

- Retain normal **three** bounded NSE source attempts. Add two late
  source-publication checks at **21:45 and 22:45 IST** on weekdays.
  GitHub Actions may start scheduled runs later than the nominal minute.
- The resolver may perform **at most two additional delayed-source
  recovery attempts** over the next seven calendar days, but only when
  *the original Git-retained attempts* prove that the **same-session**
  NSE equity UDiFF or Nifty 500 index original report was **HTTP404
  NOT_PUBLISHED**, and no prior receipt shows access denial, network
  failure, or unexplained data/identity inconsistency.
- Delayed retries must start **on a later IST calendar date** than the
  latest previous attempt. At most one retry occurs per IST day.
- **Fresh completed sessions have priority** over old delayed
  publication attempts. This prevents a previously unavailable CSV
  from starving subsequent prospective observations.
- The original source URLs remain unchanged. No substitute vendor,
  alternate market date, proxy index, 3xx redirect, anti-bot bypass,
  quote-derived opening price, missing-data interpolation, trade fill
  or paper-fund order is allowed.
- All original attempts and raw files remain append-only, with their
  true source UTC acquisition times. A later successful retrieval must
  be attached to its actual original NSE session, **never backdated**.
- Recovery does not apply to a source that was already transport
  successful but failed first-cohort EQ/ISIN reconciliation: this
  is an identity/measurement issue, not publication latency.
- Once the two additional retries or seven-day window are exhausted,
  leave a visible source gap requiring independent manual investigation.

## Reproducibility

- scripts/resolve_h021_daily_session.py
- .github/workflows/h021-daily-official-prices.yml
- tests/test_h021_delayed_source_recovery.py

Original operations remain exercised by:
tests/test_h021_daily_prices.py.

Manual read-only readiness command:

    python scripts/resolve_h021_daily_session.py \
      --calendar research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json \
      --observations-dir research/prospective/h021/daily-prices \
      --allow-delayed-publication-recovery

The command reports the exact ISO session date and a distinction between
NORMAL_AFTER_COMPLETED_EXCHANGE_CLOSE and
DELAYED_ORIGINAL_NSE_404_RECOVERY_NOT_BACKFILL.

**No 20/60-session outcome is opened by this work**. The unresolved
8 November Muhurat session, 2027 calendar source, confirmed VEDL
dividend entitlement and share adjustment, stock total-return treatment
versus price-index benchmark, executable orders and transaction costs
remain independent gates.

There is no capital authorization or retrospective stock deletion.
