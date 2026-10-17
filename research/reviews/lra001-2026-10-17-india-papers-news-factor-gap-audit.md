# LRA001 | India equity market, papers and research-gap audit

**Research cutoff:** 2026-10-17 (IST). **Purpose:** Reassess the existing MarketLab NSE research strategy and identify robust sources of *potential* incremental prediction, rather than backfit recent winners. **Status:** Post-hoc design review, **NOT a new frozen H-series experiment** or buy list. All live capital disabled.

## Executive decision

**Keep the scientific foundations. Fix the mismatch between goals and evaluation.** The repository already plans an alpha factory with point-in-time evidence, purged walk-forward learning, alpha factor controls, liquidity and cost. H001 raw growth was rejected, H002 PEAD sign was inconclusive in a 24-observation feasibility sample, and the fixed H003/H004 tests remain prospective. Do not resurrect H001 or quietly rewrite H004.

**Highest leverage research improvements:**
1. Build a separately preregistered **252/504/756 trading-session (roughly 1/2/3-year) value-creation research sleeve**. The EOD AE001 1/5/20/60-session horizons and H003 120-session sleeve cannot test the user's 1–3-year hidden-gem objective.
2. Explicitly test **liquidity-conditioned momentum versus the existing pre-momentum hypothesis H004** as independent challengers. Indian evidence suggests liquid winner continuation is material. H004's caps on prior returns may avoid false positives or may exclude profitable trends. Resolve empirically, never by editing H004.
3. Add a **model-pretraining temporal firewall**. Timestamped source documents are necessary but insufficient when an LLM has learned future events during pretraining. Label current-LLM historical narratives POST_HOC, refuse to promote them to historical alpha, and separately evaluate chronological checkpoints and prospective records.
4. Require **market-implied future operating cash versus independent incremental-ROIC project economics** under realistic financing, dilution and margin stress. A 12x/16x/20x static owner-cash hurdle is a useful rejection screen, NOT an intrinsic value or expected-return estimate.
5. Fully operationalize **risk, sector/size/quality/momentum/liquidity neutral controls and after-cost portfolio execution**, including a dated SEBI closing-auction-methodology version. A few successful stock stories are not alpha.
6. Restrict and enumerate **factor trials and researcher degrees of freedom**. Report false-discovery controls and post-publication degradation, not merely highest historical Sharpe.

These are research PROPOSALS. Existing prospective signals, recorded market sessions, registry hashes and 300-company HG009 test arms remain immutable.

## Empirical research reviewed

