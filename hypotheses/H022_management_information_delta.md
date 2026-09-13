# H022 — Management information delta

## Status

`PROMISING_HISTORICAL_DEVELOPMENT`

Live capital: **DISABLED**

This status is historical-development evidence only. It is **not** historical validation because the replay looks backward through companies selected into the Sep-2026 U001 survivor panel.

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

The exact H022 feature rule was frozen in `registry/h022_signal_rule.yaml` **before any H022 return panel was joined**.

The outcome-free H022 panel was then frozen independently:

- transcript records: **794**;
- valid delta signals: **697**;
- design-period signals: **299**;
- challenge-period signals: **398**;
- no-prior first calls: **97**;
- ambiguous-prior calls: **0**;
- panel SHA-256: `dd992523238aebce5e9f6ee8535951fd869bf9d8615705d4fb5f420e8f85bee3`;
- outcome data attached at freeze: **false**.

Only after that panel was anchored was `H022-X001` frozen and the historical price outcome reconstruction opened.

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

The split was fixed before opening H022 returns:

### Design period

`2024-09-01` through `2025-09-30`

Used for diagnostics, source validation and understanding feature distributions. It cannot be used to modify the already-frozen feature formulas after challenge returns are opened.

### Challenge period

`2025-10-01` through `2026-09-06`

Primary historical outcome evaluation occurs here.

Random train/test splits are prohibited.

## Execution rule

The separately frozen execution contract is `H022-X001` in `registry/h022_execution_rule.yaml`.

- information timestamp: exact NSE `exchange_published_at_utc`;
- entry: first NSE session open strictly after the publication timestamp; same-day entry is allowed only when publication is strictly before that session's actual open;
- the special 21-Oct-2025 Muhurat session uses its official 13:45–14:45 IST session time;
- entry session counts as holding session 1;
- primary exit: 60th holding-session close;
- secondary exits: 20th and 120th holding-session close;
- primary benchmark: official NIFTY 500 price index over the identical executable interval;
- primary outcome: stock return minus benchmark return;
- 50 bps round-trip research friction is reported as a secondary cost-adjusted result;
- any share-changing corporate action strictly after entry and on/before exit blocks that horizon in v1 rather than applying an inferred adjustment factor;
- missing stock/benchmark bars are never imputed;
- market-data cutoff is the completed NSE session of `2026-09-11`.

## Frozen primary historical test

Challenge-period observations with a valid prior transcript are ranked by the frozen primary signal.

The preregistered primary horizon is **60 sessions**. Reported metrics include:

- Spearman signal versus 60-session excess return;
- top-quintile mean and median 60-session excess;
- bottom-quintile mean 60-session excess;
- top-minus-bottom quintile mean spread;
- top-quintile benchmark beat rate;
- company-cluster bootstrap 95% confidence interval for the top-minus-bottom spread;
- coverage/status counts.

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

These thresholds were frozen before H022 challenge returns were opened. A regression test explicitly locks the 55% PROMISING beat-rate boundary.

## Historical challenge result

Authoritative outcome report SHA-256:

`4298bfce4227e4c27d1edcf19b0651def6e8980356a6a9de2493d09a81bee6c5`

Authoritative summary SHA-256:

`201644fdd6c5eca514db1266f9c03bc07361bd11c302820858e7d7d9dd6bbcb4`

### Primary: 60 sessions

Coverage:

- challenge signals: **398**;
- mature signals by the Sep-11 cutoff: **299**;
- complete outcomes: **295**;
- complete share of mature signals: **98.66%**;
- corporate-action blocked: **3**;
- missing entry stock bar: **1**;
- not yet mature: **99**.

Result:

- Spearman signal vs excess return: **0.1381**;
- Spearman p-value: **0.0176**;
- top-quintile mean excess: **+5.56 pp**;
- bottom-quintile mean excess: **+2.37 pp**;
- top-minus-bottom mean spread: **+3.19 pp**;
- top-quintile median excess: **+5.75 pp**;
- top-quintile benchmark beat rate: **55.93%**;
- top/bottom quintile counts: **59 / 59**;
- company-cluster bootstrap 95% CI for spread: **[-2.45 pp, +9.13 pp]**.

Frozen classification: **PROMISING**.

The result clears every frozen PROMISING gate. It does **not** clear STRONG because the spread is below 4 pp and the symbol-cluster bootstrap lower bound remains below zero.

### Secondary: 20 sessions

