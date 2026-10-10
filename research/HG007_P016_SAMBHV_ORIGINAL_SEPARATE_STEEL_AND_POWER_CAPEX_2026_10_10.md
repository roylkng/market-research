# HG007-P016: Original SAMBHV Q1FY27 Phase-I CAPEX Source Custody

Status: **SOURCE ACQUISITION AND ECONOMIC RISK IDENTIFICATION ONLY**.
Reviewed at 10 October 2026 IST. No actual future earnings, capex fully
spent, stock target, confidence, posterior stock re-ranking or live capital.

## Source and why it matters

Original company-hosted Reg30 investor presentation dated 3 August 2026:

https://www.sambhv.com/uploads/pdf/investors/financial-performance/results/2026-2027/Investor-Presentation.pdf

Page 9 (PDF one-based, page display 8) contains distinct future roadmap items:

- a greenfield expansion adding 1.2 MMTPA finished products in phases;
- Phase-I stainless-steel coils **0.36 MMTPA**, estimated **INR 8,100
  million = INR 810 crore** for production line, target commissioning
  **Q4 FY27**;
- separately listed **25MW round-the-clock captive power plant at
  Kesda**, estimated **INR 1,250 million = INR 125 crore** in Phase-I,
  target commissioning **Q4 FY27**;
- 30MW Sarora power project **INR 150 crore**, 8MW Kuthrel rooftop
  solar **INR 25 crore** and 0.15MMTPA ERW brownfield expansion
  **INR 50 crore** are ALSO separate roadmap lines, not automatically
  part of the 0.36MMTPA/25MW scenario.

Do not sum all unrelated project CAPEX into the steel plant. Equally,
do not take a future margin that is only achievable with round-the-clock
captive power and ignore that required power investment.

The Q1 FY27 presentation also separates:
- existing 0.682 MMTPA finished capacity;
- planned incremental 1.2 MMTPA stainless and value-added finished;
- 0.15 MMTPA ERW incremental brownfield;
- July 26 construction images and equipment-progress percentages;
- Q1 FY27 *existing-business* operating EBITDA/ton approximately
  INR 9,355, which is NOT evidence of new 0.36MMTPA cash flow after
  future construction.

These are management estimates, not independent audited plant project
returns or confirmed commissioning.

## Material issue in original HG005-D003 sensitivity

HG005-D003 preserved a strong-case gross mechanical net-equity-equivalent
uplift / 1 October share-capital reference of **0.5243963**, modeled
at 0.36MMTPA, 85% utilization, INR 9,000 operating EBITDA/tonne,
12x EV/EBITDA and **INR 810 crore CAPEX**.

The scenario did not explicitly include this **additional listed
INR 125 crore Phase-I 25MW power project**.

Once exact original source bytes are captured and pinned, P017 should
offer two mutually exclusive source-labeled boundary cases:

1. **Steel-only CAPEX assumption: INR 810 crore.**
   Preserve original HG005 result unchanged; do not claim it includes
   future power economics.
2. **Power-dependent same operating EBITDA assumption: INR 810 +
   INR 125 = INR 935 crore.** Illustratively, subtract further
   INR 125 crore from the net uplift. At historical HG005 1 Oct
   share-capital denominator INR 4,757.47 crore, that reduces
   52.44% to about **49.82%**.

The second scenario is conditional on the 25MW plant being integral
to the operating EBITDA/ton assumption. It is NOT verified that
the 25MW capex is economically unavoidable or that it produces
no separate positive avoided-power-cost value. The two EBITDA
scenarios must be independently modeled before risk-adjusted EV/FCF.

Even scenario 2 excludes debt, interest, dilution timing, taxes,
actual completion, ROCE, price/corporate actions and terminal multiple
sensitivity. Neither case qualifies as expected return or a 50% stock
target.

## Original source custody plan

- Collector: scripts/acquire_hg007_sambhv_original.py
- Tests: tests/test_hg007_sambhv_original.py
- Action: .github/workflows/hg007-sambhv-phase1-original.yml

The exact original HTTPS company URL is hardcoded. No alternatives,
redirects, authentication bypass or stale generic Q2/quarter replacement.
The issuer PDF must have exactly 43 pages with 3-Aug2026 issuer/date
and page9 distinct project/₹810cr/₹125cr text. Raw PDF and source
receipt will be SHA-256 anchored in Git after green CI.

A blocked original remains blocked and is not silently replaced by
the third-party BazaarWatch/Scribd transcript. The latter only
supports discovery until the company PDF is independently captured.

## Further operating and funding evidence needed

- True Phase-I ₹810 and ₹125 spend-to-date, committed remaining CAPEX
  and debt/equity funding split.
- 25MW plant expected operating savings and variable power/fuel costs,
  and evidence the savings are or are not included in EBITDA/ton.
- Separate 30MW/solar/ERW projects treated distinctly, never co-owned
  by the steel investment without causality.
- Check actual sales mix and internal consumption to avoid counting
  slab/coil flows multiple times. Q1 FY27 production volume includes
  captive consumption and is not directly external sales volume.
- Original updated permitting/commissioning/capacity utilization
  and post-launch audited revenues and operating cash flow.
- Updated fully diluted shares, warrants, borrowings and required
  reinvestment after FY27.

No additional return-predictive alpha experiment is declared here.
No live capital is authorized.
