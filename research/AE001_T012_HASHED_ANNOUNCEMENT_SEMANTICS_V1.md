# AE001 T012 Hashed Announcement Semantics v1

Status: FROZEN BEFORE RETURN OUTCOME MATERIALIZATION
Frozen: 2026-10-02
Live capital: DISABLED

## Objective

Test whether deterministic semantic representation of official NSE announcement
text adds short-horizon cross-sectional information beyond AE001 CORE27.

T012 is a new trial. It does not retune T007's failed hand-built event taxonomy.

## Parent evidence

T007 used counts and frozen keyword topics from official NSE announcement
metadata and failed its 1-session primary endpoint. Its 5-session secondary
endpoint was materially worse than CORE27.

T012 changes the representation only.

## Source

Reuse the exact official NSE corporate-announcement source contract promoted by
AE001-D003 and used by T007:

- endpoint: /api/corporate-announcements;
- one whole-market query per calendar date;
- source window: 2025-09-01 through 2026-09-25;
- exact official exchange dissemination timestamp;
- exact fields retained by the canonical announcement parser:
  symbol, seq_id, desc, attchmntText, attchmntFile.

D003 report SHA-256:

7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f

T007 announcement source panel expected SHA-256:

fc3be48ce09905b8d2ebef1ad0e75a7ed22815202abbd7d7b328fe6dfcd3957d

No attachment body is fetched or parsed in T012-v1.

## Decision clock and eligible text

Decision cutoff:

18:30:00 Asia/Kolkata.

T012 uses only announcements satisfying ALL:

1. official dissemination maps to a completed NSE decision session under the
   existing T007 cutoff mapping;
2. dissemination local calendar date equals that decision session date;
3. dissemination local time is strictly after 15:30:00;
4. dissemination local time is no later than 18:30:00;
5. exact same-session NSE EQ symbol + ISIN identity exists.

Therefore T012-v1 studies same-trading-day post-close text known before the
18:30 decision cutoff.

Pre-close, weekend and holiday announcements do not enter the T012 semantic
vector. They are not reassigned or backfilled.

## Text input

For one eligible announcement:

    text = desc + " " + attchmntText

Normalization:

1. Unicode NFKC;
2. lowercase;
3. extract contiguous ASCII alphanumeric tokens with regex [a-z0-9]+;
4. retain token order;
5. form:
   - every unigram as "u:<token>";
   - every adjacent bigram as "b:<token1>_<token2>".

No stop-word list.
No stemming.
No lemmatization.
No fitted vocabulary.
No sentiment lexicon.
No LLM output.
No manually assigned event direction.

An announcement yielding zero tokens contributes the zero vector and is counted.

## Frozen signed feature hashing

Dimensions:

64 exactly.

For one normalized n-gram string s:

    h = SHA256(UTF8(s))
    bucket = int.from_bytes(h[0:8], "big") mod 64
    sign = +1 if (h[8] & 1) == 0 else -1

Within one announcement:

- each distinct unigram/bigram contributes once;
- repeated identical n-grams within the same announcement do not receive
  additional count weight;
- the resulting 64-vector is L2-normalized when non-zero.

For one symbol + ISIN + decision session:

- sum the L2-normalized vectors of all eligible announcements in that interval;
- if no eligible announcement exists, all 64 semantic values are zero.

Feature names:

annsem_hash_00 through annsem_hash_63.

No dimension selection, sign flipping or post-outcome rotation is permitted.

## Base and challenger

Base:

CORE27, the frozen 18 price/liquidity + nine delivery/VWAP features.

Challenger:

CORE91 = CORE27 + 64 T012 hashed semantic features.

Base and challenger use exactly the same action-safe, delivery-complete stock
rows. The semantic layer may not filter rows based on whether text exists.

Both feature sets receive the existing within-session tie-aware percentile
transform before model fitting.

## Model

Both models:

- ridge regression;
- l2 = 1.0;
- chronological purged training;
- no hyperparameter search.

## Primary endpoint

Horizon:

1 completed NSE session.

Entry:

next completed NSE session open.

Exit:

same entry session close.

Target:

stock return minus Nifty 500 return over the identical interval.

Frozen validation folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-24

Paired Newey-West lag:

5.

Primary support requires BOTH:

1. CORE91 minus CORE27 mean daily rank IC > 0 with two-sided p < 0.05;
2. CORE91 minus CORE27 mean daily top-minus-bottom spread > 0 with two-sided
   p < 0.05.

Intersection rule.

## Secondary endpoint

Horizon:

5 completed NSE sessions.

Frozen validation folds:

1. 2026-04-01 through 2026-06-30
2. 2026-07-01 through 2026-09-18

Paired Newey-West lag:

4.

Secondary evidence cannot rescue a failed 1-session primary.

## Excluded horizons

20 and 60 sessions are not tested.

## Trial accounting

T012 must be appended to research/ae001/trial-ledger.json before the first
return outcome is materialized.

The registration must freeze:

- source hashes;
- 64 dimensions;
- tokenization;
- hash/sign rule;
- distinct-ngram rule;
- event L2 normalization;
- same-day 15:30-18:30 window;
- folds;
- l2;
- inference lags;
- success rule.

## Interpretation

If supported, T012 establishes historical-development incremental information
for deterministic post-close announcement text representation.

The next gates would be:

1. AB001 orthogonality against CORE27 and the T005 futures-delta alpha;
2. a separately frozen prospective text confirmation.

If unsupported:

- preserve the failure;
- do not alter hash dimensions, tokenization or text window under T012;
- any embedding/LLM/attachment-body trial requires a new trial ID.

T012 does not establish causal event interpretation, trading profitability,
prospective alpha or live-capital readiness.
