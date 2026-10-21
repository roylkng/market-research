# HG009 P036. Can an independently sourced NSE cohort actually be matched?

**Method registered:** October 21, 2026. **Scientific class:** new-cohort *feasibility only*. **Live capital:** disabled.

## Why this changes the source strategy

The first HG009 experiment selected 100 companies from an October 5 full-market screening universe of 2,319, plus 200 one- and zero-signal matched controls. Its October 15 H1 selected arm underperformed both controls. The original matching relied mostly on historical turnover and was not sector or size balanced.

The October 21 original NSE Total Market index file contains **741 valid EQ symbol+ISIN+one-level industry rows** among 755 constituents. It identifies only **142/300** of the previously chosen names. Trying to classify the other 158 via a public BSE active-equity API failed with **HTTP 403** on October 21. Those prior names and the negative H1 result must not be reclassified or discarded retrospectively.

Instead, this P036 analysis tests whether a **different, future research sample** can be built entirely from the officially covered index subset. It never claims to fill missing historical sector labels of the original 300.

## Reproducible source-only population

The P036 code replays the original signed October 5 HG001 router and the archived official NSE Total Market raw CSV, SHA-256 b5e615e961ba861c38e191f0341dd1e352a92ea9cf9e3cfebb9de621cc323134, first observed 2026-10-21T10:33:05.207160Z.

- Exclude **every one** of the original 300 HG009 selected/one/zero names by frozen symbol and ISIN. No overlap with already inspected H1 names.
- Admit only valid original NSE EQ symbol+ISIN pairs with authenticated one-level industry.
- Require the original HG001 source to contain a clear research lane, outside U001 and without previously recorded governance/asset cautions.
- Require at least **₹1 crore original historical median daily traded value**, strictly as a preliminary research feasibility floor. It is not measured bid/ask spread or order-book capacity.
- Form three experimental arms: two-or-more evidence planes, exactly one, and zero.
- Match *within each exact original one-level NSE industry + historical liquidity band*. Determine the number of possible 1:1:1 matched triples in each stratum. Any scarce control stratum transparently limits overall sample size.
- Within each stratum and arm, a predetermined SHA-256 sort of the original NSE source identity and constant method ID breaks ties without opening any postentry stock returns.
- Publish all source counts and an **inactive candidate queue**, not a registered forward trial.

## What this can and cannot prove

If the index-covered population contains many exact-industry-and-liquidity triplets outside the original 300, the construction can support a smaller **later** exploratory cohort with substantially better source coverage than the original source-blind matching. It may also reveal that the exact-match feasible count is too small. Either outcome is a useful constraint.

**It still cannot prove factor-neutral alpha.** One-level NSE industry is not audited four-tier classification, and Financial Services mixes lenders, asset managers and insurers. The current analysis has no source-replayed point-in-time free float, share-capital size, volatility/beta, accounting regime, corporate-action-adjusted total return, market-depth impact or transaction costs. The original index file was first observed after October 15 and cannot repair that historical cohort. A new independent trial needs its *own* future-effective preregistration before any return labels are used, plus adequate matched samples, full issuer evidence and longitudinal follow-up.

## Reproduction and proof

The materializer uses only retained original Git data. It does **not** contact NSE/BSE or price services:

    python scripts/materialize_hg009_p036.py
    python scripts/materialize_hg009_p036.py --check
    pytest -q tests/test_hg009_p036_pool.py

The signed artifact will be placed at research/hg009/hg009-p036-next-cohort-industry-feasibility-v1.json. A successful report does not automatically register a new portfolio or make a BUY recommendation. Original 300-company H1/H5 evidence stays immutable and separate.


## First authentic source-replay result (October 21, 2026)

The dedicated source-only script successfully parsed the archived official **741 valid EQ/industry** NSE index rows and excluded every original 300 development name. The eligible candidate counts after outside-U001, original caution and historical >=₹1 crore/day traded-value gates were:

| Arm | Original candidate pool after source gates | Maximum exact industry + turnover triplets |
|---|---:|---:|
| Convergent (2+ signals) | 26 | 18 |
| One signal | 110 | 18 |
| Zero signals | 55 | 18 |

The **maximum feasible independent exact-match cohort is 18 companies per arm (54 total)**. This is **not** an approved trial with adequate statistical power or broad Indian-equity coverage. The shortfall is not solved by cherry-picking favorable sectors or relaxing industry/turnover matching after seeing a return. Numbers arose from original Oct5 opportunity source combined with original NSE Oct21 one-level industry source, not future returns.

Source builder's deterministic report SHA-256 on the first captured run: `7c98f87ecac25350a6611c212a7f4b9b6c0ffe92dca7b1e083971e7ae7dbcb66`. The report requires its permanent Git artifact and independent replay. The next method must separately verify financial accounting regime, float capitalization, risk, industry source scope, dividends/entitlements and execution costs before any 60/120/252 NSE-trading-session prospective entry.

**Strategic interpretation:** the "restrict to easily classified NSE index names" alternative closes the sector-data-gap only by shrinking the experimental population dramatically. It may be a useful small feasibility pilot, but it does not fulfill a large, high-confidence hidden-gem alpha objective. Broader original issuer segment/industry coverage and independent sources remain necessary for a well-powered generalizable trial.
