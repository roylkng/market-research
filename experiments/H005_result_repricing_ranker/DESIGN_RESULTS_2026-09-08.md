# H005 source-complete design result

Recorded: 2026-09-08

Status: **REJECTED AT DESIGN GATE. HOLDOUT UNOPENED. LIVE CAPITAL DISABLED.**

This result uses only the 2025-10-01 through 2026-07-31 H005 design/training period reconstructed from retained NSE result filings, daily UDiFF EQ bars, Nifty 500 index snapshots and retained corporate-action data. It is not historical validation and does not open the frozen 2024-10-01 through 2025-06-30 holdout.

## Source and reconstruction coverage

The retained acquisition produced 8,006 candidate variant rows, representing 4,003 company-quarter candidates before variant-specific execution filters. Original current filing content is available for all 8,006 variant rows. A prior-year listing is absent for 856 variant rows and remains missing by protocol. Of prior-year listings that exist, original source content is available for 7,146 variant rows; two source URLs remain 404 and affect four variant rows.

Across 7,582 available current/prior documents required by the candidate set, 7,411 contain an explicit 70-110 day quarterly context matching the requested quarter end. Current filings with no exact quarter are excluded rather than converting annual, half-year or YTD facts into artificial quarters.

After exact-session price windows, liquidity recheck, execution, structural-action and source rules, the reconstructed design set contains:

- H005-A: 3,710 evaluable events, 204 +25%/20-session maximum-excursion labels.
- H005-B: 3,709 evaluable events, 179 +25%/20-session maximum-excursion labels.

Both the retained Nifty 500 series and the retained market session calendar contain 332 sessions over the design market-data window. No whole-market bhavcopy parse failures were admitted.

## Purged chronological tuning diagnostics

The frozen balanced L2 logistic model selected `C=0.01` for H005-A and `C=0.1` for H005-B. These are tuning/design diagnostics from purged chronological folds, not independent validation.

### H005-A, primary top 10%

- OOF rows: 2,299
- true explosive movers: 155
- selected: 230
- hits: 21
- recall: **13.55%**
- precision: **9.13%**
- prevalence lift: **1.35x**
- median Nifty 500 20-session excess among selections: **-4.47 percentage points**

The matched prior-20-session momentum baseline obtains 18.06% recall and 12.17% precision. The accounting-growth baseline obtains 16.13% recall and 10.87% precision. H005-A therefore does not improve on simple baselines.

### H005-B, primary top 10%

- OOF rows: 2,298
- true explosive movers: 135
- selected: 230
- hits: 25
- recall: **18.52%**
- precision: **10.87%**
- prevalence lift: **1.85x**
- median Nifty 500 20-session excess among selections: **-1.63 percentage points**
- median lead among hits: **7 sessions**

Matched top-10% baselines:

| Ranker | Recall | Precision | Lift |
|---|---:|---:|---:|
| H005-B logistic | 18.52% | 10.87% | 1.85x |
| prior-20-session momentum | 17.78% | 10.43% | 1.78x |
| accounting growth | 16.30% | 9.57% | 1.63x |
| first-session tape | 15.56% | 9.13% | 1.55x |

At top 20%, H005-B reaches 39.26% recall and 11.52% precision, but the frozen primary operating point is top 10%. Moving the operating point after seeing these outcomes would be post-hoc tuning and is prohibited under H005-v1.

## Decision

H005-v1 fails materially before the untouched holdout is opened. Its top-10% recall is far below the 35% historical gate, lift is below 2.5x, and median market-relative return is negative. The information-only variant is weaker still.

The earlier partial-replay probe that appeared more promising is superseded as evidence by this broader source-complete reconstruction. That discrepancy is itself useful: incomplete acquisition had materially overstated confidence.

The 2024-10-01 through 2025-06-30 holdout remains unopened and should not be consumed to validate a specification that already fails its design diagnostics. H005-v1 is retained as a rejected hypothesis. A nonlinear interaction model, if attempted, must be a new hypothesis with a frozen model and gate before any holdout labels are opened.
