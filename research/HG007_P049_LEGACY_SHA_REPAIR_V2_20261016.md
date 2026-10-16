# HG007 P049 signature discrepancy: forward-only v2 evidence

**Logged:** 2026-10-16. **Original study:** historical Datamatics FY26 cash sensitivity assembled October 14 and source prices October 13.

The legacy Datamatics report at research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json has a **reproducible packet signature discrepancy**: its historically embedded packet_sha256 does not match the digest of the parsed original body under the project's current canonical JSON digest function. This discrepancy was discovered during independent HG009 source-archive checks.

The original historical file and its Git blob **706c2dd100a49859b5054323baeddc345531fb59** are immutable and remain in place. The original October 13 whole-market NSE source Git blob **5e495c980985e0c42c112868cb04bfffb27807dd** and its valid embedded packet signature remain independently verified. The original price, issuer identity and historical reported cash fields have not been rewritten.

The new v2 report is only an **append-only signed discrepancy receipt**, recording the precise prior claimed digest, the recomputed canonical digest, source byte SHA, signed original market linkage and original research restrictions. We do not yet assert that an integer-versus-float spelling or any other single serialization detail is conclusively the cause. This can be investigated using original bytes without guessing.

Downstream investment models must reject the legacy record as fully self-signed. They may use the original Git-blob-pinned historical data **with explicit discrepancy warnings**, or the v2 source-replay receipt. Neither upgrades the old Datamatics ₹284.42 crore CFO-minus-selected-capex approximation to owner earnings, verifies current diluted shares, or supplies a valuation/return probability.

No buy recommendation, no live capital, no fabricated price correction and no retroactive market signal are created. Regression tests reject arbitrary re-signing, altered original Git bytes and current-date valuation promotion.

Reproducibility: scripts/materialize_hg007_p049_sha_repair.py; tests/test_hg007_p049_sha_repair.py. Related tracked blocker: issue #446.


## Verified immutable discrepancy record

The original P049-v1 embedded checksum is 1b72056878c56f12f5c13b8f7d557d1fa8fa0e67c34fddd60621ffd890cfb278. The project's current exact canonical MarketLab digest of the same original, unmodified JSON body is **0c2f0a2ee54df8067974f4cb421d0344577590268ab7dbd9d35e9cd31d2d22ef**. They do not match.

The source-freezer produced a **new**, signed v2 discrepancy report, SHA **5e7c8acf9ec679bc27f5942732dc90fb837e6bf7726ce2118db0a7284e310cde**. The original v1 Git blob and original official October 13 market packet were not edited.

The discrepancy is real and attributable to the historical signed JSON representation, but the precise production cause is intentionally recorded as *unproven*. No quantitative Datamatics expected-return result has been promoted through the repaired receipt.
