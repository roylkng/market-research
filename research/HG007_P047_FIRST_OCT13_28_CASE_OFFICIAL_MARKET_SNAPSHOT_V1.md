# HG007-P047: First 13 October Official NSE Session Snapshot for All 28 Hidden-Gem Cases

Established **13 October 2026, after the completed Indian cash-market session**.
This is a **source-only descriptive market observation**, not an investable
ranking, an earnings model, a prospective alpha discovery trial or proof of
trade execution.

## Exact original source, no new vendor

H021-P008 automatically collected the **entire official NSE cash-equity
UDiFF ZIP** on 13 October, and independently captured the official Nifty 500
index report. HG007-P047 reuses that identical original whole-market ZIP;
there is no new network request or alternate third-party price.

- Session: 2026-10-13 (completed Indian exchange session).
- NSE ZIP: BhavCopy_NSE_CM_0_0_0_20261013_F_0000.csv.zip.
- Original SHA-256:
  b3aba7f1e20587e4c77a5de2b720cbcd5d8f4c8fe42e1b67f06f0d7deaabbf46
- Original retained bytes: 204601.
- Frozen H021 13 Oct daily packet Git blob:
  a0aad217d171313426e00af6d234d5df02a45395
- Prior completed EQ-session history through 9 Oct: HG007-P041.
- Original 28-company current stage: HG007-P046, including
  the separately documented 9 October Vibhav 75/25 subsidiary
  equity allotment and the still-open WWIL BTA legal-close question.

Every source Git blob and original ZIP SHA is verified before a market
price or volume is processed. All 10 overlapping H021 study-company
rows are independently reconciled to the same official 13 October NSE
market file; this is a transport/source verification, not a merger of
the separate stock-selection universes.

## Scientific and exchange identity rules

All 28 original, mechanically selected HG002 companies remain present,
including those with incomplete historical EQ series.

Each company is tied to a single official historical NSE ISIN from the
original 20-session P041 source, not an inferred ticker/string alias.

- If **exactly one** currently observed NSE cash-market EQ row has
  that same ISIN and valid positive OHLC/volume/traded-value, store
  the observed official open/high/low/close, volume, cash traded
  value and executed transaction count.
- If an exact issuer appears only in **BE or other non-EQ series**,
  describe the exchange series but do not represent it as an EQ
  price, eligible execution venue or missing zero turnover.
- Changed ISIN, duplicate EQ rows, malformed fields or empty source
  remains **BLOCKED**. Never fill from a later date, alternate ticker,
  vendor or an unrelated derivative contract.

For an original P041 company with **all 20 prior EQ sessions
complete**, show the ratio of one 13 October traded value to the
*historical* 20-session median. This ratio describes source liquidity
only, not future liquidity, an order-book fill, expected stock return,
margin of safety, or reliable statistical anomaly.

## The original 28-company investment-thesis context is preserved

The five primary financially underwritten names:
ANANTRAJ, DEVX, INOXGREEN, NPST and SAMBHV, retain their
source-specified business/capital blockers and observed cash turnover.

In particular:

- INOXGREEN's **7 October WWIL payment** is not proof the O&M BTA
  completed; **9 October VEPL 75/25 equity conversion** is separate.
- INOXGREEN's historical March-2026 fully diluted value
  must not replace the first-public September-29 source or current
  October fully diluted equity; no current market capitalization
  is inferred from a bare close.
- DEVX post-rent lease cash earnings, NPST recurring EBITDA, SAMBHV
  power-plus-steel capacity economics, ANANTRAJ demerger liabilities,
  and INOXGREEN WWIL normalized cash flow remain separate studies.

The file cannot rank stocks by expected upside merely because some
display high recent trading value or price movement. No 50%-annualized
return or individual stock expected return is produced.

## Reproducible code and evidence

- Module: src/marketlab/hg007_oct13_28_snapshot.py
- CLI: scripts/build_hg007_oct13_28_snapshot.py
- Tests: tests/test_hg007_oct13_28_snapshot.py
- Workflow: .github/workflows/hg007-oct13-28-source-snapshot.yml
- Immutable result after reviewed main merge:
  research/hg007/hg007-p047-oct13-28-official-nse-source-v1.json

Run fully offline against the Git-retained original sources:

    python scripts/build_hg007_oct13_28_snapshot.py \
      --out /tmp/hg007-oct13-official-28-market.json

To detect any drift from frozen originals:

    python scripts/build_hg007_oct13_28_snapshot.py \
      --out /tmp/hg007-oct13-official-28-market.json \
      --verify-existing

## Remaining blockers

Even a valid EQ price observation does **not** establish:

- available bid/ask spread, market depth, intraday time-of-decision,
  auction participation, fill at the open or a safe position size;
- current fully diluted share count, share actions, dividends or a
  post-transaction parent-attributable enterprise value;
- normalized business free cash flows, legally completed corporate
  events, independently calibrated case completion probabilities;
- matured holding-period returns and a causal or statistically robust
  market-beating investment edge.

Only the actual 13 October completed cash-market source is examined.
All portfolio/trading and live capital permissions remain FALSE.
