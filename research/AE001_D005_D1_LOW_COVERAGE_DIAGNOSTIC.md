# AE001 D005-D1 Low-Coverage Failure Diagnostic

Status: FROZEN AFTER D005 RESULT, BEFORE D1 DIAGNOSTIC
Frozen: 2026-10-01
Live capital: DISABLED

## D005 result

D005 failed its frozen source-feasibility intersection gate.

Observed:

- READY sessions: 266 / 266;
- parser-rejected sessions: 0;
- total STO rows: 8,847,309;
- median usable stock-option symbols: 199.5;
- p10 usable symbols: 13.0;
- minimum usable symbols: 0;
- maximum usable symbols: 213.

Failed gate:

p10 usable symbols >= 75.

D005 remains FAILED regardless of D1 findings.

## D1 objective

Explain the discontinuous low-tail coverage without opening any return outcome.

D1 inspects only the already-sealed D005 report from workflow run 36809535891.

For sessions with usable_symbol_count < 75, report:

- session date;
- STO row count;
- accepted contract count;
- invalid-symbol count;
- distinct option-symbol count;
- same-session EQ-mapped symbol count;
- usable symbol count.

Also report the lowest 40 sessions and frequency of low-coverage sessions by
calendar month.

## Interpretation rule

D1 may distinguish:

- genuine source/surface sparsity;
- symbol invalidation caused by the frozen D005 row contract;
- expiry-calendar effects;
- other source-structural patterns.

D1 may NOT:

- change D005 viability thresholds;
- change D005 parser rules;
- relabel D005 as passed;
- create future-return labels;
- fit a model.

If D1 shows that D005 failed because its parser contract discarded otherwise
structurally usable source rows, a revised source feasibility study must use a
new ID: AE001-D006.

No prospective or live-capital claim.
