# HG007 P049: source-preserving Datamatics legacy integrity audit

**Audit date:** 2026-10-15. **Original report:** \`research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json\`.

The historical Datamatics original report is frozen, with Git blob SHA-1 \`706c2dd100a49859b5054323baeddc345531fb59\`. A new independent checksum validator detected that the old embedded \`packet_sha256\` is not equal to the canonical digest of all its original fields after removing \`packet_sha256\`. The blob ID remains valid. That discrepancy must **not** be hidden or retroactively repaired by overwriting the original file.

This P049 v2 packet records the original blob, the legacy claimed self-signature, independently recomputed canonical SHA, dated October 13 NSE price and explicit no-value/no-capital status. The exact source byte hash and the v2 report are generated and independently checked by \`scripts/audit_hg007_p049_signature.py\`.

The new v2 packet does **not** replace or revise any of the historical reported Datamatics FY26 cashflow observations, the earlier 12x/16x/20x illustrative price-equivalent sensitivities, or the frozen original 28-company source selection. Those earlier financial numbers still require original NSE PDF byte reconciliation and present-day fully diluted equity analysis. Old packet validity cannot be restored through copying its self-signature into a future economic model.

This audit is an explicit discrepancy disclosure and durable historical integrity control, not a new expected return, dated trade, or resolved corporate action. All live capital remains disabled. Related [issue #446](https://github.com/roylkng/market-research/issues/446).

## Independent replay result

The canonical October 15 audit recomputed SHA-256 **0c2f0a2ee54df8067974f4cb421d0344577590268ab7dbd9d35e9cd31d2d22ef**, which differs from the original claimed **1b72056878c56f12f5c13b8f7d557d1fa8fa0e67c34fddd60621ffd890cfb278**. Original raw SHA-256 is **aa7f52fd1eee192cdd53a0a1923f26c8de51fc28ab41634b584f06871d6305f1**, and its original Git blob remains **706c2dd100a49859b5054323baeddc345531fb59**.

The v2 integrity audit is itself signed as **2e68cd73f4605a7899b7be9d4f66f34b13e65a71fb062adbb169fcbdaaf0dd28**. These hashes are reproducible checks of the old JSON bytes, not proof that every manually transcribed FY26 financial statement cell is economically correct. No historical report was rewritten.
