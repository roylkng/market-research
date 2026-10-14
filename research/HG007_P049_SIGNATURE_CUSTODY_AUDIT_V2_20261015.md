# HG007 P049: source-preserving Datamatics legacy integrity audit

**Audit date:** 2026-10-15. **Original report:** \`research/hg007/hg007-p049-datamatics-cash-hurdle-v1.json\`.

The historical Datamatics original report is frozen, with Git blob SHA-1 \`706c2dd100a49859b5054323baeddc345531fb59\`. A new independent checksum validator detected that the old embedded \`packet_sha256\` is not equal to the canonical digest of all its original fields after removing \`packet_sha256\`. The blob ID remains valid. That discrepancy must **not** be hidden or retroactively repaired by overwriting the original file.

This P049 v2 packet records the original blob, the legacy claimed self-signature, independently recomputed canonical SHA, dated October 13 NSE price and explicit no-value/no-capital status. The exact source byte hash and the v2 report are generated and independently checked by \`scripts/audit_hg007_p049_signature.py\`.

The new v2 packet does **not** replace or revise any of the historical reported Datamatics FY26 cashflow observations, the earlier 12x/16x/20x illustrative price-equivalent sensitivities, or the frozen original 28-company source selection. Those earlier financial numbers still require original NSE PDF byte reconciliation and present-day fully diluted equity analysis. Old packet validity cannot be restored through copying its self-signature into a future economic model.

This audit is an explicit discrepancy disclosure and durable historical integrity control, not a new expected return, dated trade, or resolved corporate action. All live capital remains disabled. Related [issue #446](https://github.com/roylkng/market-research/issues/446).
