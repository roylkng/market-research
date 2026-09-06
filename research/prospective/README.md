# Prospective H002 capture

This directory is reserved for **future** H002 prospective observations.

No file in this directory may be backfilled from historical data and relabeled as prospective.

Prospective capture is enabled only when all of the following are true:

1. a frozen U001 universe snapshot exists for the cohort,
2. the observation symbol is present in that snapshot,
3. NSE discovery metadata is captured before or at source acquisition,
4. the original source bytes are captured and SHA-256 hashed,
5. exchange publication time is preserved separately from local capture time,
6. the resulting event is marked `PROSPECTIVE`,
7. no H002 signal or paper position is generated until the subsequent signal/execution gates are implemented.

Historical reconstruction records belong under `research/historical-reconstruction/` and are never promoted into this directory.
