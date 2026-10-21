# HG009 P034: official all-listed NSE security-master source feasibility

**Registered:** October 21, 2026. **Capital:** disabled. **Experiment:** original static NSE cash-market security master for October 21, not a stock recommendation.

## Why another source is needed

The original HG009 cohort contains 100 signal-selected names and 200 independent comparison names. P033 admitted 741 genuine original NSE Nifty Total Market EQ industry rows out of 755 reported constituents, with exact symbol+ISIN coverage **142/300**. Another **158 companies** remain unclassified, because the index subset does not cover the full NSE listings. All P033 industry evidence was first observed after the original October 15 entry, so no retrospective factor-label rewrite is allowed.

The NSE documents a daily **CM MII Security Master** covering all NSE listed securities at https://www.nseindia.com/all-reports. This is a distinct full-venue instrument master, not a 750-name index CSV. Official source targeted: https://nsearchives.nseindia.com/content/cm/NSE_CM_security_21102026.csv.gz.

The file MAY carry status, security series, issued capital and original symbol+ISIN. It MAY NOT carry four-tier industry, true free float, fully diluted current shares or actual bid/ask depth. Source rows and columns must be examined before making any claim.

## Fail-closed source experiment

1. Make one ordinary public HTTPS request without credentials, redirects or access circumvention. Record the actual first retrieval UTC; HTTP 403 or missing source is an explicit failed-source attempt, not an empty securities file.
2. Validate gzip and original CSV with real observed fieldnames and plausible file size and listed security count. Archive original compressed bytes under original SHA-256 and independently seal the decompressed SHA and actual retrieval receipt.
3. Recognize symbol, ISIN and optionally EQ series only when the ORIGINAL source uses an explicitly understood header alias. Keep all 300 research slots, and label missing/ambiguous/changed identities rather than substitute another stock.
4. Publish observed column names that resemble industry, public float, trade status or issued capital. A header observation is NOT proof of economically usable source values, four-tier NSE industry, unrestricted float-adjusted equity value or executable liquidity.
5. Replayer must reconstruct each original receipt from content-addressed original bytes, frozen group identity and actual capture timestamp; mutation, tampering and re-signing unsupported company classifications cannot retroactively change older decisions.
6. Do not merge these October 21 source fields into the earlier October 15 H1/H5 model. Any sector/float use is future-only and requires a NEW independent trial preregistered prior to its own entry.

NSE industry classifications are based on four levels, macro-economic sector, sector, industry and basic industry. A trading-master status code is not a substitute: https://www.nseindia.com/static/products-services/industry-classification

## Acceptance

The future experimental comparison remains blocked until >=285/300 independently sourced sectors/size and >=90/100 per arm, consistent accounting regimes, original full exchange share actions, volatility/momentum history, CASA status and net trading costs are evidenced **before the next independent entry**. No field name alone authorizes factor models or live capital. If the public MII file is inaccessible or industry-free, record that finding and abandon the assumption rather than silently fill 158 unknown sectors.

Scientific state: no verified after-cost alpha, no completed ten-company probability-weighted intrinsic values, no justified 50% annual-growth promise.
