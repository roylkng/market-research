# RM001-v3 Prospective Risk-State Protocol v1

Status: FROZEN BEFORE FIRST PROSPECTIVE RM001-v3 STATE
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Prospectively seal an RM001-v3 risk state for next-session portfolio
construction only after the RM001-v2 SIZE source-timing gate has independently
passed.

This protocol opens no alpha or return outcome.

## Activation gate

Prospective RM001-v3 remains disabled until:

    research/prospective/rm001-sc001/readiness-summary.json

reports:

    prospective_size_source_timing_ready = true

under the frozen RM001-SC001 rule of at least three distinct READY target
sessions captured no later than 08:30 IST.

The first two READY size sessions are source-timing evidence only. They are not
backfilled into prospective RM001-v3.

When readiness first becomes true, the only eligible RM001-v3 target is the
latest READY RM001-SC001 target session at that time.

Thereafter, only a newly observed latest READY target may create a state.

## Timing

Target session:

    D = latest READY RM001-SC001 target session

Observation date:

    D+1 local observation date recorded by RM001-SC001

The RM001-v3 state must be completely built and sealed no later than:

    09:05:00 Asia/Kolkata

on the RM001-SC001 observation date.

Actual post-computation seal timestamp is authoritative.

A late computation is permanently excluded for that target and may not be
backfilled.

## Current-session source binding

The exact target-D sources are mandatory:

1. SC001 market UDiFF bytes from the exact eligible SC001 attempt referenced by
   RM001-SC001;
2. RM001-SC001 Security File bytes from the exact READY size-timing attempt.

Their SHA-256 values and attempt hashes are persisted in the risk-state ledger.

The target-D Security File may not be re-fetched and silently substituted.

## Historical support

All support sessions strictly before D may be reconstructed during D+1 pre-open
because their publication precedes the target decision.

Frozen support acquisition:

- market/support start: D minus 420 calendar days;
- support end: D;
- minimum completed market sessions: 200;
- target D UDiFF is overridden with the exact SC001 bytes;
- target D Security File is overridden with the exact RM001-SC001 bytes;
- prior Security Files are official NSE historical archives;
- corporate-action coverage spans the full support panel.

The reconstructed target-D market/security joins must pass their original
AE001/RM001-D007 contracts.

## Risk construction

Build exactly:

1. AE001 historical price/volume features;
2. corporate-action-safe AE001 feature panel;
3. RM001-v2 PIT SIZE panel;
4. RM001-v2 exposure panel;
5. RM001-v2 realized factor/residual history;
6. RM001-v2 risk state as of D;
7. RM001-v3 risk state from the exact v2 state/history.

RM001-v3 parameters remain exactly frozen by:

- RM001_RISK_MODEL_V3.md;
- RM001_V3_PROTOCOL_AMENDMENT_P1_MATCH_PARENT_CLOCK.md.

No prospective refit or parameter selection occurs.

## Canonical evidence

Ledger:

    research/prospective/rm001-v3/risk-ledger.json

States:

    research/prospective/rm001-v3/states/<D>-v1.json.gz

Each ledger row binds:

- target session;
- observation date;
- RM001-SC001 attempt hash;
- SC001 attempt hash;
- exact current market SHA;
- exact current Security File SHA;
- v2 exposure/history/risk hashes;
- v3 risk-state hash;
- support panel hashes;
- sealed_at_utc;
- state artifact path/hash.

## Use boundary

A sealed prospective RM001-v3 state may be consumed only by a separately frozen
prospective portfolio protocol.

This protocol alone does not authorize:

- live capital;
- portfolio changes;
- alpha promotion;
- retrospective use of missed states.

## Non-goals

- no return outcomes;
- no alpha outcomes;
- no sector inference;
- no live trading;
- no backfill;
- no source-timing reinterpretation.
