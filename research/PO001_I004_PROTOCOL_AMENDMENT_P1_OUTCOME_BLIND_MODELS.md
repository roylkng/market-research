# PO001 I004 Protocol Amendment P1: Outcome-Blind Model Reconstruction

Frozen: 2026-10-01
Status: FROZEN BEFORE FIRST I004 MATERIALIZATION
Live capital: DISABLED

## Reason

The original I004 text required the reconstructed CORE27/FULL37 models to first
reproduce the sealed full T005 5D aggregate result.

That aggregate includes validation outcomes after the 2026-08-31 I004 decision
snapshot. Loading those outcomes inside I004 is unnecessary for the integration
question and conflicts with I004's frozen outcome-blind boundary.

No I004 materialization or portfolio result existed when this amendment was
frozen.

## Corrected runtime gate

I004 must NOT load, calculate or reproduce any realized 5D label whose exit is
after 2026-08-31.

Instead, model reconstruction is bound to the exact frozen T005 mechanics:

- source family definitions are unchanged;
- CORE27 and FULL37 feature lists are exact;
- ridge l2 = 1.0;
- validation fold identity remains fold 2:
  2026-07-01 through 2026-09-18;
- training is purged against validation start 2026-07-01;
- therefore every training label matures strictly before 2026-07-01;
- source acquisition for I004 ends on 2026-08-31;
- model fitting uses only the purged pre-2026-07-01 training examples;
- 2026-08-31 feature rows are scored with those fixed reconstructed models;
- no validation target is needed to score the decision snapshot.

## Source lineage gate

The I004 source builders must use the same frozen parser/feature contracts as
T005/AB001-P003.

Where a full-window artifact SHA differs solely because I004 intentionally ends
the source panel on 2026-08-31, I004 records the new artifact hash and binds
model construction to the frozen feature definitions and exact symbol+ISIN
identity rules.

## Scientific effect

This amendment is stricter than the original runtime requirement:

- no post-decision outcome enters I004;
- no T005 aggregate metric is re-opened;
- no model parameter is selected using I004 portfolio results.

T005 and AB001-P003 remain the separate evidence supporting the futures feature
family.

I004 remains a post-selection integration study and cannot create an independent
prospective-alpha claim.
