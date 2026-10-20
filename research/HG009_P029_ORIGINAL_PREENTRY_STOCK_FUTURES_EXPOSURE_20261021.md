# HG009 P029: timestamped October 14 NSE stock-futures exposure

**Source session:** October 14, 2026. **First observed UTC:** October 14, 2026 at 15:42:32Z, before the October 15 HG009 reference entry.

**Research method created:** October 21, 2026, AFTER the October 15 H1 losses were seen. The distinction matters. No posthoc factor can be called an original October 14 investment prediction.

## Original audited market-file source

The repository already archived original NSE stock-futures UDiFF ZIP bytes through AE001-SC003:

- SHA-256: 3e923241fa238ae1f2d2a86cc70ff63967d1fe9e0c96423716d1991bba372835
- Original immutable source attempt: 8dd9753ebf55619461be5cff9cebe9476039236fe0b7ca2648ce55a7d9fd64fb
- Date: 2026-10-14
- Original CSV accepted stock futures contract rows: **635**, multiple expiry series.
- Source collected after October 14 market close and before October 15 reference market opening.

The P029 algorithm independently verifies the raw ZIP and the hash-chained source ledger, parses stock-futures contracts through the existing validated NSE FO parser, and groups distinct underlying ticker names. It joins ticker exposure to the original 300 source-frozen HG009 names, retaining every original symbol+ISIN, group of 100, and absence in the original source.

### Why this matters

NSE Closing Auction Session (CAS) initially applied only to cash securities with derivatives, and SEBI published revised auction/derivative settlement rules on October 15. Different auction mechanisms and closure conventions may distort comparability of reported closing prices and executable market impact. Source:
https://www.nseindia.com/static/products-services/closing-auction-session and https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&smid=0SEBI&ssid=7

However stock-futures UDiFF **does not prove a full authoritative CAS membership or issuer ISIN match**. A present futures ticker does not by itself prove stock-level CAS operation. An absent contract ticker is NOT proof of ineligibility. The output flags this explicitly and reports **zero CAS issuer eligibilities verified**, regardless of observed futures ticker counts.

## No retrospective alpha rescue

This analysis is designed AFTER October 15 H1 source returns were seen. Even though the October 14 original FO bytes predate the first entry, its use as a selected feature does not. Do not refit the original 100 selected names, adjust first-day H1 or overlapping H5 based on this new flag, infer a trading fill, or report a causal model improvement.

For genuinely new source-frozen cohorts, obtain official CAS eligible security list, stock-level effective dates and auction price formation, original first retrieval UTC, security ISIN identity and direct spread/depth/impact source **before** future experiment entry. Exchange-published close is not the same as fillable market depth at that close.

No investment recommendation, return expectation, sector-neutral/size-neutral adjusted alpha, issuer owner-cash valuation or live-capital approval is generated.

The original source-only report is reproducible with scripts/materialize_hg009_p029.py --check and tests/test_hg009_p029.py. Report path: research/hg009/hg009-p029-preentry-fo-microstructure-v1.json.
