# Prospective capture v1

Prospective H002 observations require two independent clocks and two independent hashes.

## Clocks

- `exchange_published_at_utc`: publication time reported by exchange discovery metadata.
- `captured_at_utc`: time our collector received and persisted the source bytes.

A source cannot be accepted as prospective if the exchange publication time is missing or later than the local capture time beyond configured clock-skew tolerance.

## Hashes

- discovery payload SHA-256 preserves the exact metadata record that led to the filing.
- source SHA-256 preserves the exact original filing bytes used for parsing.

A parser output is always linked to both where available.

## Eligibility gate

Prospective capture requires a frozen U001 universe snapshot. The symbol must be present in the snapshot before the filing outcome is known. The snapshot hash and cohort id are recorded on the event.

## Revision behavior

If NSE later publishes corrected source bytes for the same economic event, the new bytes create a new immutable version. The original version remains available and is never overwritten.

## No downstream decisions here

Prospective capture does not compute UE/SUE, open paper positions, or make investment recommendations. Those belong to later H002 gates.
