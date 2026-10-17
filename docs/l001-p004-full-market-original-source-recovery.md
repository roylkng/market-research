# L001 P004: Archive recovery and original XBRL replay for all 100 HG009 identities

**Date:** October 18, 2026. **Classification:** source-only historical accounting audit. This work does not select stocks, alter HG009 H1/H5 outcome arms, create a new prospective trading cohort, or authorize capital.

## Why this work was necessary

Earlier P002 reported ten detailed P014 dossiers and zero completely underwritten owner-cash valuations. That is correct but understates *existing original-source accounting coverage*. The original GitHub Actions evidence archive already includes broad-market financial, issued-share and governance planes. Their signed original source panels can be joined to all 100 frozen HG009 companies **without querying current websites or using future returns**.

Independent local verification recovered and checked:

| Source | Pinned GitHub Actions artifact | Hash of sealed panel |
|---|---:|---|
| SS001 D001 original 2319-company identity census | 11301695772 | `0cfdc865...b3112937` |
| FA001 D002 FY26 annual and FY27 Q1 original financial fact plane | 11306919543 | `cb8a408b...fa9124` |
| SS001 D004 shareholding-derived issued-share counts | 11525307261 | `ab782411...42f780` |
| GF001 D002 source custody for original shareholding XML | 11303742567 | `dd338cd9...6dae11b` |

FA001 original XML shards, also pinned to run 37213394690: `11307293225`, `11307437621`, `11307367737`, `11306939618`, `11306939594`, `11307478103`. These are exact artifact IDs, not latest mutable URLs.

## Source-only findings (not alpha)

- All **100 / 100** HG009 identities join exactly to the 2319-company census and FA001 original-pinned source records using symbol plus ISIN.
- All **100 / 100** have source-ready FY26 annual and Q1 FY27 financial statement extracts.
- All **100 / 100** have independently hash-verified FY26 original annual XML, Q1 FY27 original XML and original shareholding XML, **300 / 300** original issuer files.
- **400 / 400** independently re-read XBRL numeric cells agree in exact selected element, source context and INR unit for: consolidated/standalone FY26 CFO, FY26 PPE purchases, Q1 revenue and Q1 PAT. Individual issuer accounting scope is retained, never homogenized.
- All **100 / 100** have a source-derived issued-share count. **97 / 100** meet SS001's *historical capitalization-source eligibility*, the other three are **BAGFILMS, LLOYDSENT, SPANDANA**. These are **not** current fully diluted shares or automatically valid October 15 market-cap denominators.
- **92 / 100** annual panels supply the conventional current plus noncurrent borrowings fields. Financial institution lending liabilities have different semantics.
- 0 / 100 have a full parent-distributable owner-cash and current fully diluted investment underwriting from this source join.

The earlier P002 count of five company-specific FY26 cash replay dossiers is **not contradictory** to this finding. Those five were separately reviewed dossiers. FA001 has broader XBRL accounting fact coverage, and this audit provides a direct original-file numeric replay across the other members. Do not upgrade generic XBRL CFO-minus-PPE to owner FCF.

## Repository implementation

- `src/marketlab/l001_p004_original_replay.py`: verifies exact immutable hashes for cohort/census/FA/SS/GF and source clock, rejects altered original XML, identity or reporting-scope drift, replays original numeric facts, and emits source-only 100-row evidence results.
- `scripts/materialize_l001_p004_originals.py`: reads ten exact downloaded archive ZIPs, extracts only 300 SHA-addressed selected issuer XML documents, emits a deterministic 100-row JSON evidence artifact and compact source pack. Neither live market search nor a broker is used.
- `.github/workflows/l001-p004-original-xbrl.yml`: independently obtains exact historical artifacts, executes the full verification, and publishes report plus source pack as a workflow artifact. No Git commit or external trading action is made by this workflow.
- `tests/test_l001_p004_original_replay.py`: synthetic invariants and tampering regressions, supplemented by full 300-original replay from the workflow.

**Important distinction:** Direct XML numeric agreement and original SHA authentication establish source identity and arithmetic, **not** the economic definition of distributable owner cash, fully diluted shares, analyst expectations or intrinsic value.

## Next data gates

1. Reconstruct originals for investor-attributable lease payments, interest, tax, minority cash, maintenance vs growth capital, acquisition obligations and restricted cash.
2. Build regulator-specific economic value templates for banks, NBFCs and insurers. Do not use industrial ROIC ratios on financial issuers.
3. Clear post-report issuance, options/warrants and ISIN continuity through the historical decision cutoff, before joining a price.
4. Freeze independent 252/504/756-session value-creation selection and a control portfolio. No realized future long-horizon returns currently exist.
5. Archive this source pack before historical Actions artifacts expire in early 2027, with custody and access appropriate to exchange document reuse rights.

**All 100 are source-accounting-ready for four specified raw cells. All 100 remain blocked from an investment recommendation.**
