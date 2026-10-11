# HG007 P029: Original June QIP object cash-use versus Ashok Cloud demerger

Research-only source review frozen **11 October 2026 IST**.
**No current cash, executed demerger, equity valuation or investment alpha**.

## Reproduced independent originals

1. NSE original 21-page monitoring agency PDF, issuer Anant Raj
   Limited, filed **8 August 2026**:
   https://nsearchives.nseindia.com/corporate/ANANTRAJ_08082026182321_Intimation_Monitoring_Agency_08082026.pdf

   Original raw PDF SHA-256:
   13d0c6237f6273dfeefacb1c49003d339e4285280a6288f1589b4df44613a45d.
   21 text-page hashes plus captured source/date are pinned by
   HG007 P028's independent raw PDF/receipt. The earlier BSE
   original attachment returned HTTP 404 and remains recorded as
   unavailable, not rewritten as successful.

2. Anant Raj / Ashok Cloud **proposed 48-page composite scheme**,
   original SHA-256:
   76db08d6210360291e81ab7813302067acdb34206cd03561db1ce0ba7ffe528f.

   Exact existing P026 22-clause source review is retained and
   byte-hash-pinned. Its proposed cloud QIP cash/debt/capital
   transfer clauses have no independently verified rupee balances.

## Original issue objects, cut off **30 June 2026** (INR crore)

| QIP use | Allocation | Used before Apr | Used Apr-Jun | Cumulative used | Unused |
|---|---:|---:|---:|---:|---:|
| Data centre / cloud subsidiary | 440.00 | 52.03 | 29.23 | 81.26 | 358.74 |
| Other property construction | 164.40 | 7.13 | 2.86 | 9.99 | 154.41 |
| Land / development rights | 185.00 | 45.48 | 25.44 | 70.92 | 114.08 |
| Debt repayment | 125.00 | 125.00 | 0.00 | 125.00 | 0.00 |
| General corporate purposes | 157.80 | 95.87 | 0.00 | 95.87 | 61.93 |
| QIP issuance costs | 27.80 | 24.49 | 2.48 | 26.97 | 0.83 |
| **Gross QIP total** | **1100.00** | **350.00** | **60.01** | **410.01** | **689.99** |

Source: original monitoring report human PDF pp 11-14. The
subtotal for cloud specifically is on page 12, land and debt
on p13, remaining corporate/fees/aggregate totals on p14.

The monitored gross issue was 1100.00 and net after forecast
issuance expenses was 1072.20. Avoid comparing the net
1072.20 figure to a gross 410.01 utilization numerator
without explicitly including the issuance-expense object.

## Critical difference between object earmark and cash assets

The originally monitored, historically unspent **cloud allocation**
is **358.74cr**. The complete unutilized 689.99cr includes
**331.25cr allocated to noncloud issue objects**.

**Neither amount is verified as October11 bank cash or cloud
newco transfer amount**. Infomerics reported 81.26cr used
toward funding Anant Raj Cloud as of June30, but this does
not specify current post-spend fixed-asset value, resulting
company ownership, net assets or cash flow.

Source report p8 says QIP proceeds passed via current/cash-credit
accounts, mixed with other unrelated debits and credits. The
agency relied in part on a chartered-accountant certificate
and only sample expense invoices. Infomerics expressly states
that the monitoring report is not an independent financial audit.

The original FDR instrument table on p18 reports **690.01cr**
fixed deposits as of June30, vs the utilization table's
**689.99cr** unutilized amount. The 0.02cr difference is
explicitly quarantined, not made to disappear through
rounding, interest assumptions or a guessed bank statement.

Several deposits matured in July, August, and September;
others were shown maturing in November. This original
**June30** inventory is not a verified October cash schedule.

## Exact legal demerger attribution gate

P026 original 48-page proposed scheme contains, among other
clauses:

- 1.13 earmarked cash/QIP investment in cloud business may
  be included in the transferred undertaking.
- Debt directly used for cloud may transfer; general-purpose
  borrowings may transfer pro-rata to historical assets.
- Intra-group balances may cancel and relevant charges/pledges
  may follow transferred assets.
- Existing ARL-owned Ashok Cloud shares are proposed to remain
  as parent holdings while eligible ARL shareholders may also
  receive newco stock, creating a two-layer attribution issue.
- Shareholder/court approvals and actual scheme effective date
  have not been verified.

A 440cr original development earmark and 358.74cr unspent as of
June do not determine how much **actually** transferred,
or whether any amounts already reflected in ARL's reported
asset/cash balance must be removed to avoid double counting.

**Never add the 358.74cr to Ashok Cloud fair value while
also retaining the same cash in the continuing parent.**

## Executable reproducibility

- src/marketlab/hg007_anantraj_qip_cash_ledger.py
- scripts/reconcile_hg007_anantraj_qip_cash.py
- tests/test_hg007_anantraj_qip_cash_ledger.py
- .github/workflows/hg007-anantraj-qip-cash-source-review.yml

The source review pins each original source by SHA-256 and
Git blob ID, checks original monitoring PDF per-page text
hashes, and exact decimal arithmetic for all six objects.
A missing source, altered number or changed proposed
legal cash/debt treatment fails closed.

On merge, generated evidence is kept permanently at:

research/hg007/anantraj-qip-monitor-june2026/p029-source-object-cash-ledger-v1.json

This is a **historic accounting classification**, not a
pre-market investment signal or current equity valuation.

## Next needed sources, not inferable from QIP monitoring

1. Auditor-signed source-specific QIP transaction and bank
   deposit inventory as of **latest pre-effective balance-sheet date**.
2. Cash at ARL parent vs ARCPL subsidiary, investments, loan
   receivables, committed but unpaid invoices and restricted
   deposits, with intragroup netting.
3. Cloud and noncloud standalone division asset schedules
   including Manesar/Rai real estate, general-purpose loan
   allocation and charges.
4. Court-approved final scheme, effective date, actual
   record-date capital and the two separate shareholder claims.
5. Cloud **actual earnings and free cash flow**, not a QIP
   cash capitalization or unaudited monitoring-object proxy.
6. Certified borrowing/debt covenants and liabilities
   transferred at the actual cut-off date.

The existing HG006 completion-probability publication blocker,
multiplicity-protected alpha gate, PF001 portfolio gate
and live-capital prohibition all remain intact.
