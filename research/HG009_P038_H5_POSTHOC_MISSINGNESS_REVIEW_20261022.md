# HG009-P038 | H5 source-missingness audit and fixed-cohort uncertainty

**Analysis registered 22 October 2026, AFTER the observed 15–22 October
five-session NSE price interval.** This is a *post-hoc source-integrity
diagnostic*, not a newly preregistered trading hypothesis, alpha discovery,
financial recommendation or holding-period total return.

## The exact original research

The first frozen HG009 experimental universe contains 100 selected stocks,
100 one-lane stocks and 100 zero-lane stocks. All three groups were selected
before the same **15 October** NSE entry session. The precommitted H5 interval
is five completed NSE sessions: **15, 16, 19, 21 and 22 October 2026**.

Original source-replayed report:
research/hg009/price-diagnostics/HG009-P006-H5-20261015-v1.json

Original report Git blob:
158fd143a0c13675cfdcd8cc716e576cd515fdab

Original result signature SHA-256:
7ee99e2b9a9a356b89850ac1acd30c4e7f367da5c306793e5cf874ab0098d0aa

Every group retains **100 original identities**, including missing and
changed-series names. The signed report records original exchange UDiFF
and Nifty 500 index-source SHA-256 receipts for *each* session.
H5 reuses H1's original entry observations; those are **one common market
entry event**, not five independent experiments or 300 independent trials.

## Observed priced-company-only findings

| Arm | Original names | Official price ratio available | Mean percent | Median percent |
|---|---:|---:|---:|---:|
| Selected hidden-gem cohort | 100 | 99 | -6.286652 | -6.700009 |
| One-lane comparison | 100 | 99 | -6.083574 | -6.565657 |
| Zero-lane comparison | 100 | 100 | -5.421358 | -5.876904 |

Official Nifty 500 *price index* open-to-final-close reference for
the same observed window: **-1.621910%**. This benchmark
is not a dividends-reinvested TRI.

The selected cohort's observed-only mean trails one-lane names by
**0.203078 percentage points** and zero-lane names by **0.865294 pp**.
Neither difference is a full fixed-100-name group mean because two
original issuer identities have no admissible NSE EQ price row:
- selected: RETAIL (INE03DD01011)
- one-lane: MOREPENLAB (INE083A01026)

Those missing identities appear in all five original source sessions.
No delisted/suspended price is presumed to be zero, and no price is
substituted from another series/date/vendor.

## Retrospective missingness scenario, NOT actual returns or circuit limits

Under the **arbitrary and explicitly unverified** stress interval
[-20%, +20%] for *each* unknown five-session stock price change:

| Hypothetical fixed-100 mean gap | Lower pp | Upper pp |
|---|---:|---:|
| Selected minus one-lane | -0.601048 | +0.198952 |
| Selected minus zero-lane | -1.002428 | -0.602428 |

This interval is a research stress example, **not** an NSE price
circuit bound, a modelled likelihood, or a guaranteed unknown-return
range. Outside that interval, conclusions may reverse.

The algebraic break-even missing-price requirements are:

- If zero-lane remains fully priced, missing selected RETAIL would
  need an approximately **+80.243%** five-session unadjusted change to
  equal zero-lane's 100-company mean.
- Relative to one-lane, unknown RETAIL minus unknown MOREPENLAB
  would need to exceed approximately **20.105 percentage points**
  for the fixed-100 comparison to reverse.

These are *scenario reversal thresholds*, not expected stock returns.

## Scientific interpretation and next real gate

The current evidence does not support promoting the old triple-
convergence selection rule. But these five days **cannot
establish its long-run alpha is negative** either.

Important caveats remain:

1. One common market entry event, not a reproducible ensemble.
2. Unadjusted prices, not dividends, split/bonus/rights or
   merger/demerger-adjusted shareholder wealth.
3. Missing/stale issuer EQ identities must not be imputed as zero.
4. Original liquidity-band controls are **not sufficiently matched**
   for sector, size, beta, financing regime and earnings-quality mix.
5. No verified executable close/open fills, bid-ask spread or
   turnover-safe real order capacity.
6. H20 is now scheduled for **12 November** for HG009 after the
   originally missing 8 November Diwali Muhurat trading session
   was separately confirmed; original NSE source/corporate-action
   evidence still must mature.
7. H60 still requires an officially verified 2027 trading calendar.
8. Future industry-balanced trials are constrained by source coverage:
   HG009-P036 found only 18 possible one-level-industry and liquidity
   matched triplets outside the original 300. That is **a feasibility
   limit**, not new validated alpha.

H5 includes H1; changing the original selected names because they
underperformed now would introduce hindsight. The proper next
experiment requires an independently frozen, genuinely new cohort,
balanced *before entry* on audited industry, size, float/liquidity,
beta and company earnings-quality family. Return comparisons need
multiple distinct market entry dates and total-return/cost treatment.

P038 creates **no** per-stock target price, investment recommendation,
current realized economic return, company probability, portfolio
eligibility or live-capital authority.

## Reproducibility

Source checks:
- src/marketlab/hg009_p038_h5_missingness.py
- scripts/materialize_hg009_p038.py
- tests/test_hg009_p038_h5_missingness.py

Machine-readable appendix is generated reproducibly after CI:
research/hg009/hg009-p038-h5-missingness-bounds-v1.json

Run:

    python scripts/materialize_hg009_p038.py
    python scripts/materialize_hg009_p038.py --check

This output cannot overwrite an existing divergent prior result.
