# HG009-D001: Independent 100-company Indian equity discovery experiment

**Method freeze:** 2026-10-14.  
**Evidence cutoff:** exact original HG001-D001 **October 5, 2026** full-market frozen router, covering 2,319 NSE identities.  
**Status:** a scientifically reproducible **research coverage cohort**, not an investable watchlist, ranking of expected returns, alpha result, model forecast or permission to trade.

## Resolve a fundamental project confusion

The earlier U001 **100-company** universe consists of the official Nifty 200 *top 100 non-financials ranked by free-float market capitalization*. It is a controlled prospective H002/H003 earnings panel, **not** the same thing as searching 2,319 NSE names for overlooked businesses.

HG001 examined the **full market** on already-frozen evidence from the independent earnings-inflection, asset/capacity-anomaly and special-situation planes. Its source recorded **474** names with at least two opportunity lanes (395 with two, 79 with three). Only 28 of the three-lane companies also met all original HG002 outside-U001/no-caution research criteria. All 28 have since advanced into the HG007 primary-document review queue, with substantial unresolved economic and execution gates.

The new HG009 population is a **separate 100-company exploratory sample** to test whether broader two-lane convergence identifies businesses missed by the strict 28-company triple intersection. Neither cohort supersedes the other.

## Frozen selection, entirely without returns

1. Reopen *exactly* HG001-D001 frozen router SHA-256 79e6b068f95c890e4ef88be62ffe2e8dfb94fabbf293770804e64aaa82d6e5ff, original workflow run 37258053642, artifact ID 11323461912. Reject any other live/current router or altered company metadata.
2. Keep all **28** historical HG002 triple-lane, outside-U001, zero governance-caution, zero asset-caution companies without changing their identity or excluding them because of liquidity.
3. From original outside-U001, zero-caution **two-lane** companies, require at least ₹1 crore original source median daily traded value. This is a *research operations feasibility* threshold, not a predicted future order capacity or return filter.
4. Three independent pair strata are retained: (earnings + assets), (earnings + special situations), (assets + special situations). Select exactly **24 per stratum**, for **72** additional research names.
5. Within each source stratum, sort by ascending SHA-256 of immutable source router SHA, constant cohort ID, frozen two-lane pair, NSE symbol, and ISIN. Tiebreak on NSE symbol. This avoids discretionary cherry-picking after recognizing favored stocks and does **not** rank returns.
6. Preserve exact prior original source row hashes, historical turnover context, flags, all 100 identities, and the hash-sealed selection manifest.

**Total = 28 + 72 = 100 source-selected companies.**

The selection deliberately retains the original 28 including some illiquid/BE-source constrained research cases. **Research inclusion is not investment eligibility.** Largely traded members of the remaining 72 are useful controls and are not automatically "hidden gems" either.

## Validation and temporal firewall

- Original HG001 source includes no opened future return outcomes and no fitted model. The October 5 source is saved as a deterministic binary gzip under research/hg009, so the complete 100-selection can be recomputed even after the GitHub Actions artifact expires.
- Method registration occurs **October 14**, not retrospectively on October 5. Historical price/news outcomes between October 5 and October 14 may be used only as *development* context clearly labeled as such. Do **not** claim a scientifically preregistered pre-October-14 alpha test.
- A future predictive trial must separately freeze feature timing, source delay, labels, models, baseline, decision clock, costs and train/test split **before its first eligible decision**. No "100 names will gain 50%" claim follows from the cohort.
- Holdouts must preserve point-in-time identity and corporate actions. Financial/lending names require distinct fundamental/accounting models, rather than misusing industrial EV/EBITDA.
- Industry exposure and market-cap distribution are descriptive only until an original *historical* sector/size mapping is verified.
- No named-company promotion to investment eligibility or capital deployment without a separate original-source economic underwriting and realistic execution cost challenge.

## Reproduction

The canonical original frozen 2,319-row HG001 router is archived in research/hg009/original-hg001-d001-router-20261005.json.gz, downloaded once from its exact pinned October 5 workflow, not from a later workflow rerun.

The 100-company result is research/hg009/hg009-d001-100-experimental-companies-v1.json. Validate both with:

    python scripts/materialize_hg009_100.py --check
    pytest -q tests/test_hg009_100.py

The generation pipeline originally downloads the exact pinned GitHub Actions artifact, verifies the HG001 source SHA and raw source bytes, creates immutable source and selection files, and validates the same outputs before committing them.

**Next scientific stage:** prospectively log source-available earnings and capital-allocation changes across these 100 versus unselected but same-date baseline NSE names. Rank investment theses only after confidence-calibrated valuation, scenario probability, execution costs and forward performance are established. This cohort is the controlled *starting population* for that experiment, not its answer.
