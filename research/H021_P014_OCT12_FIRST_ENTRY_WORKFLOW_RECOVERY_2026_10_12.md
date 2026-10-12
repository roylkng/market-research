# H021-P014: First Oct 12 Official Market Capture Operational Recovery

Dated 2026-10-12, prior to the **15:30 IST completed cash-market session**.
**Operations-only**, not a new investment hypothesis, signal, or outcome.

## The apparent failed pre-entry job was only an expired no-op

Original 9 October consensus revision cohort (10 stocks) was frozen
before 12 October 09:15 IST first intended session open.

The existing official **9 October** pre-entry source-format rehearsal
was completed successfully on **11 October 15:38:38 UTC**.
Its immutable source and parser receipt is:

    research/prospective/h021/preentry-rehearsal/original-sources-format-ready-v1.json

The original stock UDiFF ZIP SHA:
8adbb3410c8cf4372290484a9b1798490ef279d30fc2439c93f082cc20ed198c

The original official **Nifty 500 price-index** CSV SHA:
7b2b7c2ea5385e66fe87376b61ccb3492f94f300e4daaca9a972dd96d3211b01

All ten originally selected EQ/ISIN stock rows parsed. Neither future
open prices nor capital trades were observed.

The 12 October pre-entry workflow run 38216820417 happened at
**07:16:57 UTC**, *after* the frozen 03:45 UTC entry open. The original
calendar gate correctly returned SKIP. No market data were fetched.
It then failed on an unconditional upload-artifact action because the
PREFLIGHT_OUT variable was not defined on a skipped source step.

This is **not** evidence that the 11 October real-source rehearsal
failed. No retrospective rerun after open is scientifically permitted.

**Correction:** remove the obsolete one-time scheduled rehearsal cron
and permit the artifact upload only when the original gate is CAPTURE.
Manual dispatch after the entry still returns a no-op; it does not
synthesize evidence or relabel observation timestamps.

## Protect the post-close October 12 entry receipt

Existing original first-entry official source workflow:

    .github/workflows/h021-first-entry-observation.yml

It is already scheduled for 18:15, 18:45 and 19:15 IST on trading
weekdays. It remains gated against any source capture before
**12 October 15:30 IST (10:00 UTC)**.

Multiple independent research-source workflows currently write to
the repository's main branch. A single "git fetch/rebase/push" after
source acquisition risks losing a valid original exchange receipt
due to a concurrent unrelated commit.

**Correction:** retry safe fetch/rebase/push up to five times with
bounded short delays. On every retry:

- check that the original intent, comparison, universe, official
  session calendar, source parser, and capture workflow are unchanged;
- if first-entry source result is already sealed, **refuse overwrite**;
- preserve the exact same captured source bytes and original UTC
  timestamp from the earlier acquisition. Never fetch another date,
  replace a missing stock price or revise the source packet;
- if Git publication remains impossible, retain the run's original
  bytes and attempt receipts as GitHub Actions artifact, not a false
  success.

The code never changes the frozen original top-ten, H021 EPS score,
benchmark family or 20/60-session evaluation rules. It does not
assume an NSE UDiFF file is available immediately after market
close, or that the index is Nifty 500 TRI.

## Acceptance tests

    pytest -q tests/test_h021_first_entry_workflow_resilience.py
    pytest -q tests/test_h021_entry_observation.py tests/test_h021_first_entry_intent.py

These are **workflow/invariant tests**, not a substitute for the
real October 12 after-close official price files, corporate actions,
dividends, 2027 official sessions and matured forward outcomes.

The source-only P004 capture must remain research-only and
non-investable. Live capital and portfolio eligibility are disabled.
