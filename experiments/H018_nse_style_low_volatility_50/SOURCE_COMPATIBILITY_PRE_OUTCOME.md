# H018 official-source compatibility freeze before first outcome

Status: **FROZEN BEFORE ANY H018-v1 SELECTION OR OUTCOME IS OPENED**

This note changes source-format compatibility only. It does **not** change H018-v1 dates, company eligibility, liquidity rule, low-volatility score, top-50 selection count, semiannual schedule, execution convention, benchmark identity, random seed, friction, comparators, or pass/fail gates.

## Observed official archive boundary

The retained H018 checkpoint artifact from workflow run `34265875607` contains 516 complete day checkpoints and 1,220 retained exact source files. Those checkpoints cover essentially the 2016-01-01 through 2017-05-31 portion of the frozen acquisition range.

A pre-outcome official-source-only probe was then frozen and run as workflow `H018 official static index source probe`, run `34326782646`, artifact `10094085611`. `market_selection_outcomes_opened` was explicitly `false`.

Representative official daily index files were retrieved successfully from all tested current official static hosts:

- `https://www.niftyindices.com/Daily_Snapshot/ind_close_all_28112014.csv`
- `https://archives.nseindia.com/content/indices/ind_close_all_28112014.csv`
- `https://nsearchives.nseindia.com/content/indices/ind_close_all_28112014.csv`

All three 2014 responses were byte-identical with SHA-256:

`925f19113b87bede61539ee06d8cde39686c23cb53c41072454c8695280db388`

The same byte-identity was observed for the tested 2015 and 2016 daily files across the official hosts. Therefore the pre-2016 blocker is not absence of the daily official archive.

## Historical index name

The exact 2014-11-28 official daily file identifies the broad 500-stock benchmark as `CNX 500`.

The exact 2015-11-16 and 2016-01-01 official daily files identify the same benchmark as `Nifty 500`.

India Index Services & Products Limited announced the rebranding of `CNX 500` to `Nifty 500`, effective 2015-11-09. Official press release:

`https://www.niftyindices.com/Press_Release/ind_prs22092015.pdf`

This establishes a source-label change, not a benchmark-identity change.

## Historical date delimiter

The pre-outcome acquisition-only accelerator run `34328827482` retained official source bytes but did not calculate H018 selections or outcomes. Its parser diagnostics exposed 59 valid 2014 common-session files whose broad-index row is `CNX 500` and whose `Index Date` uses `DD/MM/YYYY` rather than `DD-MM-YYYY`.

For example, the retained official 2014-06-09 index snapshot contains the exact row prefix:

`CNX 500,09/06/2014,6164.55,...,6196.7,...`

The prior compatibility parser rejected these rows only because it split the source date on `-`. The benchmark label and OHLC data were otherwise valid.

## Frozen H018-only compatibility rule

Before the first H018-v1 outcome is opened, the H018 market parser is allowed to resolve the frozen Nifty 500 benchmark using exactly this rule:

1. First use the existing strict `Nifty 500` parser unchanged.
2. Only if that parser fails and `session_date < 2015-11-09`, accept exactly one source row whose normalized `Index Name` is exactly `CNX 500`.
3. The source row's own date must parse as exactly one of `DD-MM-YYYY` or `DD/MM/YYYY` and equal the requested `session_date` exactly. No other delimiter, field order, inferred transposition, or fuzzy parsing is allowed in the CNX compatibility path.
4. `Open Index Value` and `Closing Index Value` must both be finite and strictly positive.
5. Multiple `CNX 500` rows, missing values, a date mismatch, or any other ambiguity must fail closed.
6. `CNX 500 Shariah`, other CNX indices, aliases inferred by substring, or any post-2015-11-08 `CNX 500` row are not accepted by this compatibility rule.

This rule is H018 acquisition plumbing only. Shared H015/H016/H017 parsers remain unchanged.

## Checkpoint reuse rule

A subsequent H018 run may restore exact retained checkpoint/raw-source artifacts before acquisition begins. Restored bytes must continue to pass per-source SHA-256 verification. The runner may acquire only unresolved dates after restore.

Checkpoint reuse changes runtime and durability only. It cannot change any frozen H018 research semantics.
