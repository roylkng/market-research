# HG009 P018: Reverse owner-cash sensitivity (research only)

**As-of:** 2026-10-16. **Price observation:** 2026-10-15 (historical official NSE EQ close). **Status:** arithmetic screening, not valuation or investment advice.

## Objective and source boundaries

Determine *how much annual, parent-attributable distributable owner cash* the historical basic-share market capitalization would need to support at hypothetical 12x, 16x and 20x owner-cash multiples. This deliberately **does not** estimate plausible growth or an expected share return. The terminal multiple is not calibrated. Future price appreciation scenarios ignore dividends, financing, equity issuance, net cash/debt, tax and transaction costs. They must not be used as price targets.

Sources already committed in this repository:
- `research/hg009/hg009-p017-ace-two-year-cash-bridge-v1.json`: ACE audited FY25/FY26 consolidated CFO and PPE; October 15 cross-date illustration.
- `research/hg009/hg009-p014-economic-symmetry-and-cash-v1.json`: FY26 ACUTAAS and ACE original-source accounting proxy, October 15 reference close.
- `research/hg009/hg009-p016-q1-source-attestation-v1.json` and `registry/hg009_p015_ace_acutaas_q1_sources.json`: June 2026 standalone basic share counts and independently archived original Q1 issuer HTML. Shares are **not** October fully diluted shares.

The assumptions below use only historical *basic* capitalization, not adjusted enterprise value or verified shareholder claims. Mixing periods is deliberate as a falsification screen and **not** an accounting-comparable owner earnings calculation.

## Exact hypothetical formula

At hypothetical terminal multiple `M` and assumed equity uplift `g`:
`required_owner_cash_cr = historical_basic_equity_cap_cr * (1 + g) / M`.

| Company | Oct 15 cross-date basic cap (₹Cr) | FY26 CFO minus PPE proxy (₹Cr) | Proxy yield |
|---|---:|---:|---:|
| ACE | 13,764.39 | 324.01 | 2.354% |
| ACUTAAS | 25,646.15 | -35.8052 | -0.140% |

### Required owner cash for a hypothetical +50% equity valuation (₹Cr annually)

| Multiple | ACE | ACUTAAS |
|---|---:|---:|
| 12x | 1,720.55 | 3,205.77 |
| 16x | 1,290.41 | 2,404.33 |
| 20x | 1,032.33 | 1,923.46 |

This is an *inverse valuation equation*: it does **not** mean the company can earn these amounts, or that the market will pay the assumed multiple. Because the ACUTAAS historical CFO-minus-PPE proxy is negative, no positive growth multiple should be quoted against that proxy. For ACE, most FY25–FY26 proxy improvement came from lower PPE cash spending, not a CFO increase. Therefore extrapolating FY26 proxy as a durable baseline is particularly dangerous.

## Investment underwriting gaps

1. **Share denominator:** Obtain latest issued shares, outstanding ESOPs, warrants, convertibles, equity capital movements, and parent/minority split through the decision cutoff. Q1 standalone diluted EPS does not establish fully diluted October shares.
2. **Cash ownership:** Reconstruct consolidated-to-parent owner cash after maintenance capex, working-capital cycle, interest, leases, taxes, reinvestment, and noncontrolling claims. Distinguish reversible financial security purchases from productive capex.
3. **Incremental ROIC:** Underwrite capacity, commissioning, utilization, asset turns, incremental margin, tax rate, and *incremental* invested capital. A reduction in annual capex is not proof of improved ROIC.
4. **Valuation discipline:** Explicitly model net debt/cash, share changes, dilution, per-share dividends, and a scenario-calibrated terminal multiple. Include trading frictions and downside.
5. **Prospective design:** Do not change HG009 frozen selection or interpret post-October-15 filings as ex-ante evidence. Record all new hypotheses as post-hoc until independently pre-registered.

**Gate:** Both ACE and ACUTAAS remain `capital_eligible=false`, `expected_return=null`, and `owner_cash_verified=false`. No live trade or company rank is created.

## Next falsification

For ACE test whether recurring normalized PPE spend resembles FY25 (₹221.00Cr) or FY26 (₹93.26Cr) and why. Holding FY26 CFO constant, restoring FY25 PPE spending makes the CFO-minus-PPE **proxy** ₹196.27Cr, only 1.426% of the cross-date basic capitalization. Do not treat this proxy as owner cash. For ACUTAAS resolve whether FY26 PPE ₹327.98Cr is capacity-building spend with independently provable future cash returns, or structural maintenance/reinvestment. Until then a forward 3-year valuation is not source-ready.
