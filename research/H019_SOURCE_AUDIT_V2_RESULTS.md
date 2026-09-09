# H019 source audit v2 results — official annual reports

Recorded: 2026-09-09

Evidence: GitHub Actions run `34352537129`, artifact `h019-annual-report-source-audit-34352537129`, artifact SHA-256 `37aeda56b72b34a74f599ecfbd78a94a68de41d61ff3b96da27dcc8695ecb621`.

Status: **SOURCE ARCHITECTURE VIABLE. H019 INVESTMENT SCORE NOT YET FROZEN. NO MARKET OUTCOMES OPENED. LIVE CAPITAL DISABLED.**

## 1. Survivorship/access audit

Historical symbol populations were defined from legacy NSE annual-result listings rather than today's index membership:

- 2018 annual-listing symbols: 1,610
- 2020 annual-listing symbols: 1,613
- survivor proxy, present in both: 1,486
- exit proxy, present in 2018 but absent in 2020: 124

A deterministic 40-symbol sample was taken from each group before annual-report API success was known.

Official NSE annual-report API retrieval succeeded for **40/40 survivor-proxy symbols and 40/40 exit-proxy symbols**.

Point-in-time report depth at the frozen 2018-10-01 cutoff:

| group | >=1 report | >=3 reports | >=5 reports | max depth |
|---|---:|---:|---:|---:|
| Survivor proxy | 40/40 | 35/40 | 29/40 | 7 |
| Exit proxy | 40/40 | 35/40 | 24/40 | 6 |

At the 2019-10-01 cutoff, both groups had 37/40 symbols with at least three reports. Five-report depth was 31/40 survivors versus 29/40 exits.

At the 2020-10-01 cutoff, both groups again had 37/40 with at least three reports. Five-report depth was 32/40 survivors versus 29/40 exits.

### Interpretation

The audit finds **no evidence that the current official annual-report API simply excludes historical exit-proxy companies**. Three-report point-in-time depth is essentially identical in the two groups. Five-report depth is somewhat stronger among survivors, so a mandatory five-year history would impose avoidable historical coverage pressure.

**Source-driven design decision:** default H019 history depth should be three annual reports, not five, unless a later pre-outcome coverage audit demonstrates that a five-year requirement is neutral. Five-year quality may remain a comparator on the evaluable subset, but should not define H019-v1 eligibility.

## 2. Full-statement content audit

Twelve annual reports were selected deterministically, six per historical-symbol group. All 12 official archive documents downloaded successfully and all 12 PDFs were text-parseable without OCR.

Disclosure-label coverage among text-parseable reports:

| field family | Survivor proxy | Exit proxy |
|---|---:|---:|
| Revenue / total income | 6/6 | 4/6 |
| Profit after tax | 6/6 | 5/6 |
| EPS | 5/6 | 4/6 |
| Total assets | 6/6 | 4/6 |
| Equity / net worth | 6/6 | 5/6 |
| Borrowings / debt | 6/6 | 5/6 |
| Operating cash flow | 6/6 | 4/6 |
| Capex / PPE purchase | 4/6 | 2/6 |
| Direct ROE label | 1/6 | 1/6 |
| Direct ROCE label | 0/6 | 1/6 |

One exit-proxy report was image/scanned in practical terms despite being a PDF: text extraction produced zero usable characters. This must remain a normal missing-data case. OCR is not silently introduced into the frozen data path.

### Interpretation

Annual reports materially improve on the historical financial-result XBRLs. They provide balance sheet and cash-flow disclosures broadly enough to justify the next source-validation stage.

Sparse direct ROE/ROCE labels are **not** grounds to abandon capital efficiency. H019 should calculate capital-efficiency measures from audited financial-statement components when those components can be extracted and cross-validated, rather than scrape company-reported ratios whose definitions may vary.

Capex is less consistently recoverable than operating cash flow. Free-cash-flow or reinvestment metrics therefore remain provisional until numeric extraction is validated.

## 3. Relationship to source audit v1

The first source audit established that historical result XBRLs are strong for income-statement concepts but weak for complete balance-sheet and cash-flow reconstruction. Its initial lexical scanner also under-detected taxonomy-specific labels such as `BasicEarningsLossPerShare...`.

The intended H019 source stack is therefore now:

1. **NSE historical annual-result/XBRL sources** for structured P&L facts where available.
2. **NSE annual reports** for multi-year full-statement history, balance sheet and cash flow.
3. Exact retained source bytes, URL, broadcast/publication timestamp and SHA-256 for every company-year used.
4. No current-index membership as a substitute for historical eligibility.

## 4. What is now allowed

The next experiment may validate deterministic **numeric extraction** from the frozen annual-report corpus. It may compare annual-report P&L values against independent NSE XBRL values for overlapping company-years and may use accounting identities and cross-year consistency checks.

It may **not** acquire historical market prices, rank companies, select winners, calculate future returns, or choose H019 feature weights based on performance.

## 5. H019 design constraints carried forward

The investment hypothesis is not yet frozen, but the source evidence now supports these pre-outcome constraints:

- unit of observation: company-year, not result event;
- primary universe: non-financial companies;
- default history depth: three annual reports;
- plain quality is a comparator, not the claimed edge;
- candidate edge must be an improvement/inflection in business economics plus valuation discipline, not another quarterly revenue/PAT-growth composite;
- direct reported ROE/ROCE is optional evidence, not a required input;
- missing or non-text reports fail closed for the affected metric/company-year rather than being filled from future data.

No market outcome has been opened in H019.
