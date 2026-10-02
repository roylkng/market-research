# PO001 I004 Protocol Amendment P1: Action/Feature Provenance Equivalence

Frozen: 2026-10-02
Status: FROZEN BEFORE ANY I004 RISK-TREATMENT PORTFOLIO RESULT
Live capital: DISABLED

## Trigger

The first frozen I004 materialization attempt, workflow run 36966635629,
completed the market, corporate-action and delivery-source rebuilds and failed
closed before either RM001-v1 or RM001-v3 optimizer result was interpreted.

Failure:

    I004 delivery feature panel does not reproduce frozen source

The original I003 top-level delivery-feature panel SHA was:

    47ee538af6cfca16405632ce6396571455a548687b4ceabfd7999040a86f8b44

The 2026-10-02 rebuild produced:

    ec30be42b56ecc82032bb07322d6d56ac11b7a703ce63537b48519ef525ceb75

No I004 treatment portfolio existed when this amendment was frozen.

## Root cause audit

Pre-result diagnostic workflow run:

    36967504413

Compared the exact sealed successful I003 evidence from run 36610045578 with
the exact failed I004 evidence from run 36966635629.

### Corporate-action source

Legacy normalized ledger SHA:

    a63ef3366be68ce513a585efde78bf85d7fb9b2601b5d60348d7cf4ec7ffe4a9

Current normalized ledger SHA:

    02150a5797fff0b62e6e797d5741f9e50a30d489ab81d2e24286c8e65828cac9

Both contain exactly 142 normalized share-changing records.

Canonical normalized-record hash for BOTH:

    e61d0bc5f64a114f1cc03470f0a31509642a3075f1deb75ace420204b145a7ae

Only these corporate-action top-level fields differed:

- ledger_sha256;
- source_chunks.

Classification:

    SOURCE_PROVENANCE_REVISION_ONLY

### Base action-safe features

Both contain exactly 234,401 stock-date rows.

Frozen economic row projection SHA:

    f168d81df17870cdd13c0e63c7bc8610b74922f8e8c86abd47c774325f4ffecc

Frozen session/universe projection SHA:

    9f5ce211cd75f2e921bbad383bbc7a7ce81ef1c22a91bb6dae85bc68454defa6

Frozen feature-definition SHA:

    59f1dc81dfd0e09d29e144244668114fe00a7bddfe156f67436163b0e771242d

All three hashes are identical between I003 and I004.

Only:

- corporate_action_ledger_sha256;
- panel_sha256

differed.

### Delivery/VWAP augmented features

Raw delivery panel SHA in BOTH runs:

    3d1755bad85a8cebcbc27effbe3a1a4c33a01ebdad47a0c9ea15a89febb6de96

Both contain exactly 234,401 stock-date feature rows.

Frozen economic row projection SHA:

    640694c8c5e44398281912b0d2d64551f63d21f9a76d33ebde577f5e3038a163

Frozen session/universe projection SHA:

    9f5ce211cd75f2e921bbad383bbc7a7ce81ef1c22a91bb6dae85bc68454defa6

Frozen 27-feature-definition SHA:

    de753b2357df96308d999adb1636c18d2c0770cf3e9e5f631b9ba7cbb577bd7b

All three hashes are identical between I003 and I004.

Only these top-level provenance fields differed:

- base_feature_panel_sha256;
- corporate_action_ledger_sha256;
- panel_sha256.

## I004 source gate after P1

The legacy top-level I003 panel SHA remains immutable provenance.

I004 executable feature equivalence is now defined by ALL of:

1. exact raw delivery panel SHA:
   3d1755bad85a8cebcbc27effbe3a1a4c33a01ebdad47a0c9ea15a89febb6de96;
2. exact 27-feature-definition projection SHA:
   de753b2357df96308d999adb1636c18d2c0770cf3e9e5f631b9ba7cbb577bd7b;
3. exact session/universe projection SHA:
   9f5ce211cd75f2e921bbad383bbc7a7ce81ef1c22a91bb6dae85bc68454defa6;
4. exact stock-date economic feature projection SHA:
   640694c8c5e44398281912b0d2d64551f63d21f9a76d33ebde577f5e3038a163;
5. exact feature-row count:
   234401.

This gate is stricter about the information consumed by the alpha/execution
model while allowing source-chunk provenance to evolve independently.

Any feature value, identity, session universe or feature-definition change fails
closed.

## Unchanged I004 specification

This amendment changes no:

- alpha model;
- alpha prediction;
- decision session;
- execution input;
- risk state;
- NAV;
- cost parameter;
- optimizer parameter;
- factor constraint;
- outcome boundary.

The only treatment input remains RM001 risk_state.

No post-31-Aug outcome is opened.

No live-capital implication.
