# AE001 T004 Outcome Cohort Amendment P2

Status: FROZEN BEFORE FIRST ELIGIBLE T004 DECISION SESSION
Frozen: 2026-09-29
Live capital: DISABLED

## Purpose

Remove ambiguity from T004's minimum-evidence and stopping rule before the first
prospective decision session.

## Primary cohort rule

The confirmatory 5-session result uses the smallest canonical prefix of T004
decision sessions that satisfies all of the following:

1. prefix length is at least 60 decision sessions;
2. every decision in the prefix has a matured 5-session outcome artifact;
3. at least 50 sessions in the prefix have a valid paired rank-IC observation.

The prefix is ordered by canonical T004 decision-ledger sequence.

As soon as the smallest prefix satisfies all three conditions, that cohort is
frozen. Later T004 decisions cannot alter the primary result.

## Primary result

The primary success rule remains unchanged from T004 v1:

- paired augmented-minus-base 5-session rank-IC difference > 0 with two-sided
  Newey-West p < 0.05, lag 4;
- paired augmented-minus-base 5-session top-minus-bottom spread difference > 0
  with two-sided Newey-West p < 0.05, lag 4.

Both conditions are required.

## Secondary 20-session result

The secondary 20-session result uses the exact same frozen primary cohort.

It may be opened only after every decision in that frozen cohort has a matured
20-session outcome artifact.

It does not rescue a failed primary endpoint.

## Exclusions

A decision remains part of the canonical prefix even if its matured outcome has
too few valid stock rows to calculate rank IC. Such a session counts toward the
prefix length but not toward the minimum 50 valid paired-IC sessions.

No decision can be replaced by a later decision merely because its realized
outcome is inconvenient or missing after fail-closed processing.

## No optional stopping

The result opener must evaluate prefixes in canonical order and stop at the
first prefix that satisfies the frozen gates. It may not choose a later prefix
because its statistics are more favorable.

## Live capital

Disabled.
