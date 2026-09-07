# Combined Ranking V1

Status: FROZEN DESIGN BEFORE CURRENT-MARKET RANKING

## Objective

Rank the frozen 100-company FY27-Q2 U001 universe for research across short, medium and long horizons without using future outcomes, post-result H002 surprise information, or company identity during H003 semantic review.

Live capital remains disabled.

## Frozen inputs

- Universe: `research/prospective/universes/FY27-Q2-2026-09-06.json`
- H003 candidate provenance: complete H003-E002 report anchored on `run/h003-e002-full-extraction-20260907`
- H003 semantic review: complete H003-V001 r4 branch `run/h003-v001-blind-review-r4-20260907`
- Ranking as-of date: 2026-09-07

H002 realised earnings surprise is excluded from the pre-result current ranking. It may only update a company after the corresponding result becomes public.

## H003 forward-evidence pillar

H003 is unblinded only by exact `candidate_id` joins against the frozen E002 candidate report. Text inference of company identity is prohibited.

For each company calculate:

1. `accepted_source_rate`: distinct transcript sources containing at least one accepted commitment divided by candidate-bearing transcript sources.
2. `open_source_rate`: distinct transcript sources containing at least one accepted commitment not clearly expired as of 2026-09-07 divided by candidate-bearing transcript sources.
3. `open_claim_rate`: non-expired accepted commitments divided by semantic-review candidates. Values are capped at 1.
4. `open_claim_type_diversity`: number of distinct claim types among non-expired commitments, capped at eight and divided by eight.
5. `pillar_diversity`: fraction of three commitment families represented among non-expired claims: financial/growth, execution/capacity, capital-discipline/risk.

Each component is converted to a cross-sectional percentile among the 100 frozen companies. `h003_forward_evidence_score` is their unweighted mean. Missing/zero-source companies receive zero evidence, not an imputed score.

This score measures evidence strength, not expected return.

## Anti-verbosity controls

- At most the presence of an accepted/open commitment per source matters to source-rate features.
- Claim-type diversity is capped.
- Raw accepted-claim count is reported but not directly used in the score.
- No claim-type weights are tuned using stock returns.

## Expiry classification

A claim is `clearly_expired` only when its normalized deadline/horizon unambiguously precedes 2026-09-07. Ambiguous relative horizons are retained as `open_or_unresolved` rather than guessed expired. This intentionally favors false retention over false deletion at the screening stage. Current deep research must independently verify whether shortlisted commitments remain live.

## Final investment pillars

After H003 screening, shortlisted companies are evaluated using independent current information:

- management evidence and historical credibility
- business/fundamental quality and earnings trajectory
- valuation relative to growth/quality and own history where available
- identifiable catalysts and execution timing
- balance-sheet/capital-allocation risk
- market/price confirmation

No numeric pillar weight may be tuned against the same historical outcomes used for evaluation. Horizon rankings use fixed qualitative emphasis rather than outcome-optimized weights.

## Horizon emphasis

- Short, 1-3 months: catalyst timing and market confirmation dominate. Valuation and H003 evidence are required sanity checks.
- Medium, 3-12 months: execution, earnings trajectory, valuation and management evidence have roughly equal importance.
- Long, 1-3 years: business quality, capital allocation, management credibility, structural runway and valuation dominate. Short-term momentum is a secondary input.

## Validation and actionability

H002 and H003 historical tests remain separate pre-registered signal validations. A combined current ranking is exploratory until a point-in-time multi-pillar historical replay is completed with the same frozen rule and clears a pre-registered actionability gate.

Therefore `live_capital_allowed = false` for Combined Ranking V1 regardless of apparent current attractiveness.
