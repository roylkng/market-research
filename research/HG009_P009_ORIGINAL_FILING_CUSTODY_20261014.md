# HG009 P009: original NSE issuer filing custody for remaining fundamental dossiers

**Registration date:** 2026-10-14. **Capital:** disabled. **Document collection is not a financial forecast.**

## Why this work is necessary

P008 now has three original NSE FY26 source files (ACUTAAS, ACE and TRAVELFOOD), with nine financial statement rows validated against original retrieved bytes. Seven other economic research dossiers still rely on partial extracts, previously recorded transaction documents, or source URLs. P009 fills the specific source custody gap for **five original issuer filing documents** across four companies:

| Issuer | Original source type | Filing document | Existing research |
|---|---|---|---|
| MAYURUNIQ | NSE original iXBRL HTML | FY26 consolidated audited integrated filing, May 20 | P003 manual operating cash conversion |
| PIXTRANS | NSE original iXBRL HTML | Q1 FY27 standalone August 7 | P003 investment FVTPL quality |
| PIXTRANS | NSE original iXBRL HTML | Q1 FY26 standalone August 8, 2025 | P003 prior-year standalone comparison |
| DATAMATICS | Original NSE filing PDF | May 21, 2026 consolidated FY26 result | HG007 P049 cash valuation reverse hurdle |
| POKARNA | Original NSE filing PDF | May 28, 2026 financial outcome | P008 original FY26 values blocked until visual review |

The actual URLs and source IDs are **derived from hash-pinned prior P003/P049 and P008 original research files**. Arbitrary issuer URLs are not accepted. If any underlying original source metadata changes, archival must stop instead of collecting a different document.

## Proof and publication states

1. Retrieve via HTTPS strictly on nsearchives.nseindia.com. No redirects, no untrusted host, no unknown issuer paths.
2. Record the **actual UTC retrieval attempt**. The historical filing date is only the *declared document publication date*. Do not backdate the source.
3. Preserve the exact raw bytes for HTTP 200 responses matching expected preliminary PDF/HTML file signatures. Compress with a deterministic gzip and retain under a content-addressed SHA-256 filename. Validate byte-for-byte on every replay.
4. Preserve 302, 403, 404, 429 and network failures as separate signed attempt receipts. A 200 HTML access-denied page is not a verified original filing, and an unrecognized content type is never promoted.
5. Even with successfully archived bytes, the status remains **RAW_ARCHIVED_NOT_YET_FINANCIALLY_OR_IDENTITY_VALIDATED**. The initial format test does not verify financial period, ISIN, cash-flow table, published audited accounting basis or parent shareholder entitlement.
6. An independent source-replay script verifies every original file and each original source receipt without relying on an online response.
7. Only a later independent page/table review may promote a P009 original to verified issuer financial facts. The original P008 DCF continues to refuse incomplete equity value models.

This is a **source acquisition workflow**, not five new company valuations. It deliberately does not fabricate POKARNA FY26 cashflow, infer PIXTRANS consolidated owner earnings from standalone PBT, promote cash/investment assets to distributable money, or estimate an annual stock return.

## Reproduce

- scripts/archive_hg009_p009_originals.py (run with a unique --run-id)
- scripts/verify_hg009_p009_originals.py
- tests/test_hg009_p009_originals.py
- research/hg009/p009-originals/

The source archive is append-only by run ID, and each retrieved filing is addressed by its original SHA-256. The research may subsequently replay stored financial pages, but **0/10 completed current-owner-cash valuations** remains correct until separate fully diluted share, cash, capex, minority and forward return calibration are complete.

## Source-custody findings and outstanding integrity defects

- First successful original HTTP attempts on October 15 IST archived MAYURUNIQ FY26, PIXTRANS standalone Q1 FY26 and Q1 FY27, and DATAMATICS FY26 as content-addressed originals. These are **raw files not automatically verified financial statements**. Each original receipt retains its UTC attempt/retrieval clocks.
- POKARNA's original audited outcome PDF is a large (~20 MB) official filing. The initial Git archive limit does not accept such a file. A forward-only attempt records the response SHA and byte length with state `BLOCKED_OVERSIZE_ORIGINAL_NEEDS_EXTERNAL_BYTE_STORE`; it does not claim the large PDF is absent or label it an invalid document. A content-addressed object-store source with independently auditable bytes is needed to complete this source gate without overloading Git.
- An independent P009 canonical source-validation test found that the historical DATAMATICS P049 JSON self-checksum does not recompute, despite its exact historical Git blob being pinned. This inconsistency is preserved, tracked under [issue #446](https://github.com/roylkng/market-research/issues/446), and **does not** justify changing that historical source or fabricating a new P049 price observation.
- The revised P009 receipt records HTTP request start and **post-HTTP completion UTC** separately. Earlier first-run records retain their original source fields as historical attempt receipts, but cannot be treated as finer-than-available first-byte timing evidence.

No archival state authorizes current diluted shares, cashflow normalization, dividends, full market-return performance or capital.
