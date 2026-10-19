# H021: independent original NSE daily source backstop (October 19, 2026)

## Observed gap

Original H021 full-market NSE UDiFF and Nifty 500 source files are anchored through October 16, 2026. By October 19 late evening, the canonical repository had no October 19 daily source attempt or market source artifact. The last primary H021 workflow in the accessible Actions history ran October 16. The scheduled configuration existing in YAML is not proof that later jobs executed.

NSE lists October 19 as a trading session and October 20 as a Dussehra holiday. Actual source retrieval after the October 19 close is permissible as a late source observation, but never as a retroactive October 19 pre-open order, earlier model decision or an altered time stamp.

## Redundant source trigger

- Independent workflow watches the actively running AE001 SC001 prospective source workflow, schedules staggered independent weekday runs and supports manual dispatch.
- It uses **the exact same cross-workflow concurrency group** as primary H021, preventing simultaneous source attempts against the shared bounded three-attempt session budget.
- It executes the existing frozen H021 session resolver with narrowly permitted original 404 recovery, and the existing original NSE source capture script.
- It records real UTC capture and failure times, original 200/404/403 statuses, hashes original market ZIP and index CSV bytes and retains append-only attempt receipts.
- It publishes immutable original H021 market data only when independently transport-ready. Never forges missing original sources, alters the original company cohort or claims it is a trade.
- It rejects conflicting original dates, protocol changes or GitHub push failures rather than forcing a source update. Original market bytes remain canonical for the 300-company HG009 replay.
- Unlike the source-only observation workflow, T012 decision admission remains bound to its **own preregistered pre-open deadline**. A later observation cannot rescue a missed T012 decision.

## Required validations

Run Ruff against the unchanged H021 resolver/collector and new test. Run pytest on the new backstop test and existing delayed-publication tests. The test checks October 19 is the next source-missing completed trading session after original October 13–16 copies; it excludes October 20 and refuses 19 October before the official close.

Green collector workflow means the scheduler and source logic ran, not that the exchange file was available, all original 300 company prices existed, or statistical alpha was established. H20 still requires independently verified November Muhurat treatment and H60 needs a forward-only official 2027 cash calendar amendment.

This repair leaves the frozen HG009 100+100+100 memberships, T012 trial, source decision cutoffs, and all past source-time records unchanged. No live capital permitted.
