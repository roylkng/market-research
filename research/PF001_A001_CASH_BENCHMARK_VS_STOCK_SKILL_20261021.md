# PF001 A001: cash-avoidance returns are not stock-selection alpha

**Review date:** October 21, 2026. **Original fund observation:** October 19, 2026.  
**Class:** posthoc original-source measurement integrity. **No live trading.**

## Finding

Original PF001 prospective-validation book: 23 official sessions, 100% average cash, no paper entries, no open or closed stock positions, no nominal fund NAV change. Its Nifty 500 **price** benchmark declined 4.1604978% and the original attribution reports **+4.1604978 percentage points** of active performance and information ratio **2.6650**. These are mathematically valid **cash-versus-falling-index** comparisons, not stock-picking skill. The selection-skill information ratio must remain **null**, not 2.6650 and not zero.

The development PF001 book retained a single still-open **ARVIND** paper position, no closed positions and 95.3945% average cash. Original net return -0.6118642%, benchmark -4.1604978%, active difference +3.5486336 points and raw ratio 2.3436. Without a mature independent entry/exit track record, that number cannot be assigned to successful company selection either. One paper position amid a large cash sleeve is not 23 independent stock predictions.

The original paper-fund book has two explicit blocked components, source timing and unimplemented fund constraints. An all-cash result because the stock-entry gate failed is not proven market-timing skill.

## Six immutable original source receipts

The exact October 19 validation and development fund states, attribution states, and daily attribution summaries are independently pinned by Git blob SHA and SHA-256 raw receipts. Four state/attribution originals were copied byte-for-byte into the independent dated audit snapshots. The two original daily run summaries are linked rather than rewritten.

All six source documents reproduce the original v1 summary mathematics, last-session event linkage, fund-state SHA, share of NAV held in cash, portfolio entrants, open/closed positions and benchmark relationship. The source main commit is e91133400ff5028a4f638f21a566be65b843debd. Later PF001 changes cannot retrospectively alter this receipt. The original v1 information ratio remains in the new signed report with a *NOT_STOCK_SELECTION* label.

## Correct interpretation

| Legacy measurement | Historical value | Separate stock-selection evidence |
|---|---:|---|
| Validation raw net active | +4.1605 percentage points | No stock-selection return measured |
| Validation raw information ratio | +2.6650 | Selection information ratio null |
| Validation source priced holdings | Zero | All 23 sessions cash only |
| Development raw active | +3.5486 percentage points | One still-open paper position |
| Development raw information ratio | +2.3436 | Selection information ratio null |
| Development closed positions | Zero | No realized position-level excess |

The original attribution code is not "wrong arithmetic". The risk is a consumer calling this ratio stock-market forecasting alpha, recommending an investment, or extrapolating to 50% annual compounding. Any of these would be scientifically ungrounded.

## Forward-only promotion requirements

- At least one truly source-timestamp-qualified paper stock entry followed by an independently matured exit, and ultimately many independent trading entry dates.
- Original NSE source share basis, corporate actions, actual entry feasibility and after-cost price returns.
- Attribution for cash versus risk-free/cash benchmark separated from selected-stock excess versus comparable security/sector benchmark.
- Capital exposure and number of matured independent selection cases disclosed alongside every stock-skill metric.
- Stock-selection win rates and signal information ratios must remain null when not estimable.
- The old PF001 v1 source and frozen portfolio contracts are preserved without backfill, amendments, or hidden rewrites.

Canonical audit: research/paper-funds/PF001/audits/pf001-a001-stock-selection-skill-v1.json.
Replay script: scripts/materialize_pf001_a001.py --check.
Regression tests: tests/test_pf001_a001_skill_guard.py.

**No new expected returns, buy ratings, realized alpha, investment approvals or live capital.**