| Evidence | What the paper actually supports | Implication | External validity limitation |
|---|---|---|---|
| Lalwani & Meshram, *Applied Economics* (2022), 1994–2019 Indian shares | 35 characteristics evaluated in a survivorship-bias-free Indian listed-firm sample; 14 cross-sectional predictors exceeded absolute t-stat 3; rolling OOS ML beat OLS in study | India-specific factor baselines are essential | Historical pre-2020 regime, licensing and execution may differ |
| Chui et al., *Pacific-Basin Finance Journal* (2023), 3956 BSE names 2000–2021 | Liquid stocks showed more persistent momentum; illiquid names stronger short-horizon reversals | Interact momentum with liquidity, holding horizon and tradability | Sample includes BSE names; replicate on point-in-time NSE |
| Gu, Kelly, Xiu, *RFS* (2020) | Nonlinear ML gained from interactions, particularly momentum, liquidity and volatility | Establish rank/ridge baseline before boosted-tree challenger | US stocks and model-specific assumptions |
| Hou, Xue, Zhang, *RFS* (2020) | 65% of 452 anomaly tests fail t=1.96 under microcap controls; 82% under stricter threshold | Control data snooping and microcap dependence | Alternative factor-replication work disputes pessimistic conclusion |
| Jensen, Kelly, Pedersen, *JF* (2023) | Bayesian analysis supports factor replication in 13 themes and 93 countries | Organize into conceptually distinct families, not hundreds of proxies | Replication conclusion differs by model and weighting choices |
| McLean & Pontiff, *JF* (2016) | Out-of-sample returns 26% below discovery, 58% lower after publication across 97 predictors | Assume edge decay as methods diffuse | Historical US anomaly portfolio study |
| Fama & French, *JFE* (2015), Novy-Marx *JFE* (2013) | Investment and profitability, including gross profitability-to-assets, matter for return patterns | Build value *and* realized incremental capital-productivity features | Historical US evidence; India's sector/accounting basis differs |
| Lalwani & Meshram; Chui et al. | Both support empirical tests rather than deterministic generalization | Keep price, quality, liquidity and market-cap matched controls | Indian data vintage and costs matter |
| Bailey & López de Prado, *JPM* (2014) | Deflated Sharpe addresses multiple comparisons, selection bias and non-normal returns | Maintain full trial ledger, DSR and block bootstrap | DSR alone cannot fix causal leakage or survivorship bias |
| Lopez-Lira & Tang et al., *JFE* (Oct 2026) | LLMs often classify immediate US news reaction, including **non-tradable** initial response; subsequent price drift exists but is weaker | Evaluate news *novelty / information delta* at realistically tradable timestamps | US, 2021–2024; adoption erodes anomalies |
| Kelly et al., *NBER* (May 2026) | Unrestricted LLM training can encode future information; monthly point-in-time model checkpoints mitigate it | Test chronological financial NLP or genuine forward-only probes | Working paper, implementation/testing costs |
| Sarkar & Vafa (2024), Didisheim et al. *Economics Letters* (2025) | Evidence of LLM pretraining lookahead in finance-oriented tasks | Model weights require their own causal cutoff audit | No simple prompt guarantees absence of leakage |
| FinanceBench (2023) | Older retrieval-augmented financial QA configurations still made many errors | Prefer extracted numeric sources, unit tests, review receipts, abstention | Benchmark models are older than today's LLMs |
| Cheng et al., *J. Empirical Finance* (2025) | Simple linear forecasting can rival complex ML methods | Mandatory cheap regression baseline | Time-series setup differs from cross-section |
| Eisfeldt, Kim, Papanikolaou, *Critical Finance Review* (2022) | Accounting intangibles can change value assessments | Normalize R&D / software / intangible spend where source-complete | Do not blindly capitalize all intangibles, especially acquired goodwill |

**Direct source links (primary journal/research pages)**

1. https://www.tandfonline.com/doi/full/10.1080/00036846.2021.1982132
2. https://www.sciencedirect.com/science/article/pii/S0927538X23002640
3. https://academic.oup.com/rfs/article/33/5/2223/5758276
4. https://academic.oup.com/rfs/article/33/5/2019/5236964
5. https://afajof.org/issue/volume-78-issue-5/
6. https://www.onlinelibrary.wiley.com/doi/full/10.1111/jofi.12365
7. https://www.sciencedirect.com/science/article/pii/S0304405X14002323
8. https://www.sciencedirect.com/science/article/pii/S0304405X13000044
9. https://www.pm-research.com/content/iijinvest/40/5/94
10. https://www.sciencedirect.com/science/article/pii/S0304405X26001066
11. https://www.nber.org/papers/w35247
12. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4754678
13. https://www.sciencedirect.com/science/article/pii/S0165176525004392
14. https://arxiv.org/abs/2311.11944
15. https://www.sciencedirect.com/science/article/pii/S0927539825000209
16. https://www.emerald.com/cfr/article-abstract/11/2/299/1324902/Intangible-Value

The papers have mixed horizons, economies, weighting assumptions and transaction cost treatment. Numbers quoted above are **their study results**, not predicted Indian strategy returns or calibrated priors for MarketLab. Do not cite unreleased/future-dated work as existing evidence.

## Market/news regime: observed as of October 17

1. **Tightening and inflation:** Reuters reports RBI raised repo 25 bps to 5.50% on Oct 7, first hike in nearly four years; September CPI 5.54%; September wholesale inflation 11.39%, driven partly by energy. Rate/cost-pressure interactions may affect levered capex, working capital and forward valuation.
2. **Foreign versus domestic flows:** Reuters reports Rs 383.07 billion September equity mutual fund inflows and Rs 324.90 billion SIPs despite substantial foreign outflows. This is evidence of distinct investor bases, not proof of price predictability from gross flow signs.
3. **Sector concentration:** Reuters Oct16 reports Nifty IT +11.7% over the week. Any individual IT excess return must be measured relative to the sector and characteristic-matched names.
4. **Closing auction methodology:** SEBI circular dated Oct15, 2026 (No. HO/47/11/11(3)2025-MRD-POD2/I/23843/2026) updates CAS 15:30–15:40, derivatives pricing based on continuous-session trailing 30-minute VWAP, and other order handling. Most changes effective **Dec 7, 2026**; 4.8 order-transition provisions effective **Feb 8, 2027**. Version historical execution and closing-price provenance by the effective date, *never rewrite history*.
5. **Valuation compression risk:** Rate increases are a plausible downside mechanism for long-duration growth; explicitly stress discount rates and terminal exit multiples rather than assuming a fixed 16x cash multiple.

