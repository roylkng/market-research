# H021-P025: reviewed prospective weekly consensus calendar supersession

**Review date:** 2026-10-30. **Effective week:** Monday 2026-11-02 through Sunday 2026-11-08.
**Research only.** No price/return outcomes, portfolio decisions or live capital are authorized by this change.

## Why

The immutable 2026-09-06 v1 calendar leaves Sunday 2026-11-08 in
`unresolved_special_dates`. On 2026-10-19 NSE issued the original official
capital-market circular **NSE/CMTR/76941**, confirming November 8 as a Sunday
Muhurat trading session. The v1 weekly gate must therefore refuse to treat
Friday November 6 as the final session. The authoritative collector must run
on Sunday after the session instead. The separate H021-P023 source-clock
amendment already sealed these original documents and SHA-256s.

## Verified source chain

- NSE original: https://nsearchives.nseindia.com/content/circulars/CMTR76941.pdf
- Original circular PDF SHA-256:
  `ce94ee1c54d98eccdf3c30fa0673ae2b6a49ea4ed4a72fb83d826f4359f71d58`.
- Pre-existing H021-P023 approved source amendment SHA-256:
  `618f143a76696cae500dec137db834c040fb861851998e2257d8f53bcc43f783`.
- **Unmodified original** v1 calendar Git blob:
  `9ac614820a67b0f7b20d8170d15b84df3c996b62`.
- **Unmodified original** v1 calendar payload SHA-256:
  `2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce`.
- Proposed v2 calendar:
  `research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v2-Nov08-Muhurat.json`.
- v2 Git blob: `fd151df6ad8fcee88fff6d9c3ac700c0d38c9153`.
- v2 canonical payload SHA-256:
  `d3de65ceb2038f8ea96d455afb272a9d72f4a411af7d76d6b5bf1941c2bb5266`.

The additive supersession leaves the original weekdays, holidays, source
master SHA, and previously observed H021 captures unchanged. It removes
November 8 from unresolved **only in v2**, and adds the single special
session: Sunday 2026-11-08, normal market open **14:20 IST**
(`08:50Z`), conservative final CAS matching close **15:35 IST**
(`10:05Z`). Exchange trade modifications can continue until **16:15 IST**.
Neither the generic closing-auction clock nor the circular supplies a
per-security executable closing price or any future outcome.

## Prospective-only collector routing

- Before 2026-11-02, the authoritative collector and every downstream
  calendar consumer still use the exact original v1.
- From 2026-11-02 onward, the collector uses the SHA-pinned reviewed v2.
  Its immutable identity and original-circular evidence must validate
  before the gate can return CAPTURE.
- November 6 is now `NOT_FINAL_SESSION` and **must not** create a capture.
- November 8 is `CAPTURE` only **after 18:15 IST** under the existing
  post-close rule, and only if no identical manifest exists already on main.
- Sunday scheduler attempts are date-gated like weekday attempts and do
  not create observations on ordinary non-session Sundays. An earlier
  Sunday attempt is deliberately protected by the 18:15 guard so that
  ordinary GitHub scheduling delays have a safer same-day opportunity.
- November 9 is not the final session in its own calendar week.
- The AE001 expectations panel and H021 future-intent generator receive
  the **same** versioned effective calendar as the capture gate. The
  source-pinned future-intent path switches to the v2 Git blob on/after
  November 2 without rewriting any earlier intent.

## Scientific invariants

The fixed 100-member U001 set, batch partition, provider version,
same-period EPS semantics, analysts >=5 at both observations, closest-to-30
prior inside 28–35 days, EPS-only tie-inclusive top decile, explicit
NO_SIGNAL statuses, no price/returns input and immutable machine sealing
are all unchanged. The v2 has no effect on the October 30 capture and
must never be applied retroactively to prior sealed H021 observations.

This is a **reviewable source/calendar operational change**. It must pass
H021 calendar, source, comparison, AE001 and future-intent regression CI
before merge. The existing unresolved-calendar blocker remains active on
main until an approved merge. No November 8 capture can be fabricated now.
