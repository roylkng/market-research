# H021 / AE001 September 11 Legacy-Seal Compatibility Repair

Status: **SOURCE-FORMAT REPAIR ONLY — NO REVISION RULE CHANGE**  
Dated: 2026-10-09  
Return outcomes opened by repair: no  
Live capital: disabled

## Observed failure

Scheduled H021 acquisition runs on 2026-10-08 UTC reached the primary comparison
and Tier A gates, but the later AE001 expectations materializer failed before
anchoring any capture.

It attempted to verify the immutable 2026-09-11 full-U001 v1 capture with the
v2 sealed-artifact verifier and rejected its original schema/serialization.

That September 11 capture is the only eligible 28–35-day anchor for October 9.
Deleting it, reconstructing it, or selecting a different shorter interval would
change the prospective experiment and is prohibited.

## Narrow compatibility rule

The AE001 reader accepts exactly one historical v1 bundle:

- `2026-09-11-full-u001-v1.json.gz`;
- v1 manifest schema;
- gzip SHA-256
  `94bdbbc4fa4e8fa70f1535797f165dfbab52d0f937cade91425824422f9d2c33`;
- decompressed SHA-256
  `bd87a3bb942a60e7f625293577487b8850b67530b3126bea5bb7d9d9e999d434`.

For this one bundle, verify both source bytes and lengths, exact snapshot/manifest
identity, immutable source version, frozen U001 symbol membership and
symbol-to-ISIN identity binding (v1 observation ISINs may be absent; an explicitly
conflicting ISIN is rejected), batch/rank membership,
all 100 rows, prospective `outcomes_opened=false`, and matching publication date.

The original v1 JSON serialization is retained; it is not falsely described as
the later v2 canonical sealer format.

Every v2 capture remains subject to `verify_capture_bundle` unchanged.

Unrecognized v1 captures or tampering fail closed.

## Scientific boundary

No change to:

- H021's 28–35 calendar-day cohort rule;
- required analyst count or EPS/currency/fiscal period compatibility;
- Tier A primary top-decile gate;
- source capture timestamps;
- AE001 EOD cutoff or next-session timing;
- original captured bytes/manifest.

The repair must be tested against the actual checked-in September 11 bundle before
any subsequent scheduled capture is treated as successfully anchored.

The repair does not permit backdating observations, inventing today's result or
promoting an equity to portfolio eligibility.

## Delayed-cron operational timing repair

Three GitHub-scheduled attempts initiated at approximately 19:00–19:27 UTC
on 2026-10-08, which was **00:30–00:57 IST on October 9**. Date-only
session eligibility classified that pre-market Friday as the final completed
NSE session. This violated the existing frozen post-close acquisition intent.

The operational gate now additionally requires:

- an aware wall-clock timestamp whose India date equals the target date;
- on a frozen final weekly NSE session, India time **at least 18:15**;
- otherwise emit `BEFORE_POST_CLOSE_WINDOW`, without acquiring/sealing data.

The 18:15 boundary is the first pre-existing scheduled post-close attempt, not
a return-optimized timestamp. An overnight-delayed Thursday cron cannot create
Friday evidence before Friday's trading session closes.

The recorded failed source attempts are preserved and **not reclassified as
valid post-close observations**. The actual next eligible post-close acquisition
must obtain new source bytes and its true timestamp; no backdating is permitted.
