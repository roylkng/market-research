# Investment approach review: decisions before expansion

Review date: 10 November 2026, India time.
Purpose: discover mispriced Indian businesses and produce defensible, price-sensitive decisions. This is not a promise to produce a buy on every research pass.

## Overall judgment

Keep the evidence-first foundation. Change the allocation of research effort. The project has built valuable source custody, date/identity checks and negative-result accounting, but engineering activity has outrun completed underwriting. The next phase should close company cases, not add another general-purpose agent or small-model benchmark.

The desired chain is:

    broad discovery -> material change -> economic significance -> expectations already in price
        -> recurring per-share cash and downside -> dated research decision -> subsequent evidence

"Positive news -> predicted share-price increase" skips the middle of that chain. A contract is not profit, growing profit is not necessarily incremental to expectations, and a good business can be a poor investment at its offered price.

## What the retained system actually contains

The reviewed `cc001-state` snapshot was recorded at 2026-11-08T19:12:49Z. Its source workflow is 42513773657. The downloaded state artifact 13630462347 has SHA-256 `c1cec46244b4907c9c58f931b9f6f405111ca927cc9f13615d46fc8548358ec4`.

| Measure | Retained result | Correct interpretation |
|---|---:|---|
| Processed financial documents | 350 | Not 350 investment decisions |
| Companies in financial/cash reports | 196 | Received NSE coverage, not all NSE/BSE stocks |
| Scope-specific cards | 344 | Consolidated and standalone are not distinct companies |
| Unreviewed reporting-period records | 674 | Extraction is not accepted underwriting |
| Retained company price/history contexts | 15 | Not complete valuation coverage |
| Announcement candidates / originals read | 6,448 / 4 | Routing metadata is not full-document analysis |
| Announcement identity differences | 1,285 | Blocked joins, not negative investment signals |
| Full company memo imported into the decision register | 1 | SEAMEC WAIT, dated 9 November |
| Preliminary screens imported separately | 3 | CONCOR, KRSNAA and UPL are not full underwriting cases |

The broad cash report has zero same-source year-ago revenue comparisons for its 196 preferred-scope companies. Separate historical-context cards contain some additional year-ago comparisons. These statements must not be confused. Sequential quarterly changes in the broad report are attention cues, not seasonality-adjusted evidence of sustainable growth.

The latest news report contains no retrieval errors in that batch. All four planned new reads were deferred for storage headroom. The checkpoint is 124,451,387 expanded bytes, approximately 118.7 MiB, against a 128 MiB pilot cap. The news reader requires additional document/reserve headroom. Raising the cap without a durable storage plan merely postpones failure.

At four news documents per invocation, 6,444 unread candidates require at least 1,611 successful invocations with no new arrivals. At three company contexts per invocation, one pass through 196 issuers takes 66 invocations. These are arithmetic capacity bounds, not forecasts of completion. They rule out describing the current pilot as comprehensive daily coverage.

## Keep, change, stop

| Component | Decision | Reason |
|---|---|---|
| Original evidence, identities, publication/observation clocks | Keep | Necessary to avoid wrong-company facts and retrospective entries |
| Frozen hypotheses, failed trials and independent outcome ledgers | Keep | Protect against selective reporting and retrospective tuning |
| Company-specific cash/earnings underwriting | Expand | Directly contributes to a price-sensitive decision |
| One generic P/E and growth assumption for every sector | Replace as a decision rule | Useful sensitivity arithmetic, not a universal valuation model |
| Alphabetical context rotation | Replace as the research workflow | It allocates scarce effort by name rather than the unresolved decision |
| Repeated small-model tests on four seen documents | Stop as the next investment deliverable | They are engineering diagnostics, not evidence of broad model quality or returns |
| Counting tests, documents or valid citations as progress toward alpha | Stop | These are reliability measures, not investment outcomes |
| Building an unattended recommender before a useful research desk | Defer | The tested automatic interpretations are not reliable enough |
| Expanding raw intake while storage is blocked | Do not disguise as healthy growth | Preserve originals and migrate deliberately, rather than discard evidence |

