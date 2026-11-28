# 28 November 2026: twelve additional prospective earnings forecasts

## Decision and coverage

The fixed 100-company cohort now has **15 company-specific forecasts**, up from three. This dated supplement adds 12 of 12 predetermined attempts, with zero replacements and zero abstentions. All 12 have signed current and prior financial tables reviewed at the matching accounting scope. The separate four-company pilot remains separate. No target-quarter outcomes exist yet.

**Target:** first reported quarterly PAT for 31 December 2026, in INR crore. Eleven cases use consolidated PAT attributable to owners. KOTHARIPET uses standalone PAT. This is a within-quarter forecast recorded at 28 November 2026, 01:23:02 IST, not a quarter-start prediction.

**Investment status:** this is a research-accuracy experiment. It does not promote any company to BUY, update old entry prices, establish stock-return skill or alter a funded investment case. Prior decisions and frozen protocols retain their dated status.

## The twelve forecasts

| Company | Latest Sep PAT | Raw seasonal | Adjusted seasonal | Assisted base | Adverse | Favorable |
|---|---:|---:|---:|---:|---:|---:|
| [SIGMA](cases/SIGMA.md) | 6.83 | 6.86 | 6.86 | **6.65** | 4.90 | 8.05 |
| [HLEGLAS](cases/HLEGLAS.md) | 14.31 | 5.15 | 5.15 | **16.27** | 8.61 | 23.95 |
| [JAYBARMARU](cases/JAYBARMARU.md) | 32.01 | 31.95 | 31.95 | **29.81** | 16.44 | 43.48 |
| [NEULANDLAB](cases/NEULANDLAB.md) | 51.62 | -4.66 | -4.66 | **86.73** | 43.73 | 130.20 |
| [TATAINVEST](cases/TATAINVEST.md) | 115.92 | 43.15 | 43.15 | **41.77** | 15.33 | 77.74 |
| [DEVYANI](cases/DEVYANI.md) | -0.24 | 11.26 | 26.90 | **12.72** | -8.65 | 24.05 |
| [THOMASCOOK](cases/THOMASCOOK.md) | 51.67 | 26.93 | 65.74 | **68.33** | 35.43 | 91.95 |
| [BALAMINES](cases/BALAMINES.md) | 67.27 | 64.14 | 64.14 | **67.08** | 48.19 | 82.41 |
| [GRANULES](cases/GRANULES.md) | 181.84 | 201.44 | 201.44 | **184.71** | 145.04 | 213.00 |
| [KOTHARIPET](cases/KOTHARIPET.md) | 19.53 | 19.81 | 19.81 | **18.32** | 14.69 | 21.75 |
| [PETRONET](cases/PETRONET.md) | 1,256.43 | 1,295.74 | 1,314.78 | **1,098.70** | 305.42 | 1,300.18 |
| [AVONMORE](cases/AVONMORE.md) | 7.57 | 12.34 | 12.34 | **8.12** | 0.14 | 13.84 |

All values are INR crore. Raw additive seasonality is `current Sep + prior Dec - prior Sep`. Adjusted additive seasonality uses the same formula after explicit historical adjustments. The latter is not judgment-free. Scenario values are assumption sensitivities with no assigned probabilities and no prediction-interval coverage claim. Actuals can fall outside them.

## What the additional research changes

