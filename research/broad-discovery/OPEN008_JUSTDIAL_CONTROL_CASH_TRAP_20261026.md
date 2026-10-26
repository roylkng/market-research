# OPEN008 | Just Dial control discount: what happens if cash remains trapped?

**Snapshot as of 26-Oct-2026.** Conditional researcher-imposed sensitivity only. **NOT a discounted-cash-flow intrinsic value, capital authorization, calibrated forecast, purchase limit, or amendment to HG009/H002/H003 source evidence.** The signed 19-Oct FY27 Q2 original issuer filing is known through public transcription, not archived as an original raw-byte receipt in this repository.

## The falsifiable premise

OPEN007 (merged PR #543, original Git blob anchored as `f0650a9c6dac7c22db3432634812e7119c7899a4`) established:
- Q2 exact issuer **85,049,032** shares × completed **26-Oct NSE ₹698.80** = **₹5,943.2264cr** observed equity market value.
- September gross current investments, current bank deposits and cash **₹6,113.95cr**, but reported **all book liabilities ₹940.61cr** give **₹5,173.34cr accounting cashlike net of recorded claims**, not necessarily legally unrestricted/free to minority owners. This already includes deferred revenue and leases. Do not subtract deferred revenue twice.
- Six months after-tax CFO net of selected PPE, intangible purchases and lease cash **₹95.34cr**. Multiplying by 2 to **₹190.68cr** is a *mechanical illustrative annual selected cash*, NOT forecast profit, sustainable parent FCFE or shareholder dividends.
- Original FY2026 Just Dial annual report says **no company dividend after FY2014–15 through FY2025–26**, and no shares bought back during five years preceding FY2026; promoter group ~74.14%, mainly Reliance Retail Ventures. Historic non-distribution does not prove future capital-allocation intent. Original FY26 annual issuer report reproduced at https://financialfilings.com/filings/just-dial-limited/annual-report/2026/57348415/ .
- Q2 FY27 issuer financial balance and cash reproduced from the company-signed filing https://financialfilings.com/filings/just-dial-limited/interim-quarterly-report/2026/74228064/ . Direct BSE original file download blocked; no canonical original SHA.

**Do not confuse cash invested by a company with cash distributed to shareholders.** Financial assets may earn interest while retained, but the shareholder may discount deferred cash realization at a higher required equity return, even if both returns are positive.

## Single explicit conditional model

Assume $N=₹5,173.34cr$ *net-book-liquidity reference*; $C=₹190.68cr$ annual cash after selected uses; company retains it until a hypothetical final realization date `T`. Treasury grows at assumed net rate `r`. Cash generation grows at hypothetical `g`. End-of-period operating franchise is hypothetically valued at `m × next-year C`. Equity shareholder demands assumed `k` annual discount. No distributions until the chosen horizon.

```text
Cash_like_at_T = N × (1+r)^T
Retained_operating_cash_at_T
    = SUM[t=1..T] C × (1+g)^(t-1) × (1+r)^(T-t)
Terminal_franchise_value_at_T = m × C × (1+g)^T
Conditional_present_equity_value
    = (Cash_like_at_T + Retained_operating_cash_at_T
       + Terminal_franchise_value_at_T) / (1+k)^T
```

This counts each illustrative annual operating cash collection **once**, at terminal retention, not as a separate immediate distribution. All book liabilities are pre-netted *once* in original N. No after-realization taxes, changes in liabilities, fresh capex beyond selected CFO definition, changes in share count, fund fees, acquisitions, fraud, dividends, dilution, costs or broker price depth are modeled.

**Base sensitivity inputs are uncalibrated:** treasury net 6%/year, investor hurdle 12%, no cash growth, 6× terminal annual selected operating cash. Horizon is an assumed no-distribution period, **NOT a known plan**.

| Hypothetical no-distribution horizon | Conditional PV of issuer equity | Change versus ₹5,943cr dated cap |
|---|---:|---:|
| **Immediate full net-book-liquidity release** | **₹6,317cr** | **+6.3%** |
| 3 years | ₹5,632cr | −5.2% |
| 5 years | **₹5,187cr** | **−12.7%** |
| 10 years | ₹4,161cr | −30.0% |

Even the **unrealistic immediate full release** plus a 6× selected-cash operating franchise yields only ~6.3% above the observed share capitalization, far below a conservative 20–30% margin-of-safety test. This is not a trade target, and the assumed franchise multiple is neither sourced nor a probability estimate.

Other five-year sensitivities: zero operating-cash growth and 8× terminal franchise yields ₹5,404cr (−9.1%); 5% growth with 6× yields ₹5,427cr (−8.7%); 5% growth and 8× yields ₹5,703cr (−4.0%); a lower 10% shareholder hurdle gives ₹5,676cr (−4.5%); a substantially higher 10% treasury yield produces ₹6,037cr (+1.6%). These values are **illustrations of controlling-shareholder cash realization risk**, not an empirical range of fair values.

## Thesis-falsifying decision

1. The historical no-dividend policy, 5-year absence of buybacks and concentrated control can explain why a supposedly “net cash greater than market cap” stock **does not deliver positive risk-adjusted returns**. At an illustrative 12% required shareholder return versus 6% retained cash yield, delay destroys potential upside even if the underlying asset statements are genuine.
2. The base operating selected cash rate **₹190.68cr is not normalized owner FCFE**. Any lower verified sustainable margin tightens the value interval further. Its use here is deliberately transparent so we cannot assign false intrinsic-value confidence.
3. If the cash earns investment return plus operating cash remains in the company and shareholder prices it as an ongoing controlled business, the terminal multiple need not ever converge to standalone liquid book value. No current buyback or dividend catalyst is verified.
4. Exact company assets may be legally redeemable securities at fair NAV, but **ordinary shareholders cannot redeem corporate funds directly**. Cash trapped in a publicly listed controlled entity is categorically different from a bank deposit belonging to an individual.

**Research decision: downgrade the apparent Just Dial “negative enterprise value” claim to a HIGH PRIORITY CAPITAL-ALLOCATION INVESTIGATION, NOT BUY.** We still rank it above several speculative asset situations for accounting transparency, but it has **not** demonstrated an attractive after-cost expected shareholder return.

## Next evidence that would change our conclusion

- Original issue-signed current fund-by-fund portfolio with restrictions, taxes and broker settlement liquidity.
- Reliance Retail Ventures and Just Dial board capital-allocation disclosures: **formal buyback or shareholder cash distribution**, new related-party acquisition or strategic cash usage. Voluntary distribution can change the cash-trap economics.
- True normalized FY27 run-rate owner cash after marketing costs, lease, capex and renewing paid merchant campaigns, not simply total statutory PAT plus investment gains.
- Official funded corporate restructuring or verifiable access to controlling shareholder transaction costs, buyback legal cancellation and funding.
- 2026-27 diluted shares, real order depth and any actual recurring after-cost shareholder capital return.

The plain-code evaluator `scripts/open008_justdial_cash_trap.py` accepts only the pinned original OPEN007 input blob, and test suite forbids falsified original SHA, historical dividend or buyback, uncalibrated probability claims and live-capital promotion. No new prospective price returns are used.