The H001 registry already rejects raw earnings acceleration as a sufficient return predictor. Reusing similar growth figures for *diligence routing* is acceptable. Calling that routing an alpha score would reintroduce the rejected idea under another name.

The 1.5B/7B trials do not prove that LLM-assisted investing cannot work. They show that those model/prompt/protocol combinations were inadequate on those four development documents. Exact source-block selection addressed quotation reproduction, not complete interpretation. A stronger model still needs task-specific, genuinely unseen evaluation. No new model benchmark is run by this review.

## One research workflow, separate from the scientific experiments

The practical research track should focus first on medium/long-horizon business changes. Short-horizon event trading has a different latency, execution and cost problem and must remain a separate experimental track. Existing H-series, HG009 and AE001 contracts are unchanged.

### Discovery

Use cheap, broad source discovery, then allocate attention to material changes. Retain excluded, unsupported and unresolved cases in denominators. Resolve duplicate security identities across exchanges. Current membership must not be substituted into historical universes. Nominal share price is not a valuation measure.

Research lanes should include recurring-earnings improvements, funded reinvestment, capital returns, balance-sheet repair and time-bounded special situations. Adverse disclosures have a separate risk-review lane, not a negative-return forecast by default. Do not discard loss-making, asset-heavy or financial businesses merely because an industrial cash formula cannot value them.

### Establish the business facts

Confirm the business model and accounting scope first. Match year-ago periods and explain seasonal, acquisition and restatement effects. Separate legal recipient from economic amount ownership. Preserve signing, completion, payment, operations and conflicting assertions separately.

LLMs can retrieve, extract, compare, explain and challenge. Deterministic code should own units, arithmetic, dates, denominators and evidence validation. Named assisted review is useful, but it is not independently labelled ground truth.

### Build the economic and valuation case

Translate the event into incremental after-tax cash, funding, duration and per-share effects. Reconcile nonrecurring gains, working-capital release, maintenance versus growth investment, leases, restricted cash, dilution and related parties. Use sector-appropriate economics. Bank lending cash flow is not industrial free cash flow.

Reverse the offered price into the sustainable earnings/cash growth it requires. Compare that requirement with a supportable operating case and an explicit downside case. Use peer/history/cycle evidence to justify multiples rather than automatically selecting 15x. A finite contract is discounted as finite cash, not multiplied into perpetual earnings. Do not add a contract twice when already included in baseline earnings.

Publish the strongest counterargument. A thesis must explain both why the business could improve and why the offered price may not already reflect it. An order headline or a rising chart is not that explanation.

### Close a decision

A case closes as a dated research recommendation, WAIT with explicit reopening conditions, PASS with falsifiers, or EVIDENCE_BLOCKED with the decisive missing item. A missing source is not a rejected company. A WAIT judgment is not evidence that holding cash outperformed.

Each record needs its reference price/date, source cutoff, horizon, scenario assumptions, downside, counter-thesis, next catalyst and invalidation conditions. Position sizing requires portfolio, liquidity and loss-budget information and stays outside this unvalidated research pilot.

The initial register carries forward the SEAMEC memo and three preliminary screens with distinct depth labels. These are historical records, not newly prospective entries. The old closing prices are never treated as fills after this review. A different filing reopens the candidate rather than permanently suppressing it.

## Implementation completed in this review

`scripts/cc001_operating_review.py` reads the existing exports and their receipt hashes without network calls or source-state writes. It reconstructs issuer-level coverage, distinguishes full cases from screens, reports storage/freshness limitations and creates a five-case diligence batch.

Three slots use cash-supported sequential cues without the existing exceptional-income/loss flags. Two reserve breadth outside that cue lane. Among comparable cases, never-enriched issuers precede older enriched issuers, with source-hash ordering instead of an alphabetical or largest-growth tie-break. This is an explicitly unvalidated attention policy, not a trained stock-selection rule. Industry, year-ago evidence, cash normalization, price and liquidity still require review.

