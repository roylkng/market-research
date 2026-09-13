# H022 — Management information delta

## Status

`FROZEN_HISTORICAL_DEVELOPMENT`

Live capital: **DISABLED**

## Economic mechanism

Quarterly management calls contain information beyond reported accounting numbers. A management team that becomes more concrete about future operating commitments can reveal a change in confidence, visibility, execution plans, capacity, demand or capital allocation before that change is fully represented in trailing financial statements.

H022 tests whether the **change** in concrete forward-looking management information from one official call to the next predicts future benchmark-relative returns.

This first version deliberately avoids generic sentiment and LLM judgment. It uses the already-frozen H003-E002 deterministic future-commitment extraction as a source primitive, then measures how the density and specificity of those commitments change versus the company's latest strictly earlier call.

## Historical data asset

H022-R001 consumes the already-completed H003-E002 corpus:

- 100-company frozen U001 FY27-Q2 cohort;
- transcript window beginning 1-Sep-2024;
- exact source cutoff `2026-09-06T12:21:06.431463Z`;
- 794 official NSE management-call transcript sources;
- 794/794 sources `TEXT_READY`;
- 2,692 deterministic H003-E002 future-commitment candidates;
- candidate report SHA-256 `cb48b1e18c76a3ea2d06b13383955c0f0c6efa6d3d65bd132ac3d5e59217ffea`;
- evidence commit `2682d91a2be0dc3b69876ef397791515ff9146f2`.

The exact H022 feature rule is frozen in `registry/h022_signal_rule.yaml` **before any H022 return panel is joined**.

## Universe and bias label

The historical replay uses the companies in the Sep-2026 frozen U001 cohort and looks backward through their available transcripts.

Therefore this is explicitly a **current-survivor-panel historical development experiment**. It is useful for feature discovery and falsification but is not called unbiased historical validation.

Promotion requires either:

1. reconstruction of historical point-in-time universe membership, or
2. successful prospective confirmation on later frozen cohorts.

This bias label may not be removed because historical results look attractive.

## Signal

For each official transcript event `t`:

```text
forward_commitment_density_t
  = H003-E002 candidate_count_t / text_char_count_t * 10,000
```

The primary H022 signal is:

```text
forward_commitment_density_delta_t
  = forward_commitment_density_t
    - forward_commitment_density_previous_call
```

`previous_call` means the latest transcript for the same symbol with a **strictly earlier** NSE exchange publication timestamp.

Calls with no prior transcript remain explicit `NO_SIGNAL_NO_PRIOR_TRANSCRIPT` observations.

Calls sharing the same publication timestamp cannot use one another as prior information.

Secondary preregistered features are:

- deadline-candidate density delta;
- operating-domain breadth density delta;
- explicit-deadline share delta;
- current forward-commitment density level.

No composite is optimized in H022-v1.

## Forbidden signal inputs

The H022 feature builder may not consume:

- stock prices or future returns;
- benchmark returns;
- valuation or broker targets;
- H013 momentum;
- H020 timing;
- H021 analyst revisions;
- H019 quality/accounting state;
- post-publication news;
- any later management call.

Those variables can be evaluated downstream only after the H022 feature panel is frozen.

## Chronological historical split

The split is fixed before opening H022 returns:

### Design period

`2024-09-01` through `2025-09-30`

Used for diagnostics, source validation and understanding feature distributions. It cannot be used to modify the already-frozen feature formulas after challenge returns are opened.

### Challenge period

`2025-10-01` through `2026-09-06`

Primary historical outcome evaluation occurs here.

Random train/test splits are prohibited.

## Decision rule

- information timestamp: exact NSE `exchange_published_at_utc`;
- entry: next completed NSE session open after publication;
- primary exit: 60th holding-session close;
- secondary exits: 20th and 120th holding-session close;
- primary benchmark: NIFTY 500 price index over identical executable interval;
- primary outcome: stock return minus benchmark return;
- 50 bps round-trip research friction reported as a secondary cost-adjusted result;
- corporate-action adjustment is required.

Using the next session open for every event avoids pretending that we know whether an intraday publication could have been processed and traded before the same day's close.

## Primary historical test

Challenge-period observations with a valid prior transcript are ranked by the frozen primary signal.

Report at minimum:

- Spearman signal versus 60-session excess return;
- top-quintile mean and median 60-session excess;
- bottom-quintile mean 60-session excess;
- top-minus-bottom quintile mean spread;
- top-quintile benchmark beat rate;
- company-cluster bootstrap 95% confidence interval for the top-minus-bottom spread;
- sample counts, overlap diagnostics and leave-one-company-out sensitivity.

Frozen interpretation:

### STRONG

- top-minus-bottom mean excess >= 4 pp;
- company-cluster bootstrap 95% CI lower bound > 0;
- top-quintile beat rate >= 55%.

### PROMISING

- top-minus-bottom mean excess >= 2 pp;
- top-quintile median excess > 0;
- top-quintile beat rate >= 55%.

### REJECTED

If either:

- top-minus-bottom mean excess <= 0; or
- top-quintile mean excess <= 0.

Otherwise the result is `INCONCLUSIVE`.

These thresholds are frozen before H022 challenge returns are opened.

## Baselines and challengers

H022-v1 must be compared with:

- current forward-commitment density level without delta;
- raw candidate count;
- transcript text length;
- H013/price momentum as a separately computed downstream baseline, never as an H022 feature.

Later work may challenge H022-v1 with:

- lexical/semantic novelty versus the prior call;
- management-answer versus analyst-question responsiveness;
- Q&A evasion/semantic similarity;
- tone dispersion;
- LLM structured extraction.

Those are separate versions and may not rewrite H022-R001.

## Known failure modes

- current-2026 cohort survivorship bias;
- transcripts may not always correspond exactly to earnings-result dates;
- H003-E002 candidates are deterministic candidates, not perfect semantic management commitments;
- commitment density may rise during distress or uncertainty rather than confidence;
- transcript length and formatting can change across vendors/quarters;
- repeated company observations create dependence;
- 60-session windows can overlap between adjacent calls;
- corporate actions can corrupt raw-price returns if not handled correctly.

The evaluator must disclose these rather than tuning them away.

## Freeze record

- feature rule: `registry/h022_signal_rule.yaml`
- source report commit: `2682d91a2be0dc3b69876ef397791515ff9146f2`
- source report SHA-256: `cb48b1e18c76a3ea2d06b13383955c0f0c6efa6d3d65bd132ac3d5e59217ffea`
- source extraction rule: `H003-E002`
- feature outcomes: **UNOPENED at rule freeze**

## Result

Not yet evaluated. The next gate is to build, hash and anchor the H022 feature panel with no price or return inputs. Only after that commit may the historical outcome evaluator be implemented/run.
