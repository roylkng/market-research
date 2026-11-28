# Targeted legacy cash-retention check

**21 November 2026. Scope: MSTC's prior simplified valuation, the 20 November eClerx note and the 21 November CAMS reverse calculator. Original files were read without modification. This is an accounting-convention check prompted by a specific ambiguity, not a new company audit or a historical performance test.**

## Finding

**The prior MSTC mechanism leaves the use of retained cash ambiguous. The actual eClerx and CAMS models do not omit retained cash under their stated conventions.** Do not generalize the MSTC issue to every earlier decision.

The original research artifacts and their current byte hashes are listed in [source_artifact_receipt.json](source_artifact_receipt.json). These are repository artifact hashes, not newly captured issuer-source hashes. The portable [calculator](calculate.py) uses their original financial assumptions, with inputs and outputs in this directory.

## MSTC: one comparison that changes only cash retention

The earlier note uses ₹192.656 crore starting selected cash, 10% annual growth, 50% distribution, 7.04 crore shares, no opening treasury credit, a 15 times terminal cash multiple, five years and a ₹656.55 entry price. It does not explicitly say whether the other 50% funds additional growth costs or remains an asset for shareholders.

| Same original assumptions | Five-year IRR | Retained cash added at exit | Terminal price |
|---|---:|---:|---:|
| Published convention, no separate credit for the undistributed half | **2.91%** | ₹0 | ₹661.10 |
| Bounded sensitivity: all undistributed cash survives and earns zero return | **5.41%** | **₹646.90 crore** | **₹752.99** |

The difference is **2.49 percentage points annually**. The original approximately 2.9% IRR is arithmetically reproducible. The issue is **ambiguous funding treatment**, not a falsely calculated IRR.

Adding retained cash is valid only if that cash is not needed for additional capital spending, working capital, acquisitions, employee or creditor claims, or other economic uses. Conversely, if the retained half funds growth, that use and the assets or earnings it creates need explicit treatment. It cannot simply disappear from the shareholder equation.

This sensitivity is **not** the new funded MSTC forecast. It does not establish that all ₹192.656 crore is recurring free cash, that all future 10% growth is funded, or that the entire retained amount is available to outside owners. It keeps the earlier assumptions solely to identify the effect of the accounting convention. The newer MSTC case separately resolves company economics and claims.

## eClerx: the retained half was already counted

The 20 November note explicitly distributes 50% of future cash and adds the accumulated other 50% once at year-five exit. It does not assume a return on the retained balance. The formula includes:

`terminal value = multiple × year-five selected cash + assumed opening treasury + accumulated retained half`

Recalculation reproduces the published figures at the original ₹1,468.80 entry reference:

| Cash growth / terminal multiple | Published model including retention | Counterfactual if retention were omitted |
|---|---:|---:|
| 0% / 10× | −6.80% | −10.27% |
| 4% / 12× | −0.90% | −3.91% |
| 6% / 12× | **0.84%** | −2.13% |
| 6% / 14× | 3.23% | 0.55% |
| 10% / 14× | 6.85% | 4.24% |

The right column is a diagnostic counterfactual, not the old published result. **No retention correction or decision upgrade is warranted from this check.** The original model's disclosed limits, including growth funding, employee-share claims, proposed remuneration and acquisition spending, remain separate questions.

## CAMS: full future distribution leaves nothing to accumulate

The actual reverse calculator assumes **100% of annual modeled owner cash is distributable after all future reinvestment**, with 0.5% annual dilution. Opening treasury is credited once. Future distributions are paid each year and are not added again as terminal cash. Thus the retained balance is zero under the stated convention.

The normalized ₹400 crore starting-cash case at 25 times exit, a ten-year horizon and an illustrative 10% annualized shareholder return requires about **13.28% annual company cash growth**. Recalculation reproduces the ₹724.65 price. That growth requirement is an expectations calculation, not evidence that such growth is achievable with all investment already funded.

The ₹650 crore opening treasury credit, approximately ₹26.17 per current share, is treated as current value. It remains provisional in the original case. This audit neither validates that cash ownership assumption nor converts it into a dividend commitment.

## Process consequence

Every prospective cash model should assign the undistributed balance to an explicit use: retained cash, investment, working capital, debt repayment or another shareholder claim. A terminal operating multiple and a cash balance are separate components. Cash can be added once after distributions and uses. No new framework rule, automation, frozen protocol or historical source was changed by this targeted check.
