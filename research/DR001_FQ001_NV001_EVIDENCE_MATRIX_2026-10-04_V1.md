# DR001 Tier A quality + normalized valuation evidence matrix — 2026-10-04

Status: **POINT-IN-TIME RESEARCH OVERLAY**  
Quality source: `FQ001-S001-v1`  
Valuation source: `NV001-S001-v1`  
NV001 score SHA-256: `4a6202d54d811d7db24cdbafac78c6ed50d0438f1be2c99da14aa39b2910cd29`  
Portfolio eligibility: disabled  
Live capital: disabled

This overlay adds normalized own-history valuation to the previously sealed DR001 and
FQ001 evidence. It does not rewrite the original DR001 ordering and does not change the
frozen H021 gate.

| Symbol | FQ quality rank / 84 | FQ score | NV rank / 69 | Current trailing P/E | Own-history median P/E | Current vs median | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| PERSISTENT | 19 | 66.07 | 45 | 44.82x | 45.40x | **-1.3%** | quality strong; valuation near own norm |
| COFORGE | 45 | 50.00 | 53 | 39.32x | 35.43x | **+11.0%** | growth case carries a modest historical premium |
| MOTHERSON | 22 | 60.86 | 57 | 42.90x | 36.94x | **+16.1%** | strong quality, but not cheap on trailing own-history basis |
| HINDALCO | 79 | 15.92 | 61 | 15.62x | 12.02x | **+30.0%** | weak quality + trailing premium; forward cheapness depends on earnings uplift/cycle |
| AUROPHARMA | 39 | 53.42 | 65 | 27.79x | 20.64x | **+34.6%** | balanced business case, but trailing valuation requires earnings growth to arrive |

Positive "Current vs median" means the current trailing multiple is above its own
four-observation historical median.

## What changed

The new evidence makes **PERSISTENT** more interesting than its raw forward valuation
alone suggested: it has top-quartile FQ001 accounting quality and trades approximately
at its own historical trailing-P/E norm. The Nagarro transaction remains a first-order
risk, so this is not a promotion.

**COFORGE** still has the strongest operating-growth evidence, but it is not historically
cheap on a trailing basis and its FQ001 cash-conversion/reinvestment pillars are below
median. Its thesis therefore depends on durable organic growth and Encora economics.

**MOTHERSON** retains strong accounting-quality evidence, especially cash conversion
and self-funded reinvestment, but its current trailing multiple is above its own
four-year median. Capital deployment returns remain the key test.

**HINDALCO** now has two independent caution flags: low FQ001 quality percentile and a
trailing multiple roughly 30% above its own historical median. Its much lower RR001
forward-P/E proxy therefore embeds a large expected earnings uplift. That makes
cycle-normalized earnings and H021 revisions more important, not less.

**AUROPHARMA** also shows a large trailing-versus-forward valuation gap. Its RR001
forward P/E was materially below this trailing P/E, so a meaningful earnings increase is
already embedded in the forward case. Positive H021 revisions would help validate that
bridge; negative revisions would be especially damaging.

## Second-line valuation observations

The normalized valuation lens flags several previously identified non-Tier-A names as
cheap relative to their own history:

| Symbol | NV rank / 69 | Discount to own-history median | Research state |
| --- | ---: | ---: | --- |
| IOC | 2 | 52.4% | cyclical/margin-normalization watch |
| LODHA | 4 | 47.5% | Tier B deep-research candidate |
| VEDL | 5 | 44.5% | corporate-action/special-situation watch |
| DLF | 15 | 25.9% | Tier B deep-research candidate |
| ONGC | 28 | 12.5% | cyclical-value watch |
| JINDALSTEL | 66 | **35.5% premium** | Tier B, but valuation now challenges the thesis |

These are relative-to-own-history observations, not statements of absolute cheapness.
For example, a structurally high-P/E company can rank highly because its current
multiple is far below an even higher historical multiple.

## Current evidence stack

```text
RR001
growth + price confirmation + forward EPS yield
          |
          v
DR001
business/archetype deep research
          |
          +------> FQ001 accounting quality
          |
          +------> NV001 own-history valuation
          |
          v
H021 28-day EPS-revision gate
          |
          v
valuation + red-team review
          |
          v
sealed ADO
          |
          v
PF001 gates
```

FQ001 and NV001 are research lenses. They do not independently promote a company through
H021, create an ADO, or authorize a position.
