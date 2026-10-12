# H021-P011: First Verified 12 October Source Capture Trigger

Frozen: **2026-10-12 after the 15:30 IST NSE market close**, before any
original official next-open price has been sealed.

## Reason for narrow change

The first H021-P003 EPS consensus ten-company cohort was independently
frozen on 9 October before its planned 12 October 09:15 IST next-session
open. H021-P004 already provides an exact 12 October NSE UDiFF EQ and Nifty
500 price-index original-source collector, with original SHA custody and
fail-closed missing rows. Its existing GitHub Actions schedule is 18:15,
18:45 and 19:15 IST.

A delayed scheduled runner can postpone or miss an observation. P011 adds
a **single on-main-merge trigger** to the existing source-acquisition
workflow, retaining the three post-close scheduled retry opportunities.
This does **not** adjust the frozen primary H021 cohort, pricing rule or
session date, and does not invent a price.

## Source-first and no hindsight

The collector remains strictly gated:
- original planned session: 12 October 2026 only;
- must be after 15:30 IST official session close;
- source requests use the exact original NSE CM UDiFF and Nifty 500 daily
  index report URLs, with original byte SHA-256 and HTTP statuses;
- all ten selected EQ symbol/ISIN rows and price-index row must be valid
  for a complete observation;
- missing, unparseable or blocked reports remain explicit **source
  failures**, never substituted with other dates or another vendor;
- once a complete source observation is anchored to main, future
  runs exit instead of overwriting it;
- research-only, no broker fills, no fund positions or return outcome.

The workflow's sole new push trigger is a change to its own workflow
file. Unrelated automated research commits never repeatedly request the
source.

No attempt may retrospectively be called a pre-open executed fill: this
is a post-close independent official observation of the previously
frozen next-session open-price proxy.

## Next gates after source anchoring

1. Verify the actual GitHub action receipt and source hashes in main,
   including all ten official stock rows and official Nifty 500 price index.
2. Reconcile any first-session absent rows or blocked NSE source
   separately, without assuming zero returns or changing chosen stocks.
3. The original H021-P006 Muhurat special-session and official 2027
   calendar readiness gates remain blocked for actual 20/60-session
   outcomes.
4. Independently verify full-horizon corporate actions, dividends,
   index price versus total-return basis, costs and survivorship.
5. Four matured original prospective monthly-equivalent cohorts are
   required to evaluate the precommitted H021 edge.

**Capital eligibility and live trading remain disabled.**
