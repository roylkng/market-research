# Company news discovery: measured proof, 2026-09-17

## Scope

The engine discovers listing/feed entries and source URLs at runtime. No
individual article URL or company-specific expected value is configured.
This is a bounded discovery layer, not a trained stock-selection model.

## Initial result and correction

Run 35205651472 at bbb169e4eb53a0753a8f6be70438d39d5a068681 captured
125 items and 12 original PRNewswire documents. None of those documents had a
resolved connection to the 100-company research panel. The bytes and dates were
reproducible, but the result was poor investment coverage. It is not labelled
forecast progress or evidence of successful company selection.

The two editorial routes returned document-stage 404 because the configured
URLs were wrong. The publisher's official RSS directory lists /rss/companies
and /rss/markets, not the former URLs ending in RSS. These were corrected.

Article triage now reserves the budget for resolved panel mentions or explicit
NSE/BSE identifiers, including identifiers outside the panel that still require
security-master verification. At most two unlinked PRNewswire India documents
are explored. All other unlinked records are retained with an explicit deferral.
This corrects acquisition relevance without tuning against stock returns.
It can miss companies mentioned only by an unregistered brand or abbreviation.

## Final live result

- Code: 2c8299cef4d43ee2535619e9fe725e9105647e3d.
- Live run: 35206204335.
- Cutoff: 2026-09-17T09:39:26.416492+00:00, 15:09:26 IST.
- Fresh store, no manually imported excerpts and no old financial claims.
- PRNewswire India: three listing snapshots, 75 headline records.
- PRNewswire global RSS: 20 records.
- SEBI RSS: 30 records.
- Mint companies/markets: 35 records each, headline-only personal research.
- Total retained item records: 195. These are not 195 unique new company events.
- Two original issuer-distributed documents retrieved and independently replayed.
- Zero resolved panel-company mentions in those two documents.
- Two panel symbols mentioned in editorial headlines: IDEA and VEDL.
- The two matched headlines concern share-price/analyst commentary, not verified
  operating developments or an evidence-backed change in intrinsic value.
- Zero numeric financial facts, verified economic events or forecasts created.
- Deferrals: 100 headline-only and 90 unlinked-exploration-limit entries.
  Same-resource duplicates remain in the item/observation records.

NSE announcement RSS still failed at robots retrieval with ReadTimeout. PIB's
robots route returned HTTP 403. Both remain blocked, and the overall acquisition
run is PARTIAL_FAILURE with nonzero exit status. Neither is described as a
successful empty news window. The earlier unsuccessful attempts remain in their
original run artifacts, not rewritten by the correction.

## Integrity and tests

- Focused local intelligence tests: 124 passed plus five unittest subtests.
- Full repository CI at final executable code: run 35206208454, success.
- A local full-suite attempt encountered three legacy failures because its
  installed pypdf was 5.9.0 rather than the repository's pinned 6.17.0. No test
  or dependency requirement was weakened. CI used the pinned dependency.
- Downloaded archive ID 10490057763, SHA-256:
  0ec36ded6e7011289a4e129531a57f16f11b429053fb7aa13aac0e51cbe7c9c1.
- All nine implementation/config/test/document files matched the exact archived
  executable source bytes used by the live run.
- All 11 stored objects passed raw SHA-256 verification.
- Both article bodies, dates, topic spans and entity routing reproduced from
  their original HTTP responses, not from copied browser excerpts.
- Final complete report reproduced exactly from retained state at its original
  cutoff, SHA-256:
  846950ec424489ac8e8410290f5474c7879482519da5311a3f88258570ef51a0.
- The initial 125-item/12-document report also still reproduces exactly.

## Product assessment

Dynamic discovery, public editorial headline reading, source-specific failure
accounting and company mention routing now execute end to end. The source mix
is still inadequate for reliable Indian company catalyst research. Two price
commentary matches are not a substitute for filings, operating prospects,
independent expectations, current valuation or a full-market security master.
No production service, recurring v2 schedule, subscription, social-account
connection, broker integration or live-capital permission was created.
No legacy H-series protocol, canonical ledger or schedule was modified.

## Sources and retained runs

- https://github.com/roylkng/market-research/actions/runs/35205651472
- https://github.com/roylkng/market-research/actions/runs/35206204335
- https://github.com/roylkng/market-research/actions/runs/35206208454
- https://www.livemint.com/rss
- https://www.prnewswire.com/rss/
- https://www.sebi.gov.in/rss.html
- https://www.nseindia.com/static/rss-feed
- https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3

Raw article bodies are not committed or republished in the user-facing report.
