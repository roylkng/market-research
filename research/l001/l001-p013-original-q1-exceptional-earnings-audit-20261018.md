# L001 P013 | Strong-looking Q1 PAT is not necessarily sustainable operating earnings

Date **18 October 2026**. **Status:** independently derived source-only earnings-quality diagnostic from the existing 100 original NSE Q1FY27 XBRL file replays. This did NOT pre-register a future-returns strategy or change frozen HG009.

## Original-source accounting facts

Original data authority: **L001 P007** full-100 XBRL-derived original Q1 FY27 source artifact `12112967877`, with immutable SHA `ade5ea8f0d1e491fba4416443a8c5831b69cbbae81f6479bec61cfbba0e0c276`.

All 100 companies have exact original fiscal Q1 (2026-06-30) PBT, PBT before exceptional items, exceptional before tax and PAT. The identity used is **pre-exceptional PBT + issuer-reported exceptional = PBT**, not the illegitimate subtraction of before-tax exceptional profit from PAT without tax adjustments.

**7 / 100** have a nonzero exceptional item. Two nonfinancial companies' reported PBT was **more than half from positive exceptional gains**:

| Original issuer | Q1 PAT ₹Cr | Pre-exceptional PBT ₹Cr | Positive exceptional before tax ₹Cr | Reported PBT ₹Cr | Exceptional share of reported PBT |
|---|---:|---:|---:|---:|---:|
| **MMFL / M M Forgings** | **90.4244** | **35.0696** | **56.2520** | **91.3216** | **61.60%** |
| **MINDACORP / Minda Corporation** | **206.25** | **112.98** | **123.99** | **236.97** | **52.32%** |

Five other nonzero cases were AMBUJACEM (−₹24.0cr), NIITLTD (−₹1.522cr), HTMEDIA (+₹1.18cr), SANDESH (+₹0.0728cr) and ZUARIIND (+₹4.8125cr with *negative* total reported PBT). No source-based conclusion can be reached solely from this about whether gains/losses recur, reversals, goodwill, capital disposals or tax effects.

## False-positive risk in the broad 100-company screen

The previous P008 source-backed post-hoc diagnostics gave MMFL a *mechanical* FY26 CFO-minus-PPE/October 15 basic-cap ratio **9.06%**, while its apparent Q1 FY27 PAT is **₹90.42cr**. An investor could mistakenly extrapolate ₹90cr per quarter and assign a high earnings multiple. The original issuer Q1 **pre-exceptional PBT was only ₹35.07cr**, with ₹56.25cr from an exceptional item. This is a material difference, not a rounding issue.

For MINDACORP, Q1 reported PAT ₹206.25cr also contains a large positive **pre-tax** exceptional item. Neither P013 nor any unverified spreadsheet should claim an exact after-tax normalized PAT from these numbers. Tax, minority, acquisition and the specific note explaining the exceptional item must be source-reviewed.

The >50% condition is a **post-hoc triage threshold** to allocate diligence, not a validated alpha predictor. No company is automatically rejected, because one-off gains still have economic value; they should be valued separately rather than capitalized as perpetual recurring profit.

## Follow-up hard evidence needed

1. Original issuer quarterly note accounting for each exceptional item, whether sale proceeds, tax reversal, fair-value measurement, impairment reversal, or other economic asset revaluation.
2. Actual cash flows from the event, net tax, minority claims and the asset/investment accounting basis.
3. Normalized operating PBT and reinvestment cash excluding financing/investing double counts, then a risk-adjusted valuation with current issued/diluted share count.
4. Next quarterly comparable results to test persistence, genuinely prospective and source-clock controlled.

The code `src/marketlab/l001_p013_exceptional_earnings.py` binds the source report, reproduces the PBT identity, keeps 100 identities, and refuses to convert these post-hoc caution labels into a buy list. Independent GitHub Action `.github/workflows/l001-p013-exceptional-earnings.yml` replays the original source artifact.

**Classification: research-only. No financial advice or investment permission.**
