# HG009 P032: official NSE Total Market index industry source

**Method date:** October 21, 2026. **Scope:** supplemental original NSE industry data for a future independently registered Indian-equity study.

NSE's official [Nifty Total Market Index](https://www.nseindia.com/static/products-services/indices-nifty-total-market-index) describes an index of 750 equities combining Nifty 500 and Nifty Microcap 250. The official constituent CSV:

https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv

This can independently identify some sectors when the company-specific quote API denies access from cloud runners. It is **not** full-market coverage of 2,319 symbols nor a complete four-tier issuer industry record. The official index is reviewed semiannually. Thus the downloaded file is a dated original-source receipt, not a historic classification.

## Protocol and limitations

1. Download only the original official CSV, whitelist the NSE archive host, retain exact original bytes, SHA-256, observed retrieval UTC timestamp and signed replayable receipt.
2. Validate exact official columns, symbol, original ISIN and NSE EQ series. Require a unique valid industry for every issuer, and 650 to 800 constituent names as a source sanity check. Any unexpected schema or response remains blocked.
3. Join to all 300 frozen selected, one- and zero-lane identities from October 5 source. Retain unmatched issuers as missing, without assigning guessed industries.
4. Use the published one-level industry only. Do not infer macro sector, revenue mix, additional tiers or an exact company industry from the issuer name.
5. Under no circumstances retrofit October 21 retrieved industry labels into the original October 15 outcome experiment.
6. Before a new trial, require >=90/arm and >=285/300 verified industry coverage, float/size, risk beta, accounting regime, corporate actions, financial sources, costs, and an independent freeze. This 750-name source alone may not suffice.

The individual NSE quote-equity path in P031 was tested October 21, but the GitHub runner recorded an access denial and verified zero four-tier issuer records. P032 tests a separately published static exchange report with a single request, not a rate-limit circumvention. If denied, publish an explicit failure and no sector classification.

Offline verification command: python scripts/capture_hg009_p032_totalmarket.py --check

No new investment recommendation, portfolio, causal alpha claim, or live order is authorized.