- mature: **390**;
- complete: **388**;
- Spearman: **0.0838**, p = **0.0994**;
- top-quintile mean excess: **+1.45 pp**;
- top-minus-bottom spread: **+0.52 pp**;
- top-quintile median excess: **+0.67 pp**;
- top-quintile beat rate: **58.44%**;
- bootstrap spread CI: **[-1.30 pp, +2.42 pp]**.

This is weak secondary evidence. H022-v1 is not an immediate-reaction signal on this replay.

### Secondary: 120 sessions

- mature: **196**;
- complete: **191**;
- Spearman: **0.1587**, p = **0.0283**;
- top-quintile mean excess: **+12.79 pp**;
- top-minus-bottom spread: **+7.51 pp**;
- top-quintile median excess: **+8.70 pp**;
- top-quintile beat rate: **65.79%**;
- bootstrap spread CI: **[-0.95 pp, +16.42 pp]**.

This is substantially stronger secondary evidence, but it cannot be used to redefine the preregistered 60-session primary horizon. The 120-session result is a hypothesis generator for a separately frozen challenger only.

## Source and exclusion audit

The official-source replay retained/verified:

- challenge symbols: **96**;
- corporate-action audits: **96/96 READY**;
- official NIFTY 500 session files: **235/235**;
- official UDiFF session files: **201**;
- requested stock bars: **1,236**;
- observed stock bars: **1,235**;
- unresolved corporate-action audits: **0**.

The one missing stock bar is the `TMCV` entry session on **2025-11-19**. That single source observation remains missing at all mature horizons rather than being substituted.

Share-action blocks in the current outcome report are limited to explicit cases involving:

- `ADANIENT`: rights issue;
- `HINDUNILVR`: demerger;
- `VEDL`: demerger.

The compact exclusion ledger is retained in `research/historical/h022/management-information-delta-v1/challenge-2026-09-11/exclusions-summary.json`.

## Interpretation

The historical challenge provides evidence that **an increase in concrete forward-looking management commitments versus the company's prior call contains medium-term ranking information** in this survivor panel.

The strongest defensible statements are:

1. the 60-session rank relationship is positive and statistically non-zero under a conventional Spearman test;
2. the frozen top quintile outperformed the frozen bottom quintile by about 3.2 percentage points on average;
3. the top quintile cleared the preregistered 55% benchmark-beat gate;
4. the bootstrap uncertainty around the top-minus-bottom spread is still wide and crosses zero;
5. the 20-session result is weak, while the 120-session secondary result is materially stronger;
6. because the historical universe is a current-2026 survivor panel, this remains **promising development evidence rather than validated alpha**.

The result must not be combined with H013/H020/H021 and then described as independently validated without a new frozen ensemble experiment.

## Baselines and challengers still required

H022-v1 should next be compared with:

- current forward-commitment density level without delta;
- raw candidate count;
- transcript text length;
- sector/size/quality/value/momentum factor exposure;
- H013 price momentum as a separately computed downstream baseline, never as an H022 feature.

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
- factor exposure may explain part of the observed excess return;
- the NIFTY 500 benchmark is a price index rather than total return.

The evaluator discloses these rather than tuning them away.

## Freeze and evidence record

- feature rule: `registry/h022_signal_rule.yaml` (`H022-R001`);
- execution rule: `registry/h022_execution_rule.yaml` (`H022-X001`);
- source report commit: `2682d91a2be0dc3b69876ef397791515ff9146f2`;
- source report SHA-256: `cb48b1e18c76a3ea2d06b13383955c0f0c6efa6d3d65bd132ac3d5e59217ffea`;
- source extraction rule: `H003-E002`;
- feature panel SHA-256: `dd992523238aebce5e9f6ee8535951fd869bf9d8615705d4fb5f420e8f85bee3`;
- feature outcomes at feature freeze: **UNOPENED**;
- historical outcome report SHA-256: `4298bfce4227e4c27d1edcf19b0651def6e8980356a6a9de2493d09a81bee6c5`;
- historical outcome summary SHA-256: `201644fdd6c5eca514db1266f9c03bc07361bd11c302820858e7d7d9dd6bbcb4`;
- live capital: **DISABLED**.

## Next gate

H022-R001 remains frozen. The result does not justify modifying the rule.

Next work, in order:

1. run factor-neutral attribution to test independence from sector, size, value, quality and momentum;
2. reconstruct historical point-in-time universe membership if feasible and rerun the unchanged rule on a less survivor-biased panel;
3. continue/provision prospective transcript capture for an independent confirmation cohort;
4. create any 120-session or richer semantic/Q&A model only as a separately frozen challenger;
5. evaluate H022 in PF001 only after an independent promotion gate is satisfied.
