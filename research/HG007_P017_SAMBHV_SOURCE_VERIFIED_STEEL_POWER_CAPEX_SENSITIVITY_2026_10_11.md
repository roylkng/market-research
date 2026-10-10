# HG007-P017: Original SAMBHV Phase-I Steel versus Captive Power Cost Boundary

Status: **SOURCE-VERIFIED REVERSE SENSITIVITY, NOT STOCK UPSIDE FORECAST**.
Research implementation date: 11 October 2026 IST.

## What the original sources establish

The exact 3 August 2026 Sambhv Steel Tubes investor presentation was
retained as original 43-page PDF, SHA-256
19e6f9faea1aaaec481ad3ab9c842a58b96bfae636f146143f44e3a42b6d696d.
Source proof includes the original 1-based PDF page 9 and its SHA-256
c57f4b31a8c55113312ab6658773071e53e2835b1e6d8ab4a1b8808b1af49197.

The issuer listed two **separate** Phase-I Q4FY27-targeted projects:
- New stainless-steel coil capacity **0.36 MMTPA**, stated estimated
  capex **₹8,100 million = ₹810 crore**.
- A separate **25 MW round-the-clock captive power plant**, stated
  estimated capex **₹1,250 million = ₹125 crore**.

The source does **not** establish that the captive plant is required
for the new steel facility's stated steel EBITDA/ton assumptions.
Nor does it prove either asset is now commissioned, either full
capex has been spent, or that those future EBITDA/ton numbers will be
achieved. Management's other 30MW, 8MW solar and ERW capacity work
are separate roadmap lines and are intentionally excluded here.

## Why the older frozen HG005 analysis needs a source-only overlay

HG005-D003 produced a strong mechanical scenario using:
- 360,000 tonnes * 85% hypothetical utilization = 306,000 tonnes.
- ₹9,000 hypothetical annual operating EBITDA/tonne.
- 12x illustrative EV/EBITDA multiplier.
- Steel-only ₹810 crore CAPEX.
- Frozen 1 October 2026 diluted capitalization reference
  **₹4,757.470221205 crore**, with 1 October stock price **₹161.45**.

That gives **₹275.4 crore hypothetical annual operating EBITDA**,
₹3,304.8 crore at a 12x illustrative multiple, minus ₹810 crore
steel-only capex = ₹2,494.8 crore hypothetical net incremental value,
or **52.44% of the historical market-cap reference**.

It is not a share-price target. The business might never produce that
EBITDA, and the 12x multiple may not persist. None of this accounts
for financing, debt-like obligations, cash-flow timing, corporate
actions, new dilution, interest, taxes or execution costs.

## Two deliberately mutually exclusive capital-budget cases

| Source/hypothesis case | Strong 85% / ₹9,000/t / 12x | Mid 100% / ₹7,000/t / 10x |
|---|---:|---:|
| Annual steel EBITDA if assumptions hold | ₹275.40cr | ₹252.00cr |
| Gross hypothetical incremental EV | ₹3,304.80cr | ₹2,520.00cr |
| **Steel only, ₹810cr CAPEX**: value less project capex | ₹2,494.80cr | ₹1,710.00cr |
| Steel only, % frozen historical cap | **52.44%** | **35.94%** |
| **Steel + power, ₹935cr total**: value less both | ₹2,369.80cr | ₹1,585.00cr |
| Steel + power, % frozen historical cap | **49.81%** | **33.32%** |
| Mechanical difference | **−2.63 percentage points** | **−2.63 percentage points** |

The two CAPEX cases are alternatives, not additive return estimates.
The larger ₹935cr budget is valid for this scenario **only if**
the 25MW captive project is a necessary companion cost for earning
the assumed steel EBITDA and its operating savings are already
included in that steel EBITDA.

If the power plant generates an **independent cash-flow benefit not
included in the steel EBITDA**, valuing the power project as only a
CAPEX reduction could understate economics. To offset ₹125cr at an
illustrative *same* multiple would require **₹10.42cr/year additional
EBITDA at 12x**, or **₹12.50cr/year at 10x**. These are break-even
reverse hurdles, not management guidance, cost savings forecasts,
actual cash flows, or a justified enterprise valuation.

The strong coupled-case ratio falling just below 50% does **not**
prove Sambhv lacks 50% stock potential. It proves the old source-only
algebra materially depended on excluding a separately listed
possible companion capital commitment.

## Limits and remaining evidence

1. Confirm whether Kesda 25 MW is technically, commercially,
   contractually or operationally required for the 0.36 MMTPA plant.
2. Obtain power generation/consumption, tariffs, avoided grid cost,
   usage rights and baseline/expected energy intensity for steel.
3. Separate proposed, committed and paid CAPEX for both distinct
   projects; derive financing, interest, debt, taxes and minority claims.
4. Validate actual Q4 FY27 commissioning, production ramp,
   utilization, realized EBITDA per tonne and operating cash flow.
5. Independently revalidate current fully diluted Sambhv shares,
   potential warrants and post-1 October share action/price basis.
6. Do not use historical valuation ratios as expected future return;
   demand source-backed downcases and a qualified transaction
   probability before any prospective stock-level investment forecast.

## Code, original source and reproducibility

- Model: src/marketlab/hg007_sambhv_phase1_sensitivity.py
- Runner: scripts/reconcile_hg007_sambhv_steel_power.py
- Tests: tests/test_hg007_sambhv_phase1_sensitivity.py
- Source/original: research/hg007/sambhv-aug2026-investor/
- Frozen older input: research/hg005-d001-result-v1.json and
  research/hg005-d003-result-v1.json
- New result, after CI and merge:
  research/hg007/sambhv-aug2026-investor/phase1-steel-power-capex-v1.json

The source packet strictly preserves the earlier original HG005
conclusions and original August issuer PDF bytes, with explicit
no-current-FD, no-forecast, no-trade and no-capital assertions.