Sources:
- https://www.reuters.com/world/india/india-raises-policy-rate-by-25-bps-first-hike-nearly-four-years-2026-10-07/
- https://www.reuters.com/world/asia-pacific/view-india-inflation-jumps-554-september-strengthening-case-further-rate-hikes-2026-10-12/
- https://www.reuters.com/world/india/india-wholesale-prices-rise-1139-year-on-year-september-2026-10-14/
- https://www.reuters.com/world/india/india-equity-mutual-fund-inflows-hit-5-month-high-september-despite-nifty-slump-2026-10-12/
- https://www.reuters.com/world/india/indian-shares-track-higher-open-lower-treasury-yields-sebi-relief-2026-10-16/
- https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1792079571420.pdf

## Current repository alignment: implemented versus planned versus missing

**Already designed or partly implemented (do not reinvent):**
- `README.md`, `registry/hypotheses.yaml`: reject H001, freeze H002 earnings-surprise and H003 management delivery, plus H004 pre-momentum. H002 original feasibility n=24, uncertainty crossed zero.
- `docs/architecture.md`, `docs/alpha-factory-implementation-plan-v1.md`: distinct immutable H-series and AE001, 1/5/20/60-session forward labels, per-feature known-at, 13 broad feature families, purged walk-forward, risk/factor/cost/optimizer planned, trial accounting.
- `registry/h004_signal_rule.yaml`: H004 has deliberately capped prior momentum and requires information anchors; it is a **different economic bet** from liquidity-conditioned continuation.
- `registry/universes.yaml`: U001 selects 100 top-FFMC nonfinancial names from Nifty200 for H002/H003, a valid controlled earnings cohort, but **not** a full search for under-followed mid/small names.
- HG009 frozen 300-company experiment and P014–P024 owner-cash diligence: useful 100 candidate/2 control arms, but post-Oct15 dossiers cannot be presented as preregistered performance.
- P019–P021 owner-cash scenario math, original byte checks and precise document timestamps reduce source leakage and false certainty but **cannot establish model-pretraining innocence**.

**Material missing or not demonstrated in inspected repository artifacts:**
- A separately validated 1/2/3-year business-value outcome, including dividends, rights, delistings, share dilution, mergers and survivor removal.
- Original point-in-time consensus/estimate revisions for surprise relative to *market expectations*; seasonal prior-quarter EPS is not analyst consensus.
- Independent long-horizon capital allocation: organic vs acquired invested capital, incremental ROIC, sustainable maintenance and growth capex, working-capital cash, exit multiple and cost of equity.
- Directly tested liquidity × momentum interaction as a separate challenger to H004, controlled for size, value, sector and volatility.
- LLM model-knowledge-cutoff manifest and historical contamination tests, as distinct from retrieval-time source controls.
- A demonstrated live cost/microstructure model with the exact upcoming CAS regime and non-executable one-sided upper-circuit fills.
- Historical universe/delisted security and total shareholder return reconstruction across smaller equities at all relevant dates.
- An independently assessed alpha after taxes/fees/impact in multiple future market regimes.
- Consistent project status: `README.md` lists only H001–H003 while the alpha plan discusses H002–H024; registry/hypotheses.yaml currently only registers H001–H004. Reconcile index/metadata documentation from canonical immutable source registers, never synthesize missing formal registrations.

## Proposed next experiments, NOT frozen and no outcomes examined

### Proposed L001: multi-year valuation and reinvestment

Universe: liquid NSE main-board EQ, with point-in-time identity, historical listing/delisting and separate large/mid/small strata. Do not restrict to Nifty200 top100 for discovery; retain a separate capacity/liquidity screen for realistic execution.

