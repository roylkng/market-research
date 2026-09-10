# H021 expectation-revision source feasibility plan

Status: **FROZEN BEFORE H021 RETURN OUTCOMES**
Date: 2026-09-11
Live capital: disabled

## Purpose

Determine whether Indian company-level consensus revisions can be captured with enough point-in-time integrity to support H021. This phase evaluates sources, timestamps and coverage only. It must not inspect subsequent security returns to select a source.

## Source candidates

### A. Trendlyne Forecaster / revision estimates

Public documentation states that Forecaster aggregates analyst estimates for roughly 900 companies and exposes quarterly/annual EPS and revenue estimates. Revision estimates cover windows from 7 to 90 days, and current/historical estimates are described as available.

Documentation:
- https://help.trendlyne.com/support/solutions/articles/84000383175-what-are-forecaster-or-analyst-estimates-
- https://help.trendlyne.com/support/solutions/articles/84000385840-what-are-revision-estimates-
- https://trendlyne.com/equity/consensus-estimates/what-is/modal/

Feasibility questions:

- Can observations be accessed reproducibly without violating authentication/licensing restrictions?
- Does the accessible record contain the actual historical consensus value and timestamp, or only a current calculation labelled as a historical change?
- Can analyst count and fiscal-period identity be retained?
- Can coverage be enumerated rather than discovered by successful query only?

No automated dependency on Trendlyne is allowed until these are answered.

### B. NSE Corporate Performance Review

NSE quarterly earnings reviews publish aggregate and sector-level consensus-revision analyses using LSEG/IBES data. This is high-quality external evidence that revisions are economically relevant in India, but it does not by itself provide a reproducible company-level free dataset.

Reference hub:
- https://www.nseindia.com/static/research/market-reports

Use: macro/sector regime context and methodology validation only unless a company-level licensed dataset becomes available.

### C. Licensed institutional source

LSEG/IBES, Bloomberg, FactSet, Capital IQ or another licensed source would be preferred for historical company-level revisions if available to the project. No such entitlement is assumed.

### D. Prospective self-capture fallback

If no legitimate historical company-level revision source is reproducibly available, build a prospective ledger from the first capture date.

Every capture must contain:

- capture timestamp UTC and Asia/Kolkata date
- source and retrieval URL/identifier
- symbol/company identity
- fiscal period
- consensus values and analyst counts
- raw response/page hash where retention is permitted
- explicit fetch/error state for every frozen symbol

The initial universe must be frozen independently of whether the provider returns data. Missing coverage remains missing.

## Feasibility cohort

Use a deterministic cross-section before source calls. Prefer the existing frozen U001 panel plus a separate smaller/mid-cap coverage stress sample if the source supports them.

Do not substitute another company when one has no analyst coverage. Coverage failure is part of the result.

## Pass criteria

Stage A source feasibility passes only if:

1. source terms/access permit reproducible research use;
2. stable security identity can be mapped to NSE symbols;
3. fiscal estimate periods are unambiguous;
4. observation/revision timestamps cannot move backward after retrieval;
5. at least current consensus snapshots can be captured deterministically across the frozen cohort;
6. missing/no-coverage cases are explicit;
7. no subsequent returns are used in choosing the source or coverage rule.

Historical backtesting additionally requires actual past snapshots or an equivalent reconstruction whose availability timestamps are independently verifiable. A current page displaying '30-day revision' is insufficient unless the underlying prior observation can be established point-in-time.

## Output

Produce a source-audit report with:

- source/access decision
- field schema
- covered/blocked/missing counts
- analyst-count distribution
- sector and market-cap coverage
- historical-depth evidence
- timestamp semantics
- retention/hash semantics
- whether H021 may proceed as historical + prospective or prospective-only

No stock ranking, price target, H020 state or future return may appear in the Stage A report.
