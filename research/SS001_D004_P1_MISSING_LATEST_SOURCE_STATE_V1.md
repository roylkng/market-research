# SS001-D004 P1 Missing-Latest-Source Failure-State Amendment

Status: **FROZEN AFTER D004 RUNNER ABORT, BEFORE FULL D004 RERUN**  
Frozen: 2026-10-08  
Return outcomes opened: no  
Market-cap outputs: prohibited

The first full-market D004 execution stopped before writing a source-feasibility
panel. The runner incorrectly assumed every GF001-D002 `source_state=READY` row
contains a successfully retrieved latest XBRL. GF001-D002 source readiness means the
official filing URL exists; its previous parser is permitted to fail acquisition.

P1 changes only source accounting:

- if a GF001 source-ready identity has `latest=null`, emit
  `RAW_UNAVAILABLE / LATEST_RAW_SOURCE_NOT_READY`;
- if it has a latest source but no valid SHA or content-addressed file, emit
  `RAW_UNAVAILABLE` with an explicit reason;
- do not impute a share count;
- do not count any RAW_UNAVAILABLE row toward the 90% count or 85% capitalization
  thresholds;
- require full 2,319 identity and 2,050 latest-source accounting as before.

No ratio tolerance, semantic concept, source population, numerator, denominator,
share-class policy, outcome or feasibility threshold changes.
