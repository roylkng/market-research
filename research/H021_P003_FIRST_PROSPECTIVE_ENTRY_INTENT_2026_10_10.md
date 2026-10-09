# H021-P003 First Prospective Research Entry Intent: 9 October 2026

**Status: FROZEN BEFORE NEXT PLANNED MARKET OPEN (12 October 2026).**
Research-only H021 stock-level observational cohort. Not a position order,
asset allocation, H020 timing decision, PF001 eligibility, or validated alpha.

## Why the intent must exist now

H021's first valid same-period 28-day EPS-revision comparison was sealed
after the 9 October NSE close. Its existing, preregistered primary cohort
consists of 10 of 97 valid analyst-covered names.

The source H021 protocol calls for the **next completed session's executable
open** as the H021-alone entry proxy. The pinned NSE calendar expects the
next session to be Monday **12 October 2026 at 09:15 IST**.

A permanent next-open intention must be recorded **before that open** so
subsequent performance is not evaluated as if Friday's prices or Monday's
realized price move were known. We record the identity and intention now,
not fill prices or future returns.

## Strict source identity

- Comparison JSON: research/prospective/h021/comparisons/2026-10-09-primary-revision-v1.json
- Exact Git blob: 99c94c9d98284076bf1a7c34ee43e602b741b15b
- NSE calendar: research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json
- Exact Git blob: 9ac614820a67b0f7b20d8170d15b84df3c996b62
- H021 protocol: research/H021_PROSPECTIVE_PROTOCOL_V1.md
- Committed machine-readable intent:
  research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json

Reproduce on main with:

    python -m marketlab.h021_first_entry_intent

The script explicitly validates both immutable Git blob hashes and the
unchanged top-decile eligible membership. It fails on any reselected name,
modified source, changed calendar or return-opened input.

## Frozen selected observation cohort

These are observational targets, **not recommendations**:

1. VEDL
2. ETERNAL
3. DMART
4. IDEA
5. ADANIENSOL
6. JSWSTEEL
7. COALINDIA
8. INFY
9. GAIL
10. POWERGRID

ADANIENT, BOSCHLTD and TRENT remain coverage-ineligible even though the
comparison stores some numerical raw EPS changes. They cannot be
post-selected by sorting those arithmetic values.

## Measurement boundary

- Selection comes only from the original H021 primary 28-day EPS revision.
- The intent carries 10 original selected identities, 97 eligible denominator
  and three explicit ineligible identities.
- Next-open prices, corporate actions, 20-session and 60-session future
  returns, benchmark observations and transaction costs are **unobserved**.
- Entry failures must be explicit, not assigned a hindsight executable open.
- The frozen H021 outcomes remain primary 60 and secondary 20 **completed
  NSE sessions** against the Nifty 500 benchmark family.
- Calendar ends on 31 December 2026, only 55 future completed sessions
  from the planned 12 October entry. The 60th exit date cannot be
  established without a separately verified 2027 NSE calendar. No
  invented date is permitted.
- The precise official Nifty 500 series, benchmark open-to-close basis,
  constituent corporate-action treatment, source timestamps and
  transaction cost variants require independently versioned,
  **pre-outcome** pricing/evaluation contracts. Until then, this record
  may not claim benchmark excess returns.

## Capital firewall and semantics

The project has **not** established a multiplicity-robust alpha result.
HG001/HG002 company routing and DR001 Tier-A company research are independent
efforts. This observational H021 cohort is not a PF001 eligible portfolio.
Every record carries null entry price/allocation and retains explicit
portfolio_eligibility_allowed=false and live_capital_allowed=false.

The intent can be considered prospectively frozen only if its exact GitHub
commit is created before the 12 October NSE open. Creation afterward must
be classified as a **retrospective reconstruction**, not prospective
evidence. The Git commit timestamp is the authoritative publication
timestamp, not any date string inside the JSON.

## Next scientific gates

1. Verify official 12 October opening source and executable price or record
   each missing observation without substitution.
2. Freeze and source-audit consistent stock, index and corporate-action
   pricing methodologies before the first outcome is opened.
3. Continue the weekly H021 consensus captures without replacing
   the frozen U001 universe.
4. Accumulate at least four monthly-equivalent decision cohorts and mature
   the 60-session outcomes under H021's prior protocol.
5. Report head-to-head against H013 momentum, implementation costs,
   breadth, and concentration without altering frozen primary selection.

No portfolio or live-capital authority is granted by this artifact.
