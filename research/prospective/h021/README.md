# H021 prospective capture operating path

The H021 prospective experiment is governed by three frozen contracts:

- `research/H021_PROSPECTIVE_PROTOCOL_V1.md`
- `research/H021_CAPTURE_SEALING_CONTRACT_V1.md`
- `research/H021_COMPARISON_CONTRACT_V1.md`

## Weekly capture sequence

1. Initialize the acquisition draft directly from the frozen U001 identity and batch manifest:

```bash
python scripts/init_h021_capture_draft.py \
  --capture-date YYYY-MM-DD \
  --universe research/prospective/universes/FY27-Q2-2026-09-06.json \
  --batches research/prospective/h021/capture-batches-v1.json \
  --out /tmp/h021-YYYY-MM-DD-draft.json
```

The initializer creates exactly one row per frozen symbol with immutable symbol/ISIN/rank/batch identity. All acquisition-dependent fields start deliberately incomplete: `data_state=PENDING`, source status is pending, forecast values are null, and the final capture timestamp is unset. The draft therefore cannot pass the sealer accidentally.

2. Process both frozen batches and replace every pending row with current-capture evidence. Do not delete or substitute rows. Set the capture-level `captured_at_utc` only when the logical capture is complete.

3. Validate and seal the completed draft with:

```bash
python scripts/seal_h021_capture.py \
  --draft /tmp/h021-YYYY-MM-DD-draft.json \
  --universe research/prospective/universes/FY27-Q2-2026-09-06.json \
  --batches research/prospective/h021/capture-batches-v1.json \
  --out-dir research/prospective/h021/captures
```

4. Commit only the three immutable sealed outputs on a reviewable branch. The temporary acquisition draft is working state, not H021 evidence.

5. When a compatible prior capture exists 28-35 days earlier, run `scripts/compare_h021_captures.py` against the sealed capture directory.

The initializer eliminates manual universe assembly. The sealing step is intentionally separate from source acquisition and refuses universe substitutions, stale carry-forward values for blocked names, identity drift, batch drift, unsafe capture IDs, and conflicting reuse of an existing logical capture ID.

No price or return data belong in a capture draft.
