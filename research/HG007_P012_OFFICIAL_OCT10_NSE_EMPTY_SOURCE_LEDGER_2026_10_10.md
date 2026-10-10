# HG007-P012: Official Oct 10 Shareholding-Master Empty Source Proof

Research source capture **10 October 2026 13:28:32 UTC**.
This is an original-response custody and research-risk disclosure, NOT
evidence that a September issuer filing does not exist.

## Exact original source

In GitHub Action run 38055817025, the official NSE issuer-specific
shareholding-master endpoint returned HTTP 200 and **33 bytes**:

    {"data":[],"msg":"no data found"}

This original string is archived unchanged, with SHA-256:

    d08611f20f7e28174a42e3f68099de1aecd58417493ef33f17041aa179d4cf44

The exact source is:

https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN

The previous P010 source probe originally treated the object as an
unsupported envelope. P011 supported explicit data-array envelopes
and captured the exact original bytes plus original keys and timestamp.
P012 **correctly names** the result:

    NSE_MASTER_EXPLICITLY_EMPTY_FOR_THIS_ISSUER_REQUEST

An HTTP 200 with zero data records from one request is **not
evidence of the nonexistence of an exchange filing** at BSE,
a special capital-restructuring venue, the issuer website, or
a different official API. It is also not a certification of no
promoter encumbrance. It never becomes a successful source row.

## What is independently supported

**Issuer original 30 June 2026 Reg 31**:

https://www.inoxgreen.com/PDF/SHP_30JUNE2026R.html

- 401,492,045 ordinary basic shares.
- 2,467,620 reported outstanding ESOP shares.
- 225,317,291 promoter and promoter-group equity shares.
- promoter pledge disclosure: NO as of that date.
- promoter ownership: 56.12%.

**Original verified September 29 QIP**:

- 18,110,473 equity shares issued.
- issued basic count increased to 419,602,518.
- if promoter shares did not change, arithmetic promoter fraction
  is 53.6978%, consistent with secondary 53.70%.

The **unchanged promoter share count is only a conditional
mechanical reconciliation** until a post-QIP original ownership
filing confirms it. No net QIP cash benefit is assumed.

**Secondary source conflict still not confirmed by an original**:

https://trendlyne.com/equity/share-holding/1127763/INOXGREEN/latest/inox-green-energy-services-ltd/

- reports a source dated 29 September 2026;
- lists the same 225,317,291 promoter shares and 53.70% promoter
  ownership, consistent with issuance dilution;
- reports 4,900,000 newly pledged shares, which contradicts
  the June original's previous no-pledge date, but no matching
  original September Reg 31 or promoter SAST documentation was
  obtained by this run.

The potential promoter pledge must remain:
**UNKNOWN_PENDING_ORIGINAL_FILING**, not FALSE or TRUE.

## Reproducible programmatic evidence

- Exact 33-byte original response:
  research/hg007/inoxgreen-post-qip-ownership/2026-10-10-original-nse-master-empty.json
- Source guard and QIP relationship:
  src/marketlab/hg007_ownership_gap.py
- CLI: scripts/audit_hg007_nse_empty_source.py
- Tests: tests/test_hg007_ownership_gap.py
  and tests/test_hg007_ownership_source.py

Run with no remote market-data call:

    python scripts/audit_hg007_nse_empty_source.py \
      --out /tmp/hg007-inoxgreen-source-gap.json

Both original response and prior post-QIP market-cap report are pinned
by SHA-256/Git-blob identity. Tests reject altered source bytes, changed
allotment math, and accidental promotion of third-party pledge claims.

The existing original NSE master/XBRL workflow continues dated-source
searches automatically through October, without bypassing HTTP or
treating an empty response as a valid current governance record.

## Next high-priority original-source avenue

- BSE Reg 31 filing/XBRL for the 29 September special allotment
  or the 30 September standard quarter. Verify issuer ISIN and
  page XBRL source hash, promoter name and pledged share fields.
- The next revised issuer investor-relations shareholding report,
  which is currently published only through June in the inspected
  issuer site's original archive.
- Promoter Inox Wind's Regulation 29/31/31(1)/(2)/(3) encumbrance
  disclosures and exact trade/pledge date if they exist.
- Current post-QIP ESOP, warrant and convertible balance, plus any
  new stock allotments. No derived FD or enterprise value permitted
  without original as-of evidence.

Nothing here validates a company-specific completion probability,
equity expected return, stock target, stock selection change, or
live-capital authorization.