- **Tata Investment:** September dividend income is not a sound December run rate. Prior December dividends were 13.21cr versus 116.44cr in the preceding September quarter. The model uses 14cr dividends, zero net P&L fair-value gain and 31cr after-tax associates. It produces 41.77cr, close to the raw additive baseline of 43.15cr. OCI and gains credited directly to retained earnings are outside the PAT target. Sources and assumptions: [case](cases/TATAINVEST.md).
- **Petronet:** management identifies aggregate commercial/operational efficiency gains of 658cr, versus 494cr in Q1 and 41cr in prior Q2. Management did not isolate the basket into trading, inventory and operational components. The model uses 450cr and treats the 625.42cr unprovided vessel claim as a separate adverse sensitivity, not an established liability. Sources and assumptions: [case](cases/PETRONET.md).
- **HLE and Neuland:** a single prior December is a weak seasonal anchor when order conversion or commercial shipments are lumpy. Their forecasts depart meaningfully from simple additive seasonality. That is a testable hypothesis, not evidence that the models are better. HLE’s November order extends through November 2028 and receives no assumed immediate December revenue. Sources: [HLE](cases/HLEGLAS.md), [Neuland](cases/NEULANDLAB.md).
- **Balaji and Granules:** do not confuse revenue growth with volume growth or capacity announcements with current earnings. Balaji’s disclosed volume fell year on year. Granules retains input/logistics pressure and peptide losses in the operating assumptions. Sources: [Balaji](cases/BALAMINES.md), [Granules](cases/GRANULES.md).
- **Thomas Cook and Kothari:** more detail does not necessarily change the estimate. Thomas Cook’s 68.33cr is close to adjusted seasonal ratio around 66.60cr. Kothari’s 18.315cr almost equals its 18.27785cr two-quarter mean. Research may improve explanation without improving the point forecast. Sources: [Thomas Cook](cases/THOMASCOOK.md), [Kothari](cases/KOTHARIPET.md).
- **Owner attribution:** Devyani has positive group PAT but negative owner PAT in Q2. Avonmore and HLE also have material NCI. Jay Bharat Maruti separates government incentives from manufacturing EBIT and adds the after-tax JV contribution once. These distinctions prevent scope errors, but do not themselves establish forward accuracy.

## Source corrections are separate from forecast skill

| Item | Frozen extraction | Verified supplemental input | Effect |
|---|---|---|---|
| Neuland Q1 owner PAT | 147.6711cr | 147.6731cr | +0.002cr source correction |
| Neuland Q2 owner PAT | 51.6270cr | 51.6250cr | -0.002cr source correction |
| Kothari Q1 standalone PAT | 17.0248cr, derived from half-year | 17.0247cr, direct quarterly line | -0.0001cr rounding correction |
| Sigma NCI | Positive Q1/Q2 signs | Negative 0.0003/0.0005cr | Owner PAT already correct |
| Sigma Q2 tax bridge | Current plus deferred tax only | Includes prior-period tax 0.1167cr | Explains reconciliation difference |

No current PAT difference exceeds the original experiment’s bridge tolerance. The original register is retained byte-for-byte. Its Git blob is `baaf66ffe9a07933cfc46d51a0918dff535741a8`, and the enforced SHA256 is `be7769872a5260c3878e6bdabc4225bf59beca7aae61647c8dca4c852c6e600a`. These are dated supplemental corrections.

## Comparison protocol

Selection was fixed before the new source review: the first 12 original selected-roster rows in ascending original ISIN-hash rank without a prior assisted forecast. [selection.json](selection.json) preserves the exact names, ranks and no-replacement rule. The universe itself came from a selected acquisition process and is not representative of all listed Indian companies.

The primary comparison is assisted versus **normalized additive seasonality**. Always show **raw additive seasonality** alongside it. Additional same-information comparators are latest verified quarter, two-quarter mean, 25% damped sequential trend, seasonal naive and eligible raw/normalized YoY ratios. The ratio benchmark is unavailable when the prior September denominator is below the fixed positive 1cr floor. Devyani’s negative base therefore does not produce a misleading multiplicative forecast.

Historical adjustments for Devyani, Thomas Cook and Petronet contain explicit tax and sometimes owner-allocation assumptions. Thomas Cook’s prior property-sale post-tax gain is disclosed. HLE and Jay Bharat Maruti keep the uncertain labour/acquisition addbacks out of the main normalization and show separate sensitivities. Never label the normalized benchmark entirely objective.

Compare forecasts on identical observed issuer rows. The error scale remains the frozen `max(1, abs(Jun PAT), abs(Sep PAT))`, even where small input errors are corrected. Report mean scaled absolute error, paired improvement, signed bias and win/tie/loss counts together with available, observed and missing counts. No result is currently mature, so every skill metric is null.

