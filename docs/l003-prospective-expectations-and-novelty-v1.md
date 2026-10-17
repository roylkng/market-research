# L003 P001: Earnings expectations and quantified disclosure changes

Date 2026-10-17. Implementation is a **source-admission and diagnostic layer**, not new alpha, not an H002 rule change, and not an approved future-return experiment.

## What we found

The repository **already captures point-in-time analyst consensus**, in its independently frozen H021 pipeline and AE001-H021 source-only feature adapter. The sealed **2026-10-16** panel covers 100 U001 Nifty200 nonfinancial names. The frozen H021 source eligibility is **92 / 100**, with seven coverage failures and one unavailable EPS change.

The most important causal fact: the Oct16 capture completed **2026-10-16T17:28:44.369017Z** (22:58 IST), **after** AE001's same-day 18:30 IST EOD cutoff (13:00 UTC). It cannot be used as an October 16 EOD model input. Its earliest recorded execution session is **2026-10-19** at 03:45 UTC. This is a source timestamp, **not** a prediction or actual entry. We cannot promote future October 19 performance as already observed.

The H021 U001 universe **does not contain HG009's separate outside-U001 100-company discovery cohort**. No artificial cross-universe join is permitted.

## Implemented in src/marketlab/l003_novelty.py

- `assess_sealed_h021_feature`: recomputes panel SHA, enforces immutable H021 identity, one row per symbol+ISIN, exact source time, no outcomes and no live capital, and returns NO_SIGNAL for missing/insufficient coverage. Does not reimplement or alter H021's frozen percentage-revision formula.
- `assess_guidance_revision`: compares two source-backed, explicit numeric claims for the **same issuer, ISIN, accounting scope, metric, forecast period and unit**. Binds literal values to exact text excerpts in original document bytes and checks source SHA, first-seen and published timestamps. If either prior forecast or current comparable claim is missing, fail closed.
- All outputs are diagnostic only. A caller-provided `INDEPENDENTLY_REVIEWED` field is **not cryptographically proven reviewer independence**. Genuine source issuer identity, financial semantic correctness and completeness of earlier guidance cannot be certified solely from hashes or string equality.
- Neither routine infers headline-news novelty from sentiment or creates returns, forecasts, H002 variants, HG009 rankings or trade permissions.

## Source custody and next scientific gate

The October 16 H021 adapter provides hash-bound **derived consensus**, not independently reread raw original provider bytes in L003 itself. Full original source custody remains under H021. Do not use a generic news headline hash as sufficient proof of a quantified business claim.

The companion source intake must supply:
1. Earlier public dated forecast anchored in original issuer/NSE bytes.
2. New original issuer/NSE filing with exact quantified change.
3. Date, time, symbol, ISIN, scope and units. Amendments must version earlier records instead of overwriting them.
4. Independent comparison to the fixed H002 EPS-sign and simple price-only/event controls.
5. A **new future experiment freeze** (universe, rule, trial limits, costs and 5/20/60 trading-session outcomes) before any prediction. L004 restricts retrospective LLM score admission.
6. If consensus licensing or prior-guidance proof is missing, preserve MISSING instead of synthetic zero.

## Regression cases

- Tampered original bytes, impossible publication time, mismatched fiscal period/issuer/basis, unreviewed claim and spoofed NSE domain rejected.
- Historical 2026-10-16 AE001 cutoff rejects actual October 16 H021 feature. Synthetic planned next-session cutoff permits *source admission only* from its prior capture, without claiming any forward forecast or trade.
- Hash-mutated actual H021 panel rejected; the separate HG009 symbol ACE cannot enter the U001 panel by analogy.

This PR implements the admissibility layer of issue #470. **Its empirical alpha requirement cannot be completed until prospective predictions are preregistered and future outcomes mature.**
