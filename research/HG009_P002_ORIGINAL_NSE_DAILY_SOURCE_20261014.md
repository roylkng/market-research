# HG009-P002: prospective original NSE price-source observation for 300 frozen identities

**Protocol frozen:** 2026-10-14 before first planned 2026-10-15 NSE entry.  
**Prior source:** HG009 D001 100-company selection + HG009 P001 100 zero- and 100 one-signal comparison identities, permanently source hashed and remotely sealed.  
**Market-data basis:** original official NSE daily UDiFF EQ and Nifty 500 **price-index** files.  
**Capital:** disabled. No implied or executed position.

## First-principles purpose

The discovery experiment has a frozen source-blind, outcome-blind selected cohort and source-band-matched comparisons. Its effectiveness cannot be evaluated from candidate flags. P002 establishes **post-freeze original-source prices** with exact equity symbol/ISIN identity and missing data counts, without opening return labels prematurely.

Do **not** download 300 unverified web prices or replace original NSE stock data with current quote screenshots.

The H021 P008 workflow already obtains and anchors the *whole-market* original NSE cash UDiFF ZIP and Nifty 500 CSV, and independently records their actual UTC retrieval timestamps. Those originals are reusable for other experiments even if one of H021's first ten companies is unpriceable. HG009 P002 consumes that same immutable source under research/prospective/h021/daily-prices and independently reparses all full-market EQ rows and the index.

### Binding requirements

1. Accept only the original HG009 selected SHA e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5 and P001 matched controls SHA 8c8d9781adf7900addd28a1a60f1cfb33bed9a1e4985e6c410a010d2c819eef8. Validate the **entire 2,319-name original October 5 HG001** source, not just the manifest field text.
2. The first eligible market observation is **2026-10-15 official NSE cash session**, with date and close proved against the original frozen exchange calendar SHA 2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce.
3. Both original H021 NSE cash ZIP and Nifty 500 price-index CSV must be available and hash verified, with original actual retrieval timestamps after that session's 15:30 IST close and the derivative source observation after both. Original H021 record must itself be hash-verified and structurally valid.
4. Parse **all official NSE CM-STK-EQ identities**, refuse duplicate symbol/ISIN ambiguity, and join strictly on both frozen symbol and frozen ISIN. If a share migrates to a different ISIN, ticker, off-EQ BE category, suspends, disappears, or has multiple source EQ identities, the frozen slot stays **missing** until original issuer corporate-action evidence proves treatment. There are always **300 slots**, regardless of eligible prices.
5. A snapshot for a date is signed and retained once. Any later source correction creates a separately versioned research protocol, not a silent rewrite. If H021 original sources are late, retain their true timestamp. The **cohort selection was already sealed**, so delayed outcome-source receipt must not be disguised as a pre-entry "decision".
6. The recorded OHLC is official unadjusted price. Volume and turnover do not establish order-book depth or executable ticket size. Benchmark is Nifty 500 price index, NOT total-return index. Original H021 raw bytes stay under existing source paths and are not needlessly duplicated.

### Prospective collection

A derived-price workflow follows new H021 source files on main, H021 workflow completion, and late evening schedule. A date is processed **only when both original full-market source files have been anchored**. The resolver selects the earliest ready but not yet sealed date rather than blocking all later sessions behind a missing historical source. Gaps remain visible in the run summary. Run:

    python scripts/materialize_hg009_daily.py
    python scripts/verify_hg009_daily.py

The first command makes one new immutable session record under research/hg009/daily if source is available and original; the second independently replays every retained daily record against H021's original full-market ZIP/CSV, frozen 300 identities, date/ISIN, original timestamps and source hash. Both are source-only operations.

### Hard stop on returns

P002 does not yet calculate gross open-to-close, 1/5/20/60-session returns, index excess, dividends, splits, rights, share transfers, slippage, costs, or fills.

Future return evaluation must separately:
- identify the frozen **first-entry** official open and the exact NSE holding-session close, with the entry counted as holding session one;
- preserve missingness and stock/ISIN changes in the 100-name denominator of each arm, not quietly drop losers or suspended stocks;
- resolve the **unconfirmed November 8, 2026 Muhurat special session** before claiming a holding horizon that crosses it;
- after the original 2026 calendar ends, freeze official 2027 calendar evidence **prospectively**, without altering 2026 session chronology;
- source corporate actions and dividends for equity-share-basis comparability and use a price-only index in comparable price-only calculations;
- separately challenge performance under sector, financial-accounting, size, style and execution costs and replicate across independent future cohorts.

Only then can the 100-name experiment begin to answer whether systematic evidence-lane convergence matters for subsequent Indian share prices. Source custody is necessary, not sufficient for a validated alpha strategy.
