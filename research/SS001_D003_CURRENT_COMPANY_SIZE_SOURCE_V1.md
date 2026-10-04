# SS001-D003 Current NSE Company-Size Source v1

Status: **FROZEN BEFORE SOURCE DIAGNOSTIC**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Objective

Attach official current total-market-cap and free-float-market-cap context to the full
2,319-name SS001-D001 NSE EQ census.

D003 exists because the Small-Sum Alpha program must distinguish genuinely small listed
companies from merely illiquid or non-index companies. Company size is source context,
not an expected-return signal.

## Frozen universe

Use exactly SS001-D001:

- run: `37197575401`;
- artifact: `11301695772`;
- census SHA-256:
  `0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7`;
- current NSE EQ identity count: 2,319.

No symbol may be added or removed based on size.

## Official source

For each frozen current symbol query official NSE equity quote trade information:

`https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>&section=trade_info`

The NSE quote UI labels the corresponding fields:

- Total Market Cap (INR Cr.);
- Free Float Market Cap (INR Cr.).

D003 therefore interprets:

- `marketDeptOrderBook.tradeInfo.totalMarketCap` as INR crore;
- `marketDeptOrderBook.tradeInfo.ffmc` as INR crore.

The exact raw JSON bytes are retained and SHA-256 hashed per symbol.

## Frozen validation

A source row is READY only when:

1. the requested symbol is one of the exact frozen SS001-D001 identities;
2. `totalMarketCap` is finite and strictly positive;
3. `ffmc` is finite and nonnegative;
4. `ffmc <= totalMarketCap * 1.01`.

No missing market cap is imputed.

D003 does not infer shares outstanding.

## Descriptive size bands

For reporting/search routing only:

- `S1_BELOW_500CR`: total market cap < INR 500 crore;
- `S2_500_TO_1000CR`: INR 500 crore <= cap < INR 1,000 crore;
- `S3_1000_TO_2500CR`: INR 1,000 crore <= cap < INR 2,500 crore;
- `S4_2500_TO_5000CR`: INR 2,500 crore <= cap < INR 5,000 crore;
- `S5_5000_TO_10000CR`: INR 5,000 crore <= cap < INR 10,000 crore;
- `S6_10000_TO_25000CR`: INR 10,000 crore <= cap < INR 25,000 crore;
- `S7_25000CR_PLUS`: cap >= INR 25,000 crore;
- `SIZE_UNAVAILABLE`: source not READY.

These bands are not alpha ranks.

## Search context

D003 reports:

- count in every size band;
- count outside existing U001 in every size band;
- liquidity-band cross-tab when SS001-I001 context is available;
- integrated-financial-source coverage by size band;
- special-action presence by size band.

No band is excluded from SS001 discovery.

## Frozen feasibility gates

D003 passes only if:

1. all 2,319 frozen identities are accounted for exactly once;
2. at least 90% have READY total market cap;
3. at least 90% of non-U001 identities have READY total market cap;
4. all READY rows satisfy the FFMC <= total-market-cap tolerance.

Thresholds may not be lowered after diagnostic output is opened.

## Promotion

Passing D003 permits company-size-aware research routing, including explicit searches for
neglected INR 500-10,000 crore situations.

It does not authorize a small-cap alpha score.

## Scientific boundary

D003 does not:

- claim smaller companies outperform;
- rank names by market cap;
- use returns;
- infer intrinsic value;
- create ADO/PF001 eligibility;
- authorize live capital.
