# L001/L004: Long-horizon value and temporal-LLM contracts

Created: 2026-10-17. Status: experimental implementation, **NOT a frozen investment experiment**. Live capital disabled.

## Why

Existing AE001 runs at 1/5/20/60 NSE sessions. H003 tests 120 sessions. Neither proves long-term 1–3-year hidden-gem alpha. Point-in-time NSE source storage also cannot guarantee that the language model does not know a company's subsequent history.

This implementation follows research/reviews/lra001-2026-10-17-india-papers-news-factor-gap-audit.md. It does not amend HG009/H002/H003/H004 selection, benchmarks, registry hashes, recorded decisions or outcome ledgers.

## L001: long-horizon cash and shareholder returns

Code: src/marketlab/l001_long_horizon.py

- The industrial-company NOPAT/ROIC formulation **explicitly excludes banks, NBFCs, insurers and unclassified businesses**, which require a separate credit/capital-adequacy model. HG009 includes financial companies, so applying one model to all 100 would be invalid.
- Admission requires a set of nine source-backed fields: price, fully diluted parent shares, attributable distributable owner cash, genuinely excess parent cash, separately attributable claims, prior/current NOPAT and prior/current invested capital.
- Reject a CFO-minus-PPE substitute, issuer-defined net-cash headline used as fully distributable surplus, altered raw bytes, mismatched ticker/ISIN or financial basis, and publication/acquisition after the exact UTC decision instant.
- Source bytes, exact publication time and an independently reviewed status must be supplied. **The review status is a caller assertion. Code cannot certify economic truth or reviewer independence.**
- Incremental NOPAT / positive net invested capital is a diagnostic, not guaranteed organic ROIC. Segregate acquired capital, discontinued assets and working capital for real cases.
- Solve how much 1/2/3-year compounding of baseline owner cash a chosen diluted share valuation, discount rate, terminal owner-cash multiple, accessible surplus and unduplicated claims would require. This is inverse valuation arithmetic, not a future return forecast.
- Introduce 252/504/756 completed-trading-session outcome arithmetic with original unadjusted execution price, split/bonus share factor, all distributions per initial share, exit or delisting settlement, total-return benchmark, and simple cost stress.
- Refuse immature horizons, unresolved rights/mergers, missing corporate-action reconciliation, delisted names without proceeds, non-executable entries and mismatched holding periods. No missing return is implicitly zero.
- Total-return calculations use caller-supplied calendar receipts and corporate action flags. They **do not yet independently authenticate the NSE calendar bytes or complete outcome-source receipts**, so their status remains TOTAL_RETURN_MATH_ONLY and they never enter frozen canonical outcomes automatically.

## L004: model pretraining look-ahead

Code: src/marketlab/l004_model_time.py

- Store source and prompt SHA-256 and exact publication, acquisition, model release and inference timestamps.
- Forward predictions must complete before their prospectively declared decision cutoff. Future outcomes must not be attached. Passing the timestamp contract is NOT proof of a useful signal.
- Later LLM extraction of old text is EXTRACTION_ONLY. A contemporary model's historical narrative never becomes historical alpha.
- Historical model checkpoint metadata require a model that genuinely existed before the event, a pre-cutoff training period, and independently attested checkpoint lineage. Even if these are asserted, the code cannot independently audit weights or pretraining corpus. The result remains ineligible for historical alpha until stronger external audit plus holdout evaluation.
- Unknown closed-model training contents, server-side tool behavior and model memory remain explicitly unverified.

## Next source-complete work

1. Obtain original filed balance sheet/cash flow and fully diluted capital as of each new decision instant.
2. Reconcile owner distributable cash after reinvestment, leases, interest, taxes, acquisition liabilities and minorities.
3. Preregister the dynamic NSE investable universe, company controls, 252/504/756-session total shareholder return including delisted securities, trial count and after-cost metrics before observing future returns.
4. Freeze a new L001 prospective cohort independently of all earlier H-series experiments. Absent historical truly frozen checkpoint, LLM-assisted reconstruction is qualitative only.
5. Compare multi-year results to simple value, quality, momentum and liquidity baselines and matched sector/size peers. Use 1/2/3-year prospective maturation, not invented future returns.
6. Separately implement and test L002 liquidity-conditioned momentum and L003 point-in-time earnings expectations.

## Tests and release gate

- pytest -q tests/test_l001_long_horizon.py tests/test_l004_model_time.py
- ruff check src/marketlab/l001_long_horizon.py src/marketlab/l004_model_time.py tests/test_l001_long_horizon.py tests/test_l004_model_time.py
- Full repository CI before merge.

All test cases are synthetic security/contract tests. No validated NSE expected returns, no investment price target and no live-capital authorization are created.
