# HG007-P010: Independent Official INOXGREEN Post-QIP Reg31 Source

**Scope:** issuer-level original NSE shareholding source discovery, not an
investment ranking, future alpha test, or final consolidated valuation.
Frozen 11 October 2026 IST.

## Why H023 could not answer this

The existing H023 source ledger correctly covers the frozen 100-name
nonfinancial U001 experiment. INOXGREEN belongs to HG002's distinct
outside-U001 hidden-gem universe. H023's 2,016 individual source
entries contain ZERO INOXGREEN observations. The 2,319-company
GF001/SS001 census established broad historical ownership coverage,
but its latest source vintage predated the September 29 2026 QIP.

The previously corrected HG007-P008 source-proven share structure:

- original issuer 29 September QIP: 18,110,473 new shares.
- original post-QIP issued basic shares: 419,602,518.
- March and June 2026 original Reg31: basic 401,492,045 and 2,467,620
  reported outstanding ESOP; March fully diluted 403,959,665.
- last independently audited market cap: **basic at Sep29 shares only**,
  1 Oct INR159 = INR 6,671.68 crore; 9 Oct INR128.92 =
  INR 5,409.52 crore.
- October as-of-date ESOP/convertible count not proved.
- reported third-party Sep29 ownership table suggests 4,900,000
  Inox Wind promoter shares pledged (vs original June 'No'),
  but is NOT a primary NSE-filed governance source.

The separate possible pledge increase must be verified from
actual NSE Reg31 source files. Do not automatically reject the stock
or assign a governance penalty based on third-party data alone.

## Source contract

The collector uses the existing approved H023 NSE endpoint acquisition
protocol for exactly one source URL and INOXGREEN symbol:

https://www.nseindia.com/api/corporate-share-holdings-master?index=equities&symbol=INOXGREEN

Its result is original JSON bytes plus retrieval timestamp and SHA256.
The parser checks standard quarter-end filings separately from special
share-capital allotment dates such as 29 September 2026.

It selects the latest published standard quarter source whose actual
original NSE broadcast timestamp is at or before the capture timestamp,
with duplicate final revisions blocked. It never retroactively inserts
new data as if visible on an earlier prospective experiment date.

When an approved original NSE shareholding XBRL link is available,
the collector retains original XML bytes plus SHA256 and independently
parses the existing exact XBRL aggregate concepts:

- NumberOfFullyPaidUpEquityShares
- NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities
- promoter/public aggregate category-specific percentages
- declared promoter pledge/NDU/other encumbrance booleans

For a valid original **30 September 2026** report, basic shares
must reconcile to the Sep29 allotment of 419,602,518. A difference
is an explicit SOURCE_CONFLICT, not a reason to overwrite the
original QIP filing.

If only the 30 June 2026 quarter is available, historical results
stay historical. Neither the June ESOP count nor the June 'No'
pledge declaration proves the September/October state. Unavailable,
blocked, duplicate, stale, or malformed official responses are
explicit missing-source states.

## Original evidence custody and operational controls

- Module: src/marketlab/hg007_shp_source.py
- Collector: scripts/acquire_hg007_inoxgreen_shp.py
- Tests: tests/test_hg007_shp_source.py
- Workflow: .github/workflows/hg007-inoxgreen-shp.yml
- Captured originals:
  research/hg007/inoxgreen-reg31-source/source/
- Append-only attempt receipts:
  research/hg007/inoxgreen-reg31-source/attempts/

The workflow performs a post-merge first original-source attempt and
bounded October follow-up attempts. It keeps every run's original
source receipts in a CI artifact even if NSE blocks the endpoint.
Only genuinely captured and verified original bytes are committed;
no 403 is silently reinterpreted as source confirmation.

The output distinguishes:
1. original published source as-of its *quarter-end report date*;
2. date/time it was originally broadcast and later acquired;
3. original QIP allotment chronology;
4. what still cannot be asserted about October 11 current shares,
   pledged share COUNT, intervening issues, adjusted enterprise value.

## Still blocked

- Complete current Reg31 as-of-Sep30 latest revision and any subsequent
  filings, including ESOP and other dilutive instruments.
- Original pledged-share QUANTITY and scope by promoter on Sep29.
  A boolean "pledge yes" is not a verified 4.9M share count.
- Share actions or new allotments after quarter-end through the
  candidate investment date.
- Actual post-QIP cash, external debt, Vibhav minority rights,
  WWIL target normalized operating FCF, and fully diluted parent
  enterprise-value-to-equity bridge.

The audit does not mutate original HG005, HG007-P008, H023 or other
original trial evidence. No stock expected returns, buy ranking,
portfolio eligibility or live capital is authorized.
