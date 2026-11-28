# Investment discovery evidence audit | 18 November 2026

## Decision

The six-case reconstruction does not establish selection skill. A stronger test already existed in the repository but its predeclared 20-session endpoint had not been published. This audit completes that **source-price diagnostic** using the original 300-company selection. The selected arm again fails to show an advantage. This is evidence about the existing discovery mechanism, not proof that discretionary long-term company underwriting cannot work.

**Operational implication:** do not use the old opportunity-lane count as a demonstrated expected-return rank. Retain it as a source-routing aid. Current company buy decisions need their own economics and price argument. An attractive company must not inherit statistical confidence from either the six chosen examples or the old screen.

## What was actually completed

Read-only audit against repository commit `1e27acfa719ee3ff4615f8c105eaa0ae870420bf`. Recovered **40 archived original source files**, covering the stock UDiFF ZIP and Nifty 500 price-index CSV for every one of the 20 prescribed sessions. Checked each file's SHA-256 against its retained receipt. Reparsed all source bytes, independently reconciled **5,623 OHLC rows** in the 19 existing daily packets, and parsed the missing November 8 full-market archive already retained under H021. Source retrieval dates were checked to follow session close. These are archived NSE sources retrieved from the repository today, not newly collected November market observations.

The original 100 selected identities and both 100-company control arms were preserved. The selected file was committed on October 14 at 08:31:04 UTC (`5a8833b519cf9e29aa82cdf26ab51ef97d84d45f`). The control manifest was committed at 08:47:41 UTC (`d1dff0ce1a2def503361b396664cb6b634378388`). Both precede the October 15 entry. The population came from a frozen 2,319-name NSE source. It is not a random NSE/BSE portfolio.

The entry is **October 15 official NSE EQ open**. The exit is **November 12 official NSE EQ close**, following the already-frozen Muhurat amendment. November 8 is included once. The exact session sequence is October 15, 16, 19, 21, 22, 23, 26, 27, 28, 29, 30 and November 2, 3, 4, 5, 6, 8, 9, 11, 12. No decision, selection, holding period or original ledger was changed.

## New H20 result

All figures below are **unadjusted price changes among observable exact identities**, not economic or after-cost returns.

| Original arm | Original slots | Complete exact EQ observations | Mean price change | Median price change |
|---|---:|---:|---:|---:|
| Selected, two or three opportunity lanes | 100 | 98 | −0.696827% | −1.405455% |
| One-lane comparison | 100 | 98 | +0.662482% | +0.204313% |
| Zero-lane comparison | 100 | 98 | +0.029559% | −1.761619% |

Selected-minus-one-lane mean: **−1.359309 percentage points**. Selected-minus-zero-lane mean: **−0.726386 pp**. The selected median is slightly above the zero-lane median but below one-lane. This is not a uniformly dominant ordering.

The Nifty 500 **price index** rises **8.214063%**, from October 15 open **22,054.25** to November 12 close **23,865.80**. Stock and index reference clocks match. The index differs materially from these equal-name, outside-U001 and liquidity-band-selected arms. Its gap cannot be called risk-adjusted alpha or a realized portfolio opportunity cost.

As an independent arithmetic check, this parser also reproduced all six already-sealed H1/H5 arm means within **0.0000005 percentage points**. Their earlier negative comparisons were preserved. These overlapping horizons remain one market entry event, not three independent validations.

## Six omissions remain visible

| Arm | Original identity | What the archived source shows |
|---|---|---|
| Selected | GLOBAL | Same ISIN moves from EQ to BE on November 9 |
| Selected | RETAIL | Same ISIN is BE at entry and throughout the interval |
| One lane | MOREPENLAB | Same ISIN is BE at entry and throughout the interval |
| One lane | ONWARDTEC | Same ISIN moves from EQ to BE on October 26 |
| Zero lane | ICICIPRULI | Same ISIN appears as ICICILIFE from October 23. NSE circular CML76967 confirms the name and symbol change |
| Zero lane | MAHSCOOTER | No exact row on October 30. Later rows show BE, including the exit |

These are **missing under the frozen exact-symbol/EQ rule**, not six verified delistings or economic losses. Their outcomes stay null and original denominators stay 100. The ICICI rename illustrates how measurement can fail even when the security continues. A future protocol should predefine genuine identity continuity and trading-series handling. This audit does not repair the old rule after seeing returns.

Missingness reversal thresholds are algebra, not forecasts. To overturn the fixed-100 selected-versus-one-lane mean ordering, the sum of the two unknown selected changes minus the sum of the two unknown one-lane changes would need to exceed **133.212267 pp**. Against zero-lane the threshold is **71.185877 pp**. No zero imputation, probability, circuit bound or assumption about the missing outcomes is used.

The 294 admitted price paths also lack complete split, bonus, rights, dividend-entitlement and economic continuity clearance. Same ISIN and complete OHLC do not prove total-return comparability. Execution spreads, impact, taxes and capacity are unmeasured. Controls match prior turnover bands, not industry, size, beta or accounting regime. These limitations prevent an alpha claim in either direction.

## Audit of the previous six cases

The numerical price-return arithmetic is correct to floating-point precision. The scientific weakness is the experiment, not division:

1. Two presently selected survivors are not a historical investable universe.
2. Six rows contain only two issuer clusters and three common entry dates.
3. Decisions were finalized after outcomes were visible. The protocol says entry is conditional on a valuation limit but contains no frozen numeric decision rule or limit.
4. “BUY_CANDIDATE” is a retrospective screen label, not proof the complete current underwriting standard would have approved the investment then.
5. Dividend/corporate-action completeness, path drawdowns and economic benchmark returns are unavailable. The script reproduces manually transcribed prices, not underlying source verification.
6. Assertions that selected examples rose or fell merely check the supplied example outcomes. They do not test predictive skill.

The useful lesson is narrower: Datamatics 2024 exposes the cost of leaving a recovery case permanently on WATCH. A dated reopening trigger is worth testing prospectively. It does not retroactively make that missed rally predictable.

## Other evidence recovered, not recomputed here

- **H001:** retained 24-observation delayed-entry test reports Pearson 0.066 and Spearman 0.035 versus excess returns. Raw earnings acceleration was rejected as a sufficient ranking signal.
- **H021:** open PR #611 retains a different genuinely frozen 10-stock EPS-revision cohort. Its 20-session source-only mean was +6.292754% versus Nifty 500 +7.079378%, or −0.786623 pp. This has separate action/cost limitations. The primary horizon is 60 sessions. Neither result validates the current company theses.

## Reproduction and evidence

Run the accompanying script against a checkout of the source commit:

```bash
python audit_hg009_h20.py --repo /path/to/market-research --output /tmp/hg009_h20_audit
```

The script writes only the separate audit result and row CSV. `hg009_source_manifest.json` lists all 40 repository source paths and verified raw hashes. No original market files need duplicating in a research PR. The compact result retains all 300 identities, missing dates and original receipt metadata.

Primary contracts: `research/HG009_P001_MATCHED_CONTROL_PROSPECTIVE_PROTOCOL_20261014.md`, `research/HG009_P006_FROZEN_H1_H5_PRICE_ONLY_DIAGNOSTIC_20261014.md`, and `research/hg009/hg009-p004-a1-nov08-calendar-v1.json` at the stated commit. Original special-session timing: https://nsearchives.nseindia.com/content/circulars/CMTR76941.pdf. ICICI symbol continuity: https://nsearchives.nseindia.com/content/circulars/CML76967.pdf. Prior limited reconstruction was read from the user's recovered November 17 ZIP. No remote repository or frozen research files were mutated by this audit.
