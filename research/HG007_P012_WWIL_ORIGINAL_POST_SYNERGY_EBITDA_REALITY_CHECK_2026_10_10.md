# HG007-P012: Reverse-Engineer WWIL Management EBITDA Synergy Hurdle

Source review frozen: 10 October 2026 IST. No future returns,
portfolio positioning or company completion probability authorized.

## Critical question

Is the ₹550 crore Wind World India 4.5 GW wind O&M acquisition really
cheap at management's quoted **approximately 2x EBITDA**?

The original 7 October 2026 BSE Reg30 **management press release**
must be read separately from its six-page BTA/financing disclosure.
The latter says payment was made but legal transfer was still
conditional; the former discusses future operational synergies.

Original BSE press ID e588eec4-0a4f-46f7-9cac-be11142c492a.

Original BSE PDF SHA-256:
0a5a0f5028f07363311621e697f4a871e9baf59610777e4c40a54ac48be88bc9

Both the 459,650 original bytes and immutable source receipt are
anchored under research/hg007/wwil-oct7-press.

The original press wording ties the *2x* quote to **future EBITDA after
fully expected synergies over the next year**, not audited trailing WWIL
EBITDA. This is a critical underwriting difference.

## Economic counterfactual, not a forecast

If ₹550 crore were treated as a like-for-like transaction
enterprise-value numerator and if **2x** were achieved, that ratio
would require:

550 / 2 = ₹275 crore annual EBITDA.

The press also reports **approximately ₹580 crore FY26 revenue** for the
WWIL O&M undertaking.

Using that *earlier historical revenue denominator* yields a
roughly 47.4% EBITDA margin proxy (275/580). But management's
post-synergy EBITDA is expected **later**, so the revenue period and
future EBITDA period are not comparable. The calculation is strictly
a reverse hurdle, **not** a realized or forecast gross margin.

If revenue and asset contract economics stayed hypothetically fixed at
₹580 crore, alternative EBITDAs/multiples would be:

| Illustrative EBITDA margin | Arithmetic annual EBITDA | ₹550cr / EBITDA |
|---:|---:|---:|
| 15% | ₹87cr | 6.32x |
| 25% | ₹145cr | 3.79x |
| 35% | ₹203cr | 2.71x |
| 40% | ₹232cr | 2.37x |
| 47.41% | ₹275cr | ~2.00x |

The source's contractual **5% annual price escalation** cannot
automatically be applied to total revenue or profits without
contract-by-contract backlog, churn and client payment data.

## Why the headline ratio cannot price INOXGREEN stock yet

- ₹550 crore **cash payment inclusive of taxes** is not independently
  verified purchase enterprise value net of retained debt and
  transaction liabilities.
- The target historical carve-out EBITDA, receivables, technical
  maintenance capex, contract renewals and cash conversion are absent.
- Realization of group cost synergies at this scale is not audited or
  guaranteed.
- Vibhav minority economics depend on future Authum conversion terms;
  the BTA source establishes current 100% parent ordinary share capital
  before conversion, not a completed 75% future ownership structure.
- Inox Green parent-level earnings/valuation also depend on current
  diluted shares (September QIP included), debt, cash use and
  related-party adjustments. HG007-P008/P009 show earlier capital cap
  was understated, while full current FD remains blocked.
- The source press does not prove WWIL transfer conditions precedent
  are fulfilled or define a transferable earnings run rate.

## Source-pinned procedure

- src/marketlab/hg007_wwil_synergy_hurdle.py
- scripts/review_hg007_wwil_original_synergy.py
- tests/test_hg007_wwil_synergy_hurdle.py
- .github/workflows/hg007-wwil-synergy-hurdle.yml

The model rehashes the exact original BSE PDF and its immutable
source receipt, reads each PDF page with the SS002 deterministic
extractor, and requires management's exact future synergies and
2x/₹550cr/₹580cr/5% statements from those original page texts.

The derived output stores claim-page numbers, page-text SHA-256s
and exact original source hash, plus clearly non-predictive scenario
arithmetic. It does NOT create a company-specific 50% upside score,
expected return or security target price.

Result path, immutable after CI:
research/hg007/wwil-oct7-press/source-bound-post-synergy-hurdle-v1.json

Until original WWIL FY26 audited EBITDA and sustainable cash flow
are independently verified, the 2x claim is a **management
future-synergy narrative**, not an established hidden-gem bargain.

**Portfolio eligibility and live capital remain disabled.**
