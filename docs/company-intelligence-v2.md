# Company intelligence v2: first integrated slice

Date: 2026-09-17. Research only. Live capital disabled.

## What is implemented

The isolated input-handling prototype is now a repository module with its tests,
a durable SQLite/WAL research store, bounded public HTML/RSS collectors, exact
source-span extraction, common-clock return arithmetic, conditional per-share
valuation arithmetic, and a reproducible 100-company research report.

This is a company-intelligence layer alongside the old hypothesis laboratory.
No frozen H-series definition, existing ledger or production schedule changes.
The component does not issue investment rankings or calibrated forecasts.

## Run

From the repository root after installing `.[dev]`:

```bash
python scripts/run_company_intelligence.py \
  --store .marketlab/company-intelligence-v2 \
  --output reports/company-intelligence-v2

python scripts/run_company_intelligence.py \
  --store .marketlab/company-intelligence-v2 \
  --output reports/company-intelligence-v2 \
  --collect
```

The first command performs no network reads. The second attempts exactly the
five reviewed endpoints in `registry/company_intelligence_v2.json`, with
robots checks, an honest research user-agent, size/time limits, approved hosts
and redirect checks. It does not acquire subscriptions, authenticate accounts,
rotate proxies, bypass blocking, follow arbitrary attachments or place orders.

Exit 2 means partial/failed source acquisition. Reports and failure evidence
are still retained. A source failure is not a successful empty news window.

## Panel and scope

A new research panel is bootstrapped from the exact existing 100-name identity
snapshot, verified by its Git blob and SHA-256. It has a distinct panel ID and
does not alter the original U001 membership or copy historical signals into v2.
The initial non-financial, larger-company bias is explicit. Membership is not
an investment recommendation and registering 100 identities is not completing
100 fundamental reports.

Every company receives nine measured facets: financials, prospects, execution,
expectations, valuation, market, news, exposures and social. These begin as
NOT_COLLECTED. A single document creates at most PARTIAL_SOURCE_COVERAGE, never
complete current news or completed investment research. Failed latest requests
remain visible alongside previously acquired facts.

## First real-source integration

The bounded run attempts TCS current/prior Q1 financial releases, L&T's FY2026
board report, Infosys' Q1 results index, and the official NSE announcement RSS.
TCS claims are read from retained HTML, not hardcoded numeric answers. A growth
comparison requires compatible basis, units and currency. The TCS margin
comparison deliberately remains blocked because the current extractor labels
an exceptional-item adjustment that has not been reconciled with the prior.
The AI run-rate mechanism is a reviewed, source-linked research hypothesis,
not a claim that all AI sales are incremental or a stock forecast.

L&T's extracted total income is explicitly standalone. It must not be mixed
with consolidated profit. The Infosys index is document discovery only until
its attached statements are acquired and parsed. It is not financial coverage.

RSS collects all items. Unmatched, out-of-panel, ambiguous and malformed items
remain explicit leads. Only exact normalized company identities are linked.
Headlines do not become verified economic facts. RSS is a finite snapshot, not
proof of a complete historical or exchange-wide window.

Official source review:
- https://www.nseindia.com/static/rss-feed
- https://www.tcs.com/who-we-are/newsroom/press-release/tcs-financial-results-q1-fy-2027
- https://www.tcs.com/who-we-are/newsroom/press-release/tcs-financial-results-q1-fy-2026
- https://investors.larsentoubro.com/board-report.aspx
- https://www.infosys.com/investors/reports-filings/quarterly-results/2026-2027/q1.html

## Integrity and operations

Raw and normalized documents are content-addressed outside tracked Git files.
Claims retain raw hashes, normalized-text span offsets, units, period, basis,
publication precision and actual observation/processing timestamps. Publication
known only by day uses that day's end in IST conservatively. Today's acquisition
cannot create a decision as of an earlier date.

Records are append-only with SQL update/delete guards and digest verification.
A duplicate observation preserves the original processing time. Content or
parser changes create new records. Conflicting values are not silently replaced.
No hash proves a claim is true, clocks are honest, or an administrator cannot
change a database. Backups, service deployment and external checkpointing remain
production work.

The core prototype tests also preserve later corrections, provenance deduplication,
social-lead isolation and common completed-session windows. There is no network
price adapter in this slice. None of these tests is evidence of predictive alpha.

The Actions workflow is a bounded acquisition rehearsal, not a production cron.
Its token is read-only and it cannot update main or any existing experiment.
A production scheduler and durable hosting are not provisioned by this PR.

## Remaining gates

1. Broader source maps and real company research beyond the pilot. Exchange
   attachments, prospect milestones, expectations, current valuation and macro
   exposures must be acquired, interpreted and independently reviewed.
2. A wider security master and complete announcement backfill. The initial
   finite RSS snapshot cannot be marketed as full-market radar coverage.
3. Licensed/permissioned news and public-social access, with measured cost and
   completeness. Those inputs are still NOT_COLLECTED, not neutral sentiment.
4. Forecast and missed-mover evaluation, with controlled price/fundamental/news/
   prospect/social ablations, held-out future windows and paper execution.

The foundation archive was locally verified before integration. This PR extends
it rather than treating a new design document as a completed product.
