# AE001 D010 Protocol Amendment P3B: Lagged Short-Selling Historical Audit

Frozen: 2026-10-01
Status: FROZEN AFTER P3A SOURCE-TIMING RESOLUTION, BEFORE P3B FULL AUDIT
Live capital: DISABLED

## Resolved source semantics

D010-P3A run 36884023631 established that the official file named for completed
session D contains CM short-selling trades from the previous completed NSE cash
session D-1.

Examples:

- shortselling_25092026.csv -> Trade Date 24-Sep-2026;
- shortselling_24092026.csv -> Trade Date 23-Sep-2026;
- shortselling_01092025.csv -> Trade Date 29-Aug-2025.

The P3 failure is therefore a timing-contract failure, not archive absence.

## P3B objective

Re-audit CM Short Selling over publication sessions:

    2025-09-01 through 2026-09-25

using the corrected lagged timing contract.

No SLB rerun is required. SLB already passed P3 with report SHA:

    e41e749a9d0514ffc4a01af6dd923d6c838e898320bf0e4f0e699bafc9d8dd27

## Trading-session contract

For each completed NSE publication session D:

1. identify D from official UDiFF;
2. identify the immediately previous completed NSE session D-1;
3. fetch shortselling_DDMMYYYY.csv using D;
4. require every parsed Trade Date in the file to equal D-1;
5. map Symbol Name to D-1 official UDiFF EQ symbol+ISIN;
6. require identity continuity into D using the same ISIN.

No symbol-only carry-forward is allowed.

## Historical denominator support

To evaluate the first publication session 2025-09-01, P3B may acquire UDiFF
sessions before the formal window only to identify the immediately preceding
session and its symbol+ISIN map.

Those support sessions are not source-coverage denominator sessions.

## Frozen promotion gates

CM Short Selling passes P3B only if:

- READY publication-session file coverage >= 95%;
- exactly one schema across READY files;
- every READY file has embedded Trade Date exactly equal to previous completed
  NSE session;
- trade-date UDiFF identity mapping >= 95% of source rows;
- mapped rows retaining same ISIN into publication session >= 95%;
- parser/data errors are never interpreted as zero short selling.

## Duplicate semantics

Every source row remains separate.

P3B records repeated symbols but does not aggregate them.

Any summation rule is frozen later under P4.

## Timing interpretation

P3B proves a one-session reporting lag in the historical archive naming/content
relationship.

It does NOT prove the intraday publication timestamp on session D.

A future prospective alpha trial still requires a live source-timing gate.

## Promotion

If P3B passes, D010 may promote both historically viable families to:

    AE001-D010-P4-FEATURE-SEMANTICS

No return labels or predictive models are opened under P3B.

No live-capital implication.