Older frozen forecasts remain a separately labeled comparison because the information cutoff differs. A benefit from updating evidence is not automatically a benefit from reasoning. The supplement is also not a blinded comparison between models or humans.

### Outcome handling

Use the first quarterly release at the selected identity, unit and accounting target. Preserve the first version rather than replacing it with a favorable restatement. Record publication date, review time and source URL, and retain source bytes. If a merger or demerger changes the group perimeter but the same issuer and target still report a figure, score that reported figure and flag the structural change separately. Do not exclude a difficult case after results. If no matching issuer/target genuinely exists, retain the attempted row as unavailable with an explicit reason. Never silently substitute pro-forma, standalone or total-group figures.

The scorer validates calendar dates and chronological order. It cannot authenticate a financial source from a URL. Human source review and scope reconciliation remain required. The frozen original scorer accepted invalid/future synthetic dates. That limitation is documented, while stricter validation is added only in this supplement.

## Evidence and verification

The [evidence manifest](evidence_manifest.json) maps **35 unique documents: 33 PDFs and two exchange HTML filings**, totaling 151,713,200 original bytes. Original financial tables were visually reviewed. Supporting transcripts/decks are marked as issuer commentary and do not prove future outcomes. Granules’ prior signed PDF was captured through a mirror and its owner-PAT row was separately corroborated in the exchange filing. HLE’s current primary-host file matches its mirrored signed copy byte-for-byte.

The portable source archive is `forecast-evidence-2026-11-28.zip`, SHA256 `cb4270a41f6913155305753f1c74e044fdae862ab1add66f86dba35839d48471`. It contains originals, a portable manifest and a readme. Large binaries are delivered separately rather than added to the source repository. Case JSONs retain capture receipts and source locators. Local paths describe the acquisition session, while the manifest provides portable archive paths.

[audit.md](audit.md) records independent verification. All 12 base forecasts and 36 scenarios reproduce. The evaluator has targeted synthetic checks for identity/scope, missingness, chronology, source-pinning and scenario consistency. The original 100 baselines and three assisted forecasts also reproduced unchanged. These checks validate arithmetic and custody, not investment alpha.

## Reproduce

```bash
python3 research/integrated/forecast-supplement-2026-11-28/calculate.py
python3 -m unittest discover -s research/integrated/forecast-supplement-2026-11-28 -p test_calculate.py
```

[forecast_register.json](forecast_register.json) contains the complete cases and protocol. [scorecard.json](scorecard.json) contains all current comparator values and null outcomes. [forecasts.csv](forecasts.csv) is a compact numeric export. [assemble.py](assemble.py) rebuilds the register and derived outputs from the case files while reusing the recorded cutoff. Do not regenerate or edit a published forecast for later scoring. New views must be separately dated.

The visual brief can be regenerated with ReportLab and DejaVu Sans installed:

```bash
python3 research/integrated/forecast-supplement-2026-11-28/build_report.py --output /tmp/forecast-brief-2026-11-28.pdf
```

Later, after the first release has been independently reviewed, evaluate an actuals JSON array with an explicit as-of timestamp:

```bash
python3 research/integrated/forecast-supplement-2026-11-28/calculate.py actuals.json --as-of 2027-02-28T18:00:00Z
```

The example date is an evaluation-interface example, not a scheduled task or a claim that outcomes have been observed. Every actual row requires symbol, ISIN, scope, target, period end, INR_CRORE unit, actual PAT, first-release date, source URL, reviewed timestamp and the reviewed-first-release status. See the evaluator docstring.

## What remains to establish an edge

The next decisive evidence is first reported December results. Subsequent dated cohorts across different quarters are needed to distinguish repeatable forecasting value from one shared business cycle. Earnings accuracy alone still does not establish attractive entry prices, cash conversion, portfolio suitability or stock-return alpha. Prior priced investment work remains the relevant basis for any investment decision.
