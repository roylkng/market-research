# HG007-P010 Official September INOXGREEN Ownership and Governance Source Gate

Frozen 10 October 2026 IST, before any INOXGREEN company-specific
return, probability or investment decision. Live capital disabled.

## Purpose

The HG007-P008/P009 historical capitalization correction proved that
403,959,665 fully diluted shares from the March 31 shareholder register
cannot be interpreted as current after the **September 29 QIP**.

The original September QIP issuer disclosure proves 419,602,518 basic
issued shares at allotment. It does NOT prove the **September 30
reported fully diluted** shares, nor the October 10 current outstanding
options or subsequent equity issuances.

A third-party ownership table has reported roughly 53.70% promoter
ownership and 4,900,000 pledged shares for September 2026, compared
with the previous source-backed June report at 56.12% ownership and a
reported zero pledge. These are **research leads, not officially
reconciled September filings**, until exact NSE exchange source data
support them. The percent decline alone is consistent with dilution
from new QIP shares, not proof the promoter sold shares.

## Authoritative original sources

Reuse the already-tested H023 official NSE shareholding discovery and
the existing HG005 / GF001 XBRL parsers:

- https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN
- The exact authorized NSE XBRL URL returned by the master record, not
  guessed URLs, inferred source names or third-party shareholding sites.

The collector records exact response bytes, original SHA-256,
actual scan timestamp, selected standard **2026-09-30** quarter,
latest legitimate NSE broadcast/revision ID available as of that scan,
original report/filing date and exact source XBRL URL.

The XBRL parsing requires:

- Exact issuer symbol INOXGREEN.
- Exact aggregate ShareholdingPattern_ContextI and **2026-09-30** period
  instant. June-period XBRL presented as September cannot pass.
- Exact unambiguous NumberOfFullyPaidUpEquityShares and
  NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities,
  in native shares, via the already-reviewed HG005 parser.
- The exact GF001 core promoter/public percentage and
  promoter encumbrance booleans, including pledged, NDU and other.
- September issued basic shares equal to 419,602,518 from the original
  29 September NSE QIP. Any conflict is retained as a source error,
  **never smoothed, padded or guessed**.

Only exact source-ready ownership snapshots are anchored permanently.
Blocked/unavailable/late September source states are retained as
GitHub Actions artifacts with actual capture dates. The collector
rechecks as a bounded October source watch, plus manual recovery.

Even a verified promoter pledge boolean does **not** prove precisely
4,900,000 pledged shares. That amount requires an independently verified
aggregate/shareholder context and security encumbrance XBRL count, or
the specific later official promoter pledge exchange announcement.

## Temporal and business limitations

- Filing quarter-end date does not equal its publication timestamp.
  A 30 September filing only becomes known at the official broadcast.
- A September quarter-end ownership report is not proof that no further
  options or shares changed by October 9 or October 10.
- No old March option balance can be substituted for a September
  official total.
- No promoter ownership change, pledge, security encumbrance or margin
  financing is inferred from third-party charts.
- No share-based EV, net debt, WWIL earnings, shareholder risk score or
  expected stock return is computed.

## Files and audit

- src/marketlab/hg007_sept_ownership.py
- scripts/acquire_hg007_sept_ownership.py
- tests/test_hg007_sept_ownership.py
- .github/workflows/hg007-inoxgreen-sept-ownership.yml
- Potential source record, only after successful official NSE retrieval:
  research/hg007/inoxgreen-sep2026-ownership/sept-2026-source-observation-v1.json

The QIP historical correction in HG007-P008 and all 28 source-backed
casework in HG007-P009 remain immutable. No stock buy/sell ranking,
unvalidated 4.9 million pledge adoption, completion probability or
live capital is authorized by this source-only protocol.
