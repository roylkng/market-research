# H019 source audit v2 — official annual reports and survivorship

Recorded: 2026-09-09

Status: **SOURCE FEASIBILITY ONLY. NO H019 SCORE, PRICE RANK, OR INVESTMENT OUTCOME MAY BE COMPUTED. LIVE CAPITAL DISABLED.**

## Why v2 exists

The first H019 source audit established that the legacy annual-result interface has abundant historical listing metadata, but its directly linked financial-result XBRL files are primarily income-statement disclosures. They do not provide sufficiently broad balance-sheet and cash-flow coverage for a long-horizon quality-plus-inflection hypothesis.

The first audit also under-detected several XBRL concepts because taxonomy names differ from simplified English labels. In particular, EPS appears under `BasicEarningsLossPerShare...` style concepts. Therefore H019 must not shrink its design based on the first lexical scanner alone.

NSE also exposes an official annual-report API whose records point to exact exchange-hosted annual-report documents. This audit tests whether that source can provide the longer historical and full-statement coverage H019 needs.

## Frozen survivorship test

Use the legacy NSE annual financial-result listings for calendar years 2018 and 2020 only to define historical symbol sets. Do not use current-index membership or current exchange lists.

Construct two deterministic groups from 2018 symbols:

1. `SURVIVOR_PROXY`: symbols present in both the 2018 and 2020 annual-result listing sets.
2. `EXIT_PROXY`: symbols present in 2018 but absent from the 2020 annual-result listing set.

Sort each symbol set lexicographically and choose a deterministic evenly spaced sample of up to 40 symbols per group. No accounting value, price, later return, company reputation, or source success may affect sample membership.

For each sampled symbol, query only the official NSE annual-report API:

`/api/annual-reports?index=equities&symbol=<SYMBOL>`

Retain the exact API response bytes and SHA-256. Measure whether historical report records remain discoverable for both groups. A strong difference between survivor and exit proxies is evidence that the current API cannot be used naively for historical cross-sectional reconstruction.

## Historical depth audit

For every valid annual-report record returned for sampled historical symbols, retain:

- company name,
- `fromYr` / `toYr`,
- historical broadcast/dissemination timestamp,
- exact exchange-hosted `fileName`,
- response source hash.

Report, separately by sample group, the fraction of symbols with at least 1, 3 and 5 annual-report records whose broadcast timestamp is on or before these frozen cutoffs:

- 2018-10-01 00:00 Asia/Kolkata,
- 2019-10-01 00:00 Asia/Kolkata,
- 2020-10-01 00:00 Asia/Kolkata.

These are source-availability cutoffs only. They are not H019 portfolio decision dates yet.

## Full-statement content audit

After API metadata is collected, choose source documents deterministically and independently of their contents:

- up to 6 symbols from `SURVIVOR_PROXY` with a valid report whose `toYr` is closest to 2018 without exceeding 2020;
- up to 6 symbols from `EXIT_PROXY` under the same rule.

Choose symbols lexicographically from the API-success subset. For each chosen symbol choose the report minimizing `(abs(toYr - 2018), toYr, fileName)` subject to `2016 <= toYr <= 2020`.

Download only the exact official archive URL supplied by NSE. Retain original bytes and SHA-256. A ZIP may be opened only when it contains exactly one PDF candidate. PDFs are parsed with text extraction only. No OCR is permitted.

The content audit records whether the extracted report text contains recognizable disclosure labels for:

- revenue / total income,
- profit after tax,
- basic or diluted EPS,
- total assets,
- total equity / net worth,
- borrowings / debt,
- cash flow from operating activities,
- property, plant and equipment / capital expenditure,
- ROE / return on equity,
- ROCE / return on capital employed.

This audit checks disclosure availability, not numerical extraction correctness.

## Decision rule

Do not freeze an H019-v1 investment score until this audit is complete.

The preferred H019 architecture remains non-financial company-year selection using multi-year business economics. A plain quality baseline must remain separate from the candidate inflection signal. If historical annual-report retrieval shows material survivorship bias or full-statement extraction is too sparse, redesign the data layer before defining H019-v1. Do not compensate by choosing only companies or fields that happened to be easy to retrieve.
