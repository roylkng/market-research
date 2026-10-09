# SS002-P004 Eight-Document Current Event Understanding Pilot v1

Status: **FROZEN BEFORE FULL SOURCE TEXT INTERPRETATION**  
Frozen: 2026-10-10 (Asia/Kolkata)  
No return outcomes, market-cap valuation, share-count clearance, ADO, PF001 or live capital.

## Purpose

Apply the existing SS002-L001 evidence-bound transaction-fact contract to exactly
eight newly captured NSE documents from SS002-P003.

This is an LLM *semantic understanding* pilot, not a stock-selection or return
prediction experiment. The documents were selected for diversity of upstream
keyword families, issuer size and procedural-vs-economic ambiguity, **not**
because subsequent price movements were favorable.

## Immutable input

- SS002-P003-v1; workflow run `37982329060`;
- artifact `ss002-p003-37982329060` (ID `11642216135`);
- corpus SHA-256 `7abbe52043b7ef3de89cb617d4fba2b181c3d8c4978df7a29ea557eab54469f7`;
- source events from 2026-10-05 to 2026-10-08;
- only exact official NSE documents and P003 deterministic text segments.

### Frozen eight source documents

| Symbol | Upstream keyword family | Document SHA-256 |
| --- | --- | --- |
| VRLLOG | BUYBACK | `f4aa6bc559658aae64da1540b6683e5d46ed3c68a0be1d11948cb1fb0d4b6a24` |
| PVRINOX | BUYBACK | `fa31ca687e2b419813879d464990117b5f8917abd1006c5dec7ecae1a8da1058` |
| OLAELEC | RIGHTS_ISSUE | `f8a46405d8b7c10bc12f47c945b5cc96956600273fc5868edbd004baa4808b92` |
| SAMBHV | PREFERENTIAL_WARRANT | `432611a5ca2aafd37ae11b6435ff8eda8c6652d5be2f2888fed47cbee92d41b1` |
| INOXGREEN | INSOLVENCY_RESOLUTION | `541277b2c8a6d732bc77e62c6b637c98b92a5044dddeac09e34038d8d4d5d451` |
| KOTHARIPET | SCHEME_REORGANISATION | `17ff4dbc9d62243ffb7ccc3ca78a903eecb3991bf091e27030f384fe725bf891` |
| PREMEXPLN | OPEN_OFFER_CONTROL | `6e9ef61a11d6a47a771e6d9ec255507cd14104016a5baa682317bef3c206baf5` |
| TVSSRICHAK | CAPITAL_REDUCTION | `f619d7a5473c6e34268f2aaf1440b7276ec807789c04fa6a8481ba4ab3d10659` |

No substitutions, cherry-picking after observing model output, or removal of
difficult/noisy documents.

## LLM semantics

- model/runtime: `CHATGPT_NATIVE_INTERACTIVE / GPT-6`;
- one source document per inference;
- no web search, filing outside the sealed P003 document, stock price or issuer lore;
- input must retain exact P003 segment IDs and hashes;
- output must conform to `SS002-L001-v1` plus a separate human-readable
  `case_assessment` description which does not enter the L001 JSON;
- every EXPLICIT fact must cite at least one exact P003 segment ID;
- an ambiguous or absent term must be UNKNOWN;
- no extrapolation or completion probability estimate.

## Validation and status

- deterministically verify the frozen corpus SHA and 8 document IDs;
- recompute every cited text-segment SHA-256;
- run `validate_extraction` against the exact input IDs;
- keep raw model response separate from host-added provenance;
- keep semantic audit status `PENDING_INDEPENDENT_REVIEW` unless independently
  checked against source pages by a second reviewer;
- retain exclusions, false positives and incomplete results;
- never label an event as investable merely because JSON validates.

Passing automated validation allows transaction-thread research only,
not price/IRR predictions or portfolio positions.
