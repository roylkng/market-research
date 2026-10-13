# H021-P022: First Post-Entry Daily NSE Source Capture On Merge

**Frozen 13 October 2026, after the NSE market close.**
This modifies source-capture scheduling only. The 9 October research-only
signal/ten original names, 12 October entry-source packet, 20/60 completed
exchange-session horizons, and no-live-capital restrictions are unchanged.

## Operational gap

The 12 October H021 P003/P004 entry source, including the original NSE
Nifty 500 index report, was fully recovered from official bytes.
However the original P008 daily path collects the next session onward,
starting 13 October 2026.

The capture workflow depended only on cron/manual triggers. At the review
time on 13 October the repository had no committed P008 daily-prices
folder for the first completed post-entry session. GitHub schedules may
be delayed or skipped and cannot be treated as reliable source timestamps.
The original exchange report publication may also lag session close.

This patch makes source collection run at merge through a push trigger
scoped to the source workflow's own file changes. The existing collector
and retry/source integrity rules remain the sole authority for when a
completed official session can be requested.

## No feedback loop

The push event is scoped to the workflow and source/test files.
It does NOT watch the research/prospective/h021/daily-prices folder or
arbitrary main commits. Automated Git writes therefore cannot
self-trigger an infinite acquisition loop or exhaust the bounded
three-attempt NSE original report budget.

Existing workflow rules still include:

- strict NSE market-close gating against future information;
- oldest eligible completed session selection and no look-ahead;
- exact UDiFF EQ/ISIN and original NSE Nifty 500 index file URL;
- original SHA-256, raw bytes and true acquisition timestamps;
- HTTP 404 NOT_PUBLISHED states, with limited original-date recovery;
- explicit missing/blocked/partial states, never invented stock prices;
- append-only Git custody, bounded Git concurrency and run artifacts.

## Scientific boundary

After the 13 October close, the workflow may attempt source retrieval.
A green GH Actions job does not alone prove source completeness.
Only original exchange data verified by SHA/identity count as observed.
Missingness is preserved, not converted into stock price or return.

Unresolved November Muhurat, 2027 official NSE calendar, VEDL
ex-dividend measurement, corporate actions, Nifty500 price index vs TRI
and liquidity/fees remain independent blockers.

No H021 alpha, trading, price-target or capital authorization is
introduced by this change.

Reproduce: pytest -q tests/test_h021_daily_mergetrigger.py
tests/test_h021_daily_prices.py

Verify the first real workflow run and its independently captured source
packet. Do not assume real-world success from workflow configuration.
