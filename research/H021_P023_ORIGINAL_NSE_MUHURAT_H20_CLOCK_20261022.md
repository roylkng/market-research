# H021-P023: Source-Verified 8 November Muhurat Session Clock

**Audit date:** 22 October 2026 (before 8 November Muhurat session).
**No changes** to the original 9 October EPS revision signal, 12 October
next-open stock identities, 20/60-session horizons, and Nifty 500 benchmark.
**Returns/portfolio/live capital remain disabled.**

## The previously unresolved calendar fact is now published

Original H021-P006 used the immutable official NSE cash-market
2026 calendar (payload SHA-256
2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce).
It flagged **Sunday, 8 November 2026** as an unresolved Diwali Muhurat
special session, with provisional ordinary weekday-only H20 ending on
**9 November 2026**. The H021 original source contract correctly refused
to calculate a trading outcome under that uncertainty.

The official capital-market circular
**NSE/CMTR/76941**, circular 149/2026, issued **19 October 2026**,
provides the concrete Sunday trading schedule:

https://nsearchives.nseindia.com/content/circulars/CMTR76941.pdf

- Normal-market continuous trading begins **14:20 IST**.
- Non-closing-auction shares' regular market closes at **15:30 IST**.
- Closing-auction securities have an earlier continuous-market close
  at **15:15** and closing auction matching through **15:35 IST**.
- Final exchange trade modification cutoff **16:15 IST**.
- All executed Muhurat trades carry settlement obligations.

The same original circular was already retrieved and content-addressed
in the repository by the separate HG009-P004-A1 study on 20 October,
**before** the Sunday 8 November session. Exact original NSE PDF SHA-256:
ce94ee1c54d98eccdf3c30fa0673ae2b6a49ea4ed4a72fb83d826f4359f71d58.
HG009's independent signed circular receipt and validated amendment are
replayed byte-for-byte by this H021 adapter. HG009 itself already amended
its October 15 entry cohort's H20 endpoint to **12 November**.

## H021 corrected prospective sequence

H021's initial H021-P003 10-company decision remains fixed on 9 October,
with original official first entry on **12 October 2026**. Counting the
entry session as holding-session one:

1. Session 1 is Monday 12 October.
2. Session 19 is Friday 6 November.
3. **Session 20 is Sunday 8 November 2026, Muhurat trading.**

The H021-P006 provisional Nov9 result and original calendar are **retained**
for provenance. A separate P023 signed source-clock amendment, anchored
before 8 November, identifies only the verified calendar endpoint.

The actual stock and Nifty 500 original source reports for Sunday remain
future evidence. For conservative retrieval, no source should be claimed
before **16:15 IST** after the special session. Reported official close
prices of closing-auction versus non-closing-auction securities require
original NSE source and instrument classification checks. The source
announcement alone cannot supply a market close or an executable fill.

The **60-session primary H021 horizon remains blocked**: from 12 October,
only 56 official calendar sessions, including the special Sunday,
exist through the end of 2026. At least four additional sessions
require a new original **official NSE 2027** calendar; guessing 2027
January holiday patterns is unacceptable.

## Reproducibility and scientific integrity

Sources:

- Original unchanged H021-P003 intent plus its SHA-pinned Oct9
  comparison and original NSE calendar.
- Original signed HG009-P004-A1 source receipt and actual NSE
  two-page PDF SHA-256.
- Already independently calculated/signed HG009 November 8 Muhurat
  amendment with original Oct15/H5 retained and H20 Nov12.

Implementation:

- src/marketlab/h021_muhurat_amendment.py
- scripts/seal_h021_muhurat_clock.py
- tests/test_h021_muhurat_amendment.py
- .github/workflows/h021-p023-muhurat-calendar.yml

Run without fetching any future price:

    python scripts/seal_h021_muhurat_clock.py --require-20-calendar-date

Run tests:

    pytest -q tests/test_h021_muhurat_amendment.py

Permanent append-only artifact after CI-reviewed merge:

research/prospective/h021/amendments/h021-p023-nov08-calendar-v1.json

**This does not authorize an H021 20-session return, raw price-only
benchmark comparison, expected alpha, trade, position change, or capital.**
The VEDL dividend, actual security settlement, identity changes, company
corporate actions, potential CAS price basis, transaction costs,
future Sunday NSE files and all 2027 calendar gates remain separate.
