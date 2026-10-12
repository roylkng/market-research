# H021-P017: Exact First Entry OHLC and Source Measurement Caveats

Protocol/analysis created 12 October 2026 **after the trading session close**.
This is a post-entry **measurement diagnostic**, not a change to the
prospectively frozen October 9 top-decile stock selection.

## Exact source chain

- Original Oct 9 H021 P003 first-cohort intent was frozen before the Oct12
  09:15 IST market open. H021 selected 10/97 covered members of the
  originally frozen 100-company U001.
- Original P004 first attempt: 12 October approximately **17:33 IST**,
  run **38246531921-1**. Official NSE CM UDiFF ZIP source
  SHA-256 **818f673b3cdb96ae8ec4e466c7c4fd3a28d035482173a675dd24f9437a3ecd99**.
  All 10 original EQ symbol/ISIN rows and opens were present.
- The official Nifty 500 daily-index CSV was **HTTP 404 at the first
  attempt**, not represented as zero or substituted from another vendor.
  A later source attempt may find it. Original first-attempt packet SHA:
  **c314c0f001476f9ff221ca5055fb6b185702f862d4a455c5f0bb0e2f151dacbd**.
- H021 P016 independently reproduced and sealed the *partial* packet
  from the actual source ZIP, source receipts and original frozen intent.
  The P017 study revalidates this packet's canonical content digest.

## Verified after-close observation, not a trade

| Original selected NSE symbol | Official 12 Oct open (₹) |
|---|---:|
| VEDL | 265.95 |
| ETERNAL | 325.75 |
| DMART | 3,407.00 |
| IDEA | 13.02 |
| ADANIENSOL | 1,274.90 |
| JSWSTEEL | 1,174.00 |
| COALINDIA | 413.05 |
| INFY | 1,029.30 |
| GAIL | 167.75 |
| POWERGRID | 250.90 |

All ten are original exchange *after-close* observations of the planned
next-session opening proxy. They are **not** proof a broker could buy at
those prices, before or after the 09:15 auction. This overlay includes no
portfolio fills, allocation or 20/60-session investment returns.

## Two distinct original-cohort measurement warnings

### IDEA: frozen EPS revision has reversed economic direction

The original P007 September/October consensus source showed:

- Prior EPS: **-₹1.73**
- Current EPS: **-₹1.81**
- Original H021 score: **+4.624277%**
- Actual signed EPS change: **-₹0.08** (expected loss *worsens*).

The algebraically frozen ratio divides by negative prior EPS. That
changes the economic direction of the sign. IDEA remains in the
prospective selection, because removing it post-selection would make
H021 a different, retrospectively optimized test.

### VEDL: known pre-entry dividend on the measurement horizon

The issuer announced an **₹5 per share dividend** publicly on Oct 8,
with an **Oct 14 issuer-reported record date**. Original NSE dividend
PDF SHA-256:
**abdd026339469b9e51ab75fb2a37551be23812dcc037c875759cd79a8e6cb364**.

Crucial dual-timestamp provenance: the issuer's source notice was
public before the Oct12 entry, but our original PDF was retrieved on
Oct12 *after* that opening session. Do not backdate the retrieval
or turn a later audit into proof of earlier execution.

₹5 divided by the official observed Oct12 VEDL open of ₹265.95 is
approximately **1.88% as a *cash-dividend/open-price magnitude***.
This is **not** a verified yield earned, actual price drop, or return.
The original board letter itself does not independently prove
the ex-date or that an imaginary entry buyer received and was paid
the dividend. Full company-action interval coverage for *all* ten
names is not complete.

Stock raw prices and Nifty500 **price index, not TRI** are different
economic return bases whenever dividends occur. A stock-versus-index
alpha claim cannot be opened without a separately precommitted and
consistent total-return/price-return policy.

## Falsifiability and hard restrictions

- Original top ten, analyst count threshold, EPS ratio formula and
  60/20-completed-session horizons remain unchanged.
- No actual broker fill, position, dividend receipt or exit date
  has been observed or invented.
- No later-session Nifty500 index value is backfilled into the
  original 17:33 first-attempt packet.
- Neither the Nov 8 Muhurat trading calendar ambiguity nor the
  missing verified 2027 NSE calendar has been resolved here.
- No performance, investment prediction, stock exclusion, capital
  eligibility or alpha significance is claimed.

## Reproduction

P017 source hashes and URL/ISIN/source timestamp checks:

- Model: src/marketlab/h021_first_measurement.py
- CLI: scripts/audit_h021_first_entry_measurement.py
- Regression: tests/test_h021_first_measurement.py
- Workflow: .github/workflows/h021-first-entry-measurement.yml
- Immutable after-merge evidence:
  research/prospective/h021/entry-observations/measurement-integrity-v1.json

Reproduce without calling any market service:

    python scripts/audit_h021_first_entry_measurement.py \
      --out /tmp/h021-original-entry-measurement.json

The recorded file is source-only, point-in-time and auditable, with
**live capital disabled**.
