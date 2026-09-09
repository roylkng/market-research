# H018 equity-session benchmark-gap rule, frozen before first outcome

Status: **FROZEN BEFORE ANY H018-v1 SELECTION OR OUTCOME IS OPENED**

This rule is source-completeness plumbing only. It does not alter H018-v1 dates, eligibility, liquidity, low-volatility score, top-50 selection, semiannual schedule, execution convention, benchmark identity, friction, random seed, comparators, or pass/fail gates.

## Deterministic residual gap

Two independent acquisition-only resolver runs reproduced the same final state from the frozen source corpus:

- 879 fully sourced common equity/index sessions;
- 426 confirmed no-session calendar days;
- exactly three unresolved dates: `2014-12-15`, `2015-03-12`, and `2015-07-08`.

For each of the three residual dates, an official NSE cash-equity bhavcopy exists and parses successfully for the exact date. The Nifty 500/CNX 500 daily benchmark row could not be recovered from any tested official daily source.

A dedicated pre-outcome source probe then tested both NSE Indices static hosts for each exact dated daily snapshot. Each returned the NSE Indices HTML application shell rather than CSV. A warmed-session POST to the official historical-data endpoint also redirected to the site shell and returned HTML rather than the documented JSON response. No H018 selection or outcome file was read or created by these probes.

## Frozen representation

The three dates must remain **equity trading sessions** because their official cash-equity bhavcopies are valid. They must not be:

- labeled holidays;
- deleted from the equity session calendar;
- forward-filled with a benchmark value;
- assigned an inferred Nifty 500 value;
- silently ignored.

They may be represented by checkpoint status `EQUITY_SESSION_INDEX_GAP` with:

1. the exact retained official NSE bhavcopy bytes and SHA-256;
2. the exact session date;
3. explicit metadata that no benchmark value is available for that date;
4. a reference to the frozen three-gap source probe.

During market reconstruction, these checkpoints contribute the equity session and all parsed EQ bars exactly like a common session, but contribute no entry to the Nifty 500 index map.

## Hard benchmark-availability gate

H018-v1 does not use Nifty 500 values to construct the candidate universe or low-volatility score. The benchmark is used only by realized outcome evaluation, which computes benchmark return from each cohort's entry-date open and exit-date close.

Therefore, after the five frozen cohorts are constructed and **before any outcome is attached**, the runner must fail closed unless every frozen cohort `entry_date` and `exit_date` has an actual retained Nifty 500/CNX 500 benchmark row in the reconstructed index map.

No interpolation or substitute index is permitted at an entry or exit endpoint.

If all ten required endpoints are sourced, the three mid-period benchmark gaps are irrelevant to the frozen benchmark-return calculation and H018-v1 may proceed unchanged.

## Scope lock

This exception applies only to the exact three dates listed above and only because official equity-session evidence exists while the benchmark source is unavailable. Any additional equity-session benchmark gap requires a new pre-outcome evidence freeze. Once H018 outcomes are opened, this rule may not be expanded to rescue the result.
