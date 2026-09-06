# Artifacts

Binary research artifacts are tracked by content hash and provenance.

## 2026-09-06 earnings-edge workbook

File: `india_earnings_edge_experiment.xlsx`

SHA-256:

```text
b7dbb16f5149e74adc25a7db3de3413283220cbc3cc892aabea50688b2f20b37
```

The workbook was generated during the initial feasibility experiment and contains the frozen design, pilot data, literature references, and robustness checks.

The current GitHub connector used to initialize this repository can create UTF-8 repository files but cannot directly attach the local binary workbook through the contents API. The workbook is therefore referenced by hash in this foundation commit rather than silently omitted or converted into a lossy representation.

A future local clone can add the exact binary only if its SHA-256 matches the value above.
