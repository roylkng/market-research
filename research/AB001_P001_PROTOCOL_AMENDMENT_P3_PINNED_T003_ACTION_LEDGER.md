# AB001 P001 Protocol Amendment P3: Pin Sealed T003 Corporate-Action Ledger

Frozen: 2026-09-30
Status: FROZEN BEFORE VALID P001 MATERIALIZATION
Live capital: DISABLED

## Trigger

P001 source reconstruction discovered that the NSE historical corporate-action
endpoint no longer reproduces the exact source-chunk hashes captured by sealed
T003.

The first pre-maturity P001 run 36669808434 failed closed on the resulting
augmented feature-panel hash mismatch.

The corrected P1/P2 run 36670213817 also began before this source-provenance
issue was resolved and is permanently excluded from valid P001 evidence.

## Equivalence audit

Diagnostic run:

36670723158

Compared exact sealed T003 evidence from run 36533659236 against the rebuilt
P001 evidence.

### Corporate-action ledger

Sealed T003 ledger SHA:

1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1

Rebuilt ledger SHA:

ae628bb05e9294efd073bab7152856022906fd84b234ed7f481531fd9ec2a8fd

Findings:

- normalized action records exact: TRUE;
- old-only normalized records: 0;
- new-only normalized records: 0;
- source chunk count old/new: 13 / 13;
- source chunk provenance exact: FALSE.

Therefore the drift is source-response provenance, not a changed normalized
share-action set.

### Action-safe feature panel

Sealed T003 panel SHA:

300c45cc6cd5f3e0b37dc419c2d6250317175f367bd74757f1ad45b4a4af63c8

Rebuilt panel SHA:

151eba8359243442a8c90da7a9b3607f1ccd486d3e749c1c4b7d1b16034dce4d

Findings:

- feature row count identical: 258006;
- feature rows exact: TRUE;
- session economics exact: TRUE.

The panel hash differs only because the embedded corporate-action ledger SHA
changed.

### Delivery-augmented feature panel

Sealed T003 panel SHA:

99c0c34da30a9318c428d44d68d23360c7588a618e54cad80acde22a959c2e90

Rebuilt panel SHA:

54a378ac2af33ed1244285f378a34071e593ffc38e9aa78cd9613f70a6596826

Findings:

- feature row count identical: 244855;
- symbol + ISIN + session identity symmetric difference: 0;
- feature-value difference rows: 0;
- full augmented rows exact: TRUE.

Classification:

CORPORATE_ACTION_SOURCE_PROVENANCE_DRIFT_WITH_EXACT_FEATURE_ECONOMICS

## Frozen resolution

P001 will not adopt the revised historical NSE action-response representation.

Instead it will pin and verify the exact sealed T003 corporate-action ledger:

- source workflow run: 36533659236;
- source artifact ID: 11017864952;
- source artifact name: ae001-delivery-pilot-36533659236;
- source path:
  reports/ae001-delivery-pilot/action-safe/corporate-action-ledger.json.gz;
- internal ledger SHA:
  1238ec2c4b2697cf52ea66194aeb0d70171a22071f7249e3fcdc8a8f83ede5c1;
- gzip artifact SHA:
  6ee878d48eadae0b76c7b4db3a02b3f1fb6cada61c2d3c39b40fb872b1622e2d.

The pinned ledger is the executable corporate-action input for P001.

The official market panel and delivery panel continue to be rebuilt because they
already reproduce the sealed T003 hashes exactly.

## Valid P001 source chain after P3

1. rebuild the sealed market panel;
2. load the exact pinned T003 corporate-action ledger;
3. regenerate the action-safe feature panel from the pinned ledger;
4. require exact sealed action-safe panel SHA;
5. rebuild delivery data;
6. require exact sealed augmented panel SHA;
7. require P2 A1/A2 OOS metric reproduction;
8. only then construct the AB001 library.

## Invalid workflow attempts

The following runs are permanently excluded from valid P001 evidence:

- 36669808434: INVALID_PRE_MATURITY_FIX;
- 36670213817: INVALID_PRE_PINNED_ACTION_LEDGER.

No metric or artifact from either run may be used as the P001 result.

This amendment changes no alpha feature, label, fold, model, blend parameter or
outcome rule.