The initial five names are EFCIL, NRAIL, ASKAUTOLTD, BALAMINES and BPL. They are **not investment recommendations**. The last two are breadth samples, not claims of superior economics. The 67 accounting-reconciliation cases remain visible separately, and no case disappears from the overall denominator. The broader queue is built only from the received 196-company dataset, not asserted to cover the whole market.

The read-only verification workflow fetches one exact state-branch revision, not unrelated latest files. It exports the operating review and retains its implementation. No scheduled operation, production prioritizer, original store, model endpoint, broker or frozen research ledger is silently changed. This is a completed executable review/queue handoff, not a claim that the storage blockage has been fixed or that the new routing policy has proven returns.

## What must be evaluated next

Three scoreboards are needed, not a single "AI accuracy" score.

**Evidence quality:** critical fact correctness, monetary attribution, contradiction handling, unsupported-claim frequency, missed material events and abstentions. Use a stratified unseen source set, including routine/negative cases, with adjudicated labels. Retain issuer/event clusters and revisions across train/test boundaries. The four development cases cannot become a holdout after inspection.

**Research productivity:** completed company decisions, decision reversals caused by source errors, analyst time per decision, coverage within declared source windows and turnaround on material new information. Set an initial five-active-case work limit. Close cases before continually opening new ones. Any numerical production target is a management target, not demonstrated model capacity.

**Investment value:** evaluate predeclared decisions against broad total-return and appropriate sector/simple-rule baselines, after execution costs and non-executable observations. Retain WATCH/PASS cases and the opportunity cost of waiting. Separate short-horizon price drift from longer-horizon operating thesis realization. A five-year scenario cannot be declared validated after a few good weeks.

Historical source reconstruction remains useful for engineering and understanding businesses. It is not uncontaminated forecasting evidence for an LLM trained on that period. Use frozen model versions, actual availability clocks and genuinely forward decisions. Preserve all attempted variants and avoid treating overlapping issuer/event outcomes as independent samples.

## Commercial direction

The first product should be an evidence-linked research copilot: what changed, what is contradicted, what the price assumes, and what would change the decision. Demonstrate analyst time saved and material errors avoided before selling autonomous stock tips. Generic news summarization alone is a weak product distinction.

Publicly accessible data is not automatically licensed for commercial redistribution. NSE's published data policy addresses intended use, subscription agreements and redistribution permissions. Market prices, issuer documents and third-party research need source-specific rights review. This review provides no regulatory clearance or commercial licence.

A versioned object store plus a transactional metadata database is the appropriate long-term separation. Git remains for code, policies and compact manifests. Do not silently delete originals, raise safety limits or treat 14-day Actions artifacts as permanent retention. No new paid service or credential is provisioned here. The persistent store remains a real operating blocker.

## Next acceptance gates

1. Resolve durable-source storage and verify a saved run with fresh source acquisition, not merely a green report export.
2. Complete a small diverse batch of company underwriting cases. Do not force a positive recommendation when the hurdle is not met.
3. Evaluate a capable extraction/review setup on unseen, adjudicated cases. Enable automatic acceptance only within measured safe task boundaries.
4. Accumulate prospective decision evidence, including false negatives and costs, before claims of investment advantage or capital deployment.
5. Verify commercial data rights, serving operations and customer value before a public subscription product.

No claim is made that independent labels, predictive outperformance, current diluted-share proof for the whole universe, production inference, or commercial hosting are complete.

## Primary methodological references

- Internal H001 result: `registry/hypotheses.yaml`, raw growth rejected as a return-prediction proxy.
- Existing operating contract: `docs/analyst-fund-manager-operating-system-v1.md`.
- Lopez-Lira, Tang and Zhu, *The Memorization Problem: Can We Trust LLMs' Economic Forecasts?*, revised 15 December 2025: https://arxiv.org/abs/2504.14765
- Lopez-Lira and Tang, *Can ChatGPT Forecast Stock Price Movements?*, model-capability and out-of-sample study, not a demonstrated Indian-market strategy: https://arxiv.org/abs/2304.07619
- Harvey, Liu and Zhu, multiple-testing framework: https://www.nber.org/papers/w20592
- NSE Data Sharing & Usage Policy: https://www.nseindia.com/static/market-data/nse-data-policy
