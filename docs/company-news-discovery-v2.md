# V2 dated company/news discovery

## Delivered boundary

This component discovers public headlines and release URLs at runtime. No
individual article URL or expected financial value is supplied in its source
configuration. It follows bounded PRNewswire India listing pagination, reads
RSS/Atom snapshots, retrieves approved issuer-distributed HTML documents, and
joins mention-based research tasks into the existing company research store.

It is a discovery and review-input layer, not a directional forecast model.
Topic matches do not establish that an event happened. For example, "not yet
commissioned" prompts a capacity review without recording commissioned capacity.
Named mentions do not establish ownership, revenue attribution or beneficiaries.

## Source scopes

`registry/company_news_discovery_v2.json` records provider type, region, source
URL, adapter, timezone, article path scope and documentation. The routes are:
PRNewswire India listings and global RSS, NSE announcements, SEBI RSS, PIB RSS,
and Mint companies/markets headlines. Every configured route is attempted and
failures remain failures. A working press-release source does not replace
editorial or exchange coverage. Mint is headline-only, for personal noncommercial
reading under its published RSS terms, not licensed commercial redistribution.
No paywall, authenticated account, subscription or access restriction is bypassed.

Official source directories:
- https://www.prnewswire.com/rss/
- https://www.prnewswire.com/in/news-releases/news-releases-list/
- https://www.nseindia.com/static/rss-feed
- https://www.sebi.gov.in/rss.html
- https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3
- https://www.livemint.com/rss

## Acquisition and accounting

The default run is capped at three listing pages per source and twelve article
requests, with a seven-calendar-day review lookback. Pagination follows actual
listing links, not invented date URLs. All items remain in the store, including
outside-lookback, malformed, future-dated, unknown-date and out-of-panel items.
Every budget deferral and headline-only restriction is recorded in the run.

Acquisition priority is a fixed research triage: panel mention, economic topic,
source identity and provider ordering. It is not an estimated probability or
investment rank. Unknown publication time is not treated as "today" or assigned
an invented old timestamp for ranking. The clock for prospective use still
requires actual source observation and processing, not a backdated public date.

Article retrieval is restricted by both host and path. The optional transport
guard checks each redirect before requesting it, including the same release
resource identity. Original HTTP bytes and normalized body bytes are retained
in the private runtime store and hashed. Published times come from article
metadata or explicit feed dates. Disagreement is unresolved. A day-only date is
stored as a conservative upper bound, not a fake exact publication time.

All body routing excludes the provider's navigation and the publisher's trailing
About boilerplate. Exact legal-name aliases and explicit `NSE:` identifiers are
matched. Short bare tickers are deliberately not guessed. Unknown NSE identifiers
and BSE codes remain candidates for security-master verification, not approved
listed securities. Parent/subsidiary and customer relationships require review.

Wrapper-only changes create observations without duplicating document versions.
Substantive changes create immutable versions. Latest state is derived from the
last successful observation, including A -> B -> A reversions, not from the
original version's first-seen date. Failed latest retrieval remains visible.
Old reports reproduce at their recorded cutoff using their original engine
version, configuration and retained source data.

## Run

After the existing project setup, from repository root:

```bash
python scripts/run_company_news_discovery.py \
  --store .marketlab/company-intelligence-v2 \
  --output reports/company-news-discovery \
  --collect
```

Omitting `--collect` only verifies retained documents and rebuilds a report.
The same store can contain existing original company facts. The new report joins
news document IDs and headline IDs into those company packets without treating
headlines as financial facts. Exit 2 means acquisition had a partial failure.
The read-only Actions workflow is a finite verification run, not a production
scheduler. No H-series rule, old canonical ledger or schedule is changed.

## Acceptance and unresolved work

Acceptance requires actual discovered URLs, actual original article bytes,
reproducible dates/mentions/topic spans, visible deferrals, and tests rejecting
backdating and silent source failures. Counts of unit tests do not establish
predictive value. A bounded discovery snapshot is not complete news coverage.

Still needed: reliable complete exchange acquisition, PDF/XBRL attachments,
verified aliases and the wider security master, economic event interpretation,
company exposure links, cash-flow/valuation inputs, licensed editorial/social
inputs where necessary, and out-of-sample forecasting/missed-mover evaluation.
Raw third-party documents are not committed to Git. Do not republish acquired
article bodies or use headline-only data for a commercial service without rights.
