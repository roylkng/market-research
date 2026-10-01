# RM001 SC001 Previous-Session Size Source Pre-Open Timing v1

Status: FROZEN BEFORE FIRST RM001-SC001 PROBE
Frozen: 2026-10-01
Earliest observation date: 2026-10-02
Live capital: DISABLED

## Objective

Prospectively establish whether the official NSE CM MII Security File for the
most recent completed cash-market session is available, parseable and size-valid
before 08:30 IST on the following trading morning.

This is source-timing evidence only. It opens no stock-return outcomes and does
not alter RM001-v2 historical results.

## Motivation

RM001-D007 established the NSE Security File as a viable point-in-time historical
source for total-market-cap SIZE:

    total_market_cap_inr = official_close_price * IssdCptl

RM001-v2 P001 then showed SIZE improves risk decomposition modestly.

Prospective use remains disabled because same-session publication timing is not
yet verified.

For next-session portfolio construction, using completed session-D size
information by D+1 08:30 preserves causality and leaves 45 minutes before the
09:15 NSE open.

## Target session

At each probe, select the latest SC001 session satisfying:

- SC001 eligible_before_cutoff = true;
- target session date is strictly earlier than the local observation date.

This gives an exact completed-session market source and avoids calendar-day
assumptions across holidays/weekends.

## Frozen pre-open cutoff

08:30:00 Asia/Kolkata on the observation date.

Actual post-fetch timestamp is authoritative.

A target session is ready only when all are true:

1. Security File is downloadable;
2. gzip/parser contract passes;
3. exact target-session SC001 market bytes are available;
4. same-session symbol+ISIN join passes D007 total-size session gates;
5. capture completes no later than 08:30 IST.

## Official source

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_DDMMYYYY.csv.gz

Frozen parser/join semantics are exactly RM001-D007.

## Probe cadence

Weekday approximate IST:

- 06:30
- 07:00
- 07:30
- 08:00
- 08:15
- 08:25

GitHub scheduling delay is expected. Actual capture time controls eligibility.

Once a READY observation exists for a target session, later probes for that
target are no-ops.

## Evidence contract

Each attempt records:

- target session date;
- observation date;
- actual captured_at_utc;
- pre-open cutoff UTC;
- SC001 attempt SHA;
- SC001 market raw SHA;
- Security File URL/SHA/path;
- D007 parser and exact-join diagnostics;
- ready_before_preopen_cutoff;
- immutable attempt SHA.

Canonical ledger:

    research/prospective/rm001-sc001/source-ledger.json

Exact Security File bytes:

    research/prospective/rm001-sc001/raw/<target-session>/

## Promotion gate

RM001-v2 SIZE may not be treated as prospective-ready until at least three
distinct target sessions have READY observations no later than 08:30 IST.

Passing this source gate does not by itself authorize live capital or change any
portfolio policy.

## Non-goals

- no alpha model fitting;
- no return outcomes;
- no sector inference;
- no free-float-size inference;
- no automatic portfolio promotion;
- no live trading.