Hypothesis: companies with **positive, verifiable incremental return on invested capital AND conservative market-implied operating growth**, after fully diluted balance-sheet adjustments, deliver superior 252/504/756-session *total shareholder returns* compared with value/quality/momentum and industry/size matched controls.

Predecision features: (i) reverse-DCF owner-cash growth hurdle (multi-period, rates stressed); (ii) realized capital deployment by organic / acquisition / maintenance classification; (iii) cash-tax/lease/interest/minority effects; (iv) revenue and cash conversion path; (v) dilution / capital issuance; (vi) asset/intangible R&D treatment; (vii) current investor expectations proxied by disclosed forecasts if time-stamped, else missing.

Benchmark must include Nifty500 total return and sector/matched controls; 1-year/2-year/3-year *labels cannot mature immediately*, so first validations are genuinely prospective only or pretraining-safe prior historical panels.

### Proposed L002: liquidity-conditioned momentum control

Universe: same historical dynamic eligible NSE symbols and tradable liquidity strata. Predeclare 6–12 month formation momentum with a recent-month reversal skip if supported by evidence, then 20/60/120-session outcomes. Include *standalone* liquidity bands, sector/size neutrality and open-price versus executable VWAP comparison.

Benchmark: original frozen H004 non-momentum information anchor, plus simple momentum and sector index. Do not move any H004 thresholds. Question: does conditioning on liquidity improve **net long-only** forward returns, rather than just mean gross decile spreads?

### Proposed L003: earnings information surprise + novelty

Mechanism: market expectation *change*, not raw revenue or positive-news adjectives. Compare frozen H002 seasonal-earnings sign to independent point-in-time news novelty, price already moved, documented analyst revisions where available, and company-source quantified guidance delta. Baseline H002 remains untouched; new hypothesis must be separately registered and frozen before first 20/60-session prospective holdout. Zero marginal information beyond plain UE sign or no licensed historical consensus => reject/abstain.

### Proposed L004: temporal LLM validity study

Compare on exact same pre-cutoff document packet: (A) deterministic numeric/accounting parser + plain linear/rank baseline, (B) current-LLM extraction-only + human source verification, (C) time-restricted model where feasible, (D) forward-only live prospective LLM claims. Record model identifier, model weights/training horizon where documented, request timestamp, source known-at, whether ticker and outcomes blinded, and prompt/content hashes. If (B) beats (A) only on pretraining-era dates and not on true forward holdout, reject historical LLM predictive value.

## Evaluation and falsification contract

- **Researcher degrees of freedom:** maintain complete attempted-factor count, failed/abandoned variants, DSR and familywise/FDR views; no selective winner publication.
- **Causal integrity:** actual known-at AND model-knowledge cutoff, preserve exact source audit and freeze version before observing returns.
- **Controls:** Nifty500 TR, sector TR, matched size/liquidity/valuation/factor portfolios, equal-weight and value-weight, ablation vs simple rank, downside/max drawdown.
- **Tradability:** actual opening order depth if accessible; explicit no-fill on missing/limit-only/circuit/insufficient ADV; fees/STT/spread/slippage/market impact. Version CAS change by effective dates.
- **Regime stability:** predefine RBI rate/inflation/FX/oil/volatility buckets; report model results in each without tuning on holdout. Flows and macro should be context tests, not directional certainty.
- **Universe integrity:** original delisted names must appear; no survivorship, IPO future-membership, split or corporate-action backfilling.
- **Longitudinal results:** 1-year/2-year/3-year forward returns after dividends/corporate actions, benchmark and costs, uncertainty intervals; do not project multiyear 50% returns as calibrated probabilities.
- **Abstain:** missing fully diluted shares, acquisition consideration, original owner cash or price/market data leads to research-only state.

## Recommendation and priority

**P0 now:** Design long-horizon evaluation and no-lookahead LLM controls; add independent liquidity-momentum challenger. These address *scientific coverage*, not another round of post-hoc narrative stock ranking.

**P1 next:** Gather time-stamped analyst consensus/issuer estimate revisions where legitimately available; build full-tradability and share-denominator inputs; conditional macro exposure validation.

**P2 later:** Neural or agentic ensemble challengers only if they add independent after-cost OOS information over linear, rank and price/volume baselines.

**Do not claim** this document establishes alpha, ranks companies, calibrates chances of 50% returns, or permits live trading. It is a sourced plan for new falsifiable tests.
