# AE001 T009 Protocol Amendment P1: Frozen Source Materialization

Frozen: 2026-10-01
Status: FROZEN BEFORE OUTCOME MATERIALIZATION
Live capital: DISABLED

## Purpose

Freeze the exact T009 source-only materialization from workflow run
`36821482949` before any future-return label is opened or any T009 model is fit.

## Reproduced upstream lineage

- market panel: `9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e`
- action-safe feature panel: `300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8`
- corporate-action ledger: `1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1`
- delivery 27-feature panel: `99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90`
- futures source panel: `02656c828a1d5fe22660c154a445ebd69a7492b56f1807da0d8c959a6f0c11d5`
- futures 37-feature panel: `62dd3c2f50fcaf6d58e47526df76aff41f2a4c2ec43c2a5724f7c23611af803f`

## New T009 source artifacts

- D006 FO source-hash chain: `edf21ed30ea4021a82118c8699f1a7470442bcee29155810772a09c4b24bc6dc`
- options panel: `e621da419f3562acf8737b00c7acd25199b70c9280d7c3872e331391e23d3912`
- options-augmented 47-feature panel:
  `e1e30b94f86aa459bd422b1815701d1eda61e7d6fc7a2736dcf4227c698cba1e`

## Coverage

- READY options sessions: 266
- unavailable sessions: 0
- parser-rejected sessions: 0
- option-complete sessions: 196
- option-complete stock/session rows: 39811

Exclusion counts:

```json
{
  "NONPOSITIVE_PAIRED_PRIOR_OI": 18
}
```

## Outcome boundary

The source-only run explicitly reports:

- `outcomes_opened = false`
- `model_fit_started = false`

P1 changes no T009 feature, fold, horizon, ridge parameter or success criterion.

Historical FO publication timing remains unverified. No prospective or
live-capital claim.
