# What the broader discovery pass actually covered

This is a dated attention review, not a new predictive model. The input is the retained CC001 financial export at commit `bed62144e1c8f0407113ecd19442a7a4c13c5aa6`, last evaluated on 8 November 2026. Every preferred-scope issuer was joined to the original 18 November NSE stock/EQ price file by exact symbol and ISIN.

- 196 retained issuers, all 196 matched to current prices.
- 192 have the expected April–September six-month cash period. Four quarterly/nine-month cases are now explicitly excluded from doubled-H1 arithmetic.
- 21 pass the initial cash/earnings/price attention rule. This does not mean 21 buy candidates.
- 2,756 distinct STK/EQ identities exist in the current price file. Receiving those prices does not mean their businesses were screened.
- The retained financial fields remain UNREVIEWED. An export hash is proof of input identity, not proof of correct financial meaning.

## Attention rule and actual buckets

Prefer consolidated scope. Route NBFC-template filings separately. Preserve existing source-reconciliation flags. For comparable six-month periods, require positive EPS and positive cash after specified capex, lease payments and financing interest. A price no more than 18 times doubled H1 EPS routes the name for source review. The multiple is a practical attention choice, not a validated return predictor or annual earnings forecast. No liquidity rejection is applied, but turnover is displayed.

| Bucket | Issuers |
|---|---:|
| Source reconciliation required | 66 |
| Cash after selected uses nonpositive | 56 |
| Above attention multiple | 25 |
| Original-document review queue | 21 |
| Sector-specific lens | 10 |
| EPS basis unresolved | 13 |
| Incomparable reporting period | 4 |
| Cash component incomplete | 1 |
| Total | 196 |

The 21 mechanical names are SADBHIN, SANDESH, KHAITANLTD, BCLIND, COSMOFIRST, GINNIFILA, KOTHARIPET, IFBAGRO, PETRONET, UFO, HYBRIDFIN, EPIGRAL, ANTELOPUS, JKPAPER, DATAMATICS, MOIL, SEAMECLTD, VRLLOG, SIGNPOST, HAPPSTMNDS and TRIDENT. Their initial order by the attention multiple is not a conviction or expected-return ranking. HYBRIDFIN requires a sector lens despite the source template, so industrial cash reasoning is not accepted automatically.

## Original checks that changed the analysis

**Cosmo First:** the original structured filing has interest and dividends swapped. The signed cash-flow statement records interest ₹74.14cr and dividends ₹10.38cr. Including the separate lease interest, actual cash after selected uses is ₹81.60cr, versus the raw screen's ₹145.36cr. All total cash equations can still balance despite the semantic error. The signed statement overrides the structured tags for the company valuation. See the Cosmo case and `primary_review_overrides.json`.

**Sandesh:** the original signed CFO contains a positive fair-value adjustment despite the gain described in the profit note. The investment roll-forward follows the opposite sign. The reported CFO of ₹354.5338cr cannot be used as recurring owner cash without resolving this. The asset-value case is assessed separately, without silently changing signed financials.

**Petronet:** the November call describes approximately ₹9,000cr FY2027 capex and a similar FY2028 level. The current earnings multiple cannot be read as a distributable cash yield. This was a preliminary original-call check, not a full priced underwriting. Source: https://nsearchives.nseindia.com/corporate/PETRONET_09112026165711_Intimationtranscript.pdf

**Datamatics:** the company-specific review replaces a doubled-H1 shortcut with an attributable, tax-normalized trailing cash bridge and a financing sensitivity. Its model does not use the broad export's cash-equivalent-only debt measure as net financial debt.

These targeted checks do not semantically certify the remaining 192 issuer cases. A coverage count must be accompanied by the depth of actual work.

## Reproduce

Retrieve the immutable source export from:

https://raw.githubusercontent.com/roylkng/market-research/bed62144e1c8f0407113ecd19442a7a4c13c5aa6/cash-underwriting.json

Retrieve the dated original price ZIP from the URL in `nse_20261118_manifest.json`. The user evidence bundle contains both bytes. Then run:

```bash
python3 reproduce_breadth_review.py --financial cash-underwriting.json --prices nse_20261118.zip --output breadth_review_reproduced.json
```

The script verifies both input hashes, date and identity uniqueness. It writes a separate report. It does not modify the source exporter, the production queue, a frozen hypothesis or a portfolio policy. `primary_review_overrides.json` is an explicit additional research layer, not a hidden change to raw data.
