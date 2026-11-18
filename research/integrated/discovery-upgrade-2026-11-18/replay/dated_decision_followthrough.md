# Follow-through of decisions actually recorded before today

**Observed: 18 November 2026.** These four judgments existed before today's close. They were recovered from dated repository records, not reconstructed after seeing the subsequent prices.

| Company | Actual recorded decision | Recorded price and date | 18 Nov official NSE close | Raw reference-price change |
|---|---|---:|---:|---:|
| SEAMEC | No fresh purchase, wait for price or evidence | ₹1,526.60, 9 Nov | ₹1,535.50 | **+0.58%** |
| TD Power | Watch valuation and capital returns, no new buy | ₹635.45, 16 Nov | ₹632.30 | **−0.50%** |
| WABAG | Watch contract loss and cost exposure, no new buy | ₹1,894.40, 16 Nov | ₹1,867.40 | **−1.43%** |
| Xpro | Watch ramp returns on capital, no new buy | ₹1,194.80, 16 Nov | ₹1,262.00 | **+5.62%** |

**Interpretation:** Xpro is the clearest early price move against the wait decision. Keep it visible. It is not yet a proven false negative because the decision concerned multi-year owner returns and funded expansion, while this observation spans two closing prices. Similarly, the two declines do not prove that waiting was correct. SEAMEC's small rise does not settle its normalized earnings and fleet-funding case.

## Real decision clocks

- SEAMEC's memo was committed to main on **9 November, 23:35:55 IST**, after the referenced close. Commit `1cf0ed8093154044d4477ea1ef724e781a4ddfb5`, file `research/company_cases/seamec/2026-11-09.md`.
- The TD Power, WABAG and Xpro note was first committed on **17 November, 11:04:53 IST**, during the following market session. It explicitly used the previous day's closes. Commit `dee7e6c49686436859a4f189c92cb69ef12810b0`, file `research/integrated/decision-review-2026-11-17.md`. The first version contains all three recorded prices and WAIT judgments. Its later correction concerned the TD Power drawdown reference. PR #619 remains open and unmerged.

Consequently these are **changes from documented reference prices**, not returns from executable post-decision purchases. They must not be presented as money the user earned, lost or necessarily could have captured.

## Source verification

All four old prices were independently matched to their original NSE UDiFF rows with exact symbol, ISIN and EQ series. Raw November 9 archive hash: `9b1388cbf80206119e04efa57779b2637b93fa37fd81c974ce978858f1b3dce2`. November 16: `4b092142ecfdd80eb359a62a9146a598a5fad274ef84930d0d7caf0e9eeaf645`.

Today's original NSE November 18 ZIP was checked against hash `9b434afe659efc880b74ff68f9643038e5876d23e6abf5046a620e044f1a725c`, then its CSV bytes were matched to the source already captured this session. All four terminal rows have the same end-point ISIN and EQ series as the old references.

No complete intervening dividend, split, bonus, rights or other corporate-action ledger was cleared. Same end-point identity is not proof of total-return continuity. Prices exclude distributions, execution costs and taxes. Cash/index alternative returns, portfolio weights and path risk were not calculated. Therefore **no true opportunity-cost return or investment success rate is asserted**.

The companion JSON retains exact original decisions, first verified commit timestamps, original/terminal source provenance, calculations and null economic-return/false-negative fields. No old decision or frozen result was edited. The bounded search found no earlier qualifying priced TD Power/WABAG/Xpro decision in the reviewed files. The November 15 handoff explicitly established no fresh prices or buy approvals, so it was excluded as an outcome anchor.

Sources: [SEAMEC original memo](https://github.com/roylkng/market-research/blob/1cf0ed8093154044d4477ea1ef724e781a4ddfb5/research/company_cases/seamec/2026-11-09.md), [first November 17 three-company decision](https://github.com/roylkng/market-research/blob/dee7e6c49686436859a4f189c92cb69ef12810b0/research/integrated/decision-review-2026-11-17.md), [official November 18 NSE prices](https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261118_F_0000.csv.zip).
