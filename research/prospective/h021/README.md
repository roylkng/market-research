# H021 prospective capture operating path

The H021 prospective experiment is governed by three frozen contracts:

- `research/H021_PROSPECTIVE_PROTOCOL_V1.md`
- `research/H021_CAPTURE_SEALING_CONTRACT_V1.md`
- `research/H021_COMPARISON_CONTRACT_V1.md`

## Weekly capture sequence

1. Process the frozen U001 panel in the two batches defined by `capture-batches-v1.json`.
2. Build a draft full-capture JSON containing exactly one row for every frozen symbol.
3. Validate and seal the draft with:

```bash
python scripts/seal_h021_capture.py \
  --draft /path/to/draft.json \
  --universe research/prospective/universes/FY27-Q2-2026-09-06.json \
  --batches research/prospective/h021/capture-batches-v1.json \
  --out-dir research/prospective/h021/captures
```

4. Commit the three immutable outputs on a reviewable branch.
5. When a compatible prior capture exists 28-35 days earlier, run `scripts/compare_h021_captures.py` against the sealed capture directory.

The sealing step is intentionally separate from source acquisition. It refuses universe substitutions, stale carry-forward values for blocked names, identity drift, batch drift, and conflicting reuse of an existing logical capture ID.

No price or return data belong in a capture draft.
