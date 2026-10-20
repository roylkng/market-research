# L001 P019: Sun TV FY26 franchise-rights cash bridge, source red-team

**Investigation date:** October 20, 2026. **Annual reporting date:** March 31, 2026.  
**Source:** [Sun TV Network's own FY25–26 annual report](https://www.suntv.in/pdf/Finance/2025/Sun_TV-41st_Annual_Report_25-26.pdf), actual PDF pages 77–78, 160, 184, 228 (zero-based and page-numbered financial statements).  
**Identity:** SUNTV, ISIN INE424H01027. **Status:** retrospective original-filing research only. No October 15 prediction, current-price buy rating or normalized owner cash.

## The discrepancy that matters

The original signed L001 P016 100-company accounting report reports FY26 Sun TV consolidated operating cash ₹1,801.64cr, PPE cash purchases ₹83.91cr and intangible cash purchases ₹2,130.31cr. Therefore:
- CFO less PPE: **+₹1,717.73cr**, a badly incomplete proxy.
- CFO less PPE and all intangible purchases: **−₹412.58cr**, potentially too punitive if the one-time franchise acquisition is mixed into recurring spending.

The FY26 original Sun TV annual report supplies independently identifiable **three different representations** of its SunRisers Leeds (formerly Northern Superchargers) investment:

| Original issuer source | Audited FY26 observation | Amount ₹cr | Meaning |
|---|---|---:|---|
| Standalone cashflow, PDF page 78 | Payment towards investment in subsidiary | **1,190.88** | Parent's cash outflow to acquire the subsidiary |
| Consolidated Note 5, PDF page 184 | Addition to the franchise-right intangible asset | **1,190.88** | Consolidated recognition of acquired franchise-right asset |
| Consolidated Note 46(C), PDF page 228 | GBP 100.5m consideration equivalent | **1,184.99** | Deal consideration stated at a different translation/accounting basis |
| Consolidated Note 5, PDF page 184 | Post-acquisition currency translation | **+57.39** | **Noncash** change to franchise-right carrying value |
| Consolidated Note 5, PDF page 184 | March 2026 franchise-right carrying value | **1,248.27** | Asset carrying value, **not** 2026 cash paid |

The filing explicitly identifies an **asset acquisition of cricket franchise rights under Ind AS 103**, effective July 28, 2025, with 100% subsidiary ownership. The ₹5.89cr difference between reported deal consideration and recognized franchise-right initial cost is not allocated without a supporting note/payment schedule.

## Audited group/parent cashflows must not be added together

| FY26 consolidated ₹cr | Value |
|---|---:|
| Operating CFO | 1,801.64 |
| Cash purchases of PPE | (83.91) |
| **Cash purchases of all intangible assets** | **(2,130.31)** |
| Simple CFO less both categories | **−412.58** |
| Acquired franchise-right initial recognized amount | 1,190.88 |
| **Cash intangible spending after a *conditional* franchise deduction** | **939.43** |
| **CFO less PPE and this conditional remainder** | **+778.30** |

The conditional arithmetic is **not a confirmed original cashline allocation**. Matching the initial recognized asset and the parent investment proves this acquisition is material and separately identified, but it does not prove precisely which original individual cash receipts are included in the consolidated ₹2,130.31cr line. Reconciliation to the group consolidation worksheet and issuer payment records is still required.

**Do not add standalone ₹1,190.88cr subsidiary investment to consolidated franchise cash spending:** consolidation eliminates parent intercompany investment, leaving the acquired underlying franchise asset. Similarly, ₹57.39cr foreign exchange translation is not extra franchise cash paid.

For comparison, standalone FY26 CFO ₹1,736.10cr less PPE ₹71.17cr less its other intangible cash ₹938.51cr is **₹726.42cr**, before the separate subsidiary payment. This independent accounting-scope perspective is consistent with significant non-franchise content rights investment, but it does **not** prove the residual ₹939.43cr is maintenance. FY25 consolidated CFO less PPE and intangibles was **₹1,280.65cr**. We cannot extrapolate either year without identifying when television, OTT, film and sports rights require replacement.

## What changes the economic decision

The **+₹1,717.73cr** figure is not owner cash. The **−₹412.58cr** figure is not a proven sustainable annual cash drain. The acquisition-excluded **+₹778.30cr** is a conditional, unreconciled historical sensitivity, not a forecast of future group shareholder cash or a fair value.

An investor-grade dossier now requires:
1. Underlying FY26 bank/payment cashline showing which subsidiary acquisition funding transactions were included in consolidated intangible purchases, exchange rates and transaction costs.
2. Film/TV rights content cash recurrence in FY23–FY27, including replacement rights, broadcast/OTT economics, rights amortization and current outstanding payments.
3. SunRisers Leeds franchise earnings and incremental cash returns, ownership, acquired intangible impairment sensitivity and ongoing capex.
4. Parent-claimable cash, financial assets/restrictions, taxes, dividends, minority ownership, fully diluted share count and current dated official NSE execution basis.
5. Multi-year normalized owner earnings and independently calibrated bear/base/bull valuations **before** claiming undervaluation.

## Reproducibility and source limitations

Prior original XBRL-derived cash is pinned to L001 P016 Git blob 00241232ca88aa8f1217407be0929e686335f928 and source analysis P014 Git blob 931f7954c3270ce157b38f22ef06bde68aaad4db. The new P019 packet deterministically verifies both prior bytes and the exact annual-report *visually confirmed* page-level amounts, with signed research-only reconciliation.

The source annual PDF's complete raw bytes are **not yet guaranteed to be stored** in the repository. A separate original issuer source capture attempts exact first-party PDF download, validates the named original pages and records a real UTC capture timestamp and SHA-256. It archives the full PDF if at most 8MB, otherwise content-addressed original five-page excerpts, explicitly distinguishing that from full-original archival. A blocked HTTP request or missing page evidence produces a nonpromotable failure receipt. Do not treat a successful excerpt as full source preservation.

Canonical evidence: research/l001/l001-p019-suntv-franchise-rights-cash-bridge-v1.json. Test with scripts/materialize_l001_p019_suntv.py --check and tests/test_l001_p019_suntv_rights.py. Original 100-company HG009 cohort and all prospective price/event ledgers are unchanged. **No buy rating, no owner cash yield, no 50% annual target, no live capital.**
