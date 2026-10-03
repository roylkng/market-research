# AB001 P004 Protocol Amendment P1: Source-Aligned RG001 Context

Frozen: 2026-10-03
Status: FROZEN BEFORE ANY P004 OUTCOME RUN
Live capital: DISABLED

## Purpose

Bind P004's RG001 context reconstruction to the exact historical market panel
already used by the sealed AB001 P003 alpha source.

## Frozen market source

P003 market panel SHA-256:

`9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e`

Source window:

- 2025-09-01 through 2026-09-25.

P004 must rebuild RG001-v1 from this exact panel.

The broader RG001 standalone materialization through 2026-10-01 remains useful
as a reusable context plane, but it is not the P004 historical test input.

## Rationale

Using the exact P003 market panel prevents:

- source-window drift;
- later-market-data inclusion;
- context reconstruction from a different market snapshot;
- accidental differences in session calendars or equity identity availability.

## Frozen gate

P004 fails closed unless:

    rg001_panel.market_panel_sha256
    ==
    9e644012720084a693071a40ce9c592b4586f8c6cee8445fcf7aa599be94b41e

No P004 outcome was opened before this amendment.
