# Analyst Decision Object ledger v1

This directory contains immutable sealed Analyst Decision Objects consumed by PF001.

Rules:

- one JSON file per sealed decision;
- filename should be `<decision_id>.json`;
- existing decisions are never edited to improve an outcome;
- a later view is a new decision object with a new timestamp and digest;
- `DEVELOPMENT` decisions may exercise the machinery but cannot become PF001 validation evidence;
- `PROSPECTIVE_VALIDATION` decisions must satisfy the PF001 post-freeze and pre-entry timing rules;
- `WATCH`, `REJECT`, and `HOLD_REVIEW` objects remain analyst evidence but are not selected for new PF001 entries;
- live capital remains disabled.
