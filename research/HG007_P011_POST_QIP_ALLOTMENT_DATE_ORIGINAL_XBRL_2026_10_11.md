# HG007-P011: Official 29 September Post-QIP Shareholding Is Not a Quarter-End Filing

Source-custody protocol frozen 11 October 2026 IST. Research only.

## Discovery

The original 11 October HG007-P010 original NSE shareholding master
(source SHA-256 dcdf2485a74174667ad230d5da200936d666a60137f62f06b52383b902d40e38)
did NOT have a normal **30 September 2026** quarterly Reg31 filing.

It DID contain a unique **29 September 2026 QIP allotment-date**
shareholding pattern:

- original NSE record ID: **213525**
- issuer: INOXGREEN, ISIN INE510W01014
- as-of report date: **29-SEP-2026**
- submission and broadcast date: **8 October 2026**
- original public broadcast: **18:54:47 IST (13:24:47 UTC)**.
- exchange master promoter percentage: **53.70%**
- exchange master public percentage: **46.30%**
- original linked NSE XBRL:
  https://nsearchives.nseindia.com/corporate/xbrl/SHP_1734551_08102026065442_WEB.xml
- source master remarks expressly identify the September 29
  Qualified Institutions Placement allotted shares as included
  in the shareholding report.

The original regular **30 June 2026** report was last revised and
broadcast 3 August, and reports basic 401,492,045, dilutive
2,467,620, fully diluted 403,959,665 and no promoter pledge.

The September 29 allotment-date event is NOT a standard September
30 quarterly signal, so it must not be silently included in frozen
H023 U001 or historical as-of-September 29 investment decisions.

Its first broadcast on October 8 means the filing could have been
available before an October 9 market open, but absolutely not before
October 8 18:54:47 IST. No backdating is allowed.

## Source acquisition and validation

The P011 script pins the *exact original* NSE 11 October master
bytes, recorded event identity, date, source URL and percentages,
then accesses only that official XBRL URL.

Where raw XBRL is accessible it is hashed and retained exactly. The
existing audited share-count and ownership-governance parsers report:

- issued shares and FD shares **as of the Sep29 filing**,
- issued share count must reconcile to QIP 419,602,518 or be
  explicitly rejected,
- dilutive ESOP/convertibles delta to basic at Sep29,
- aggregate promoter/public percentages and promoter-pledge BOOLEAN,
- the source's own review status and SHA-256.

A boolean is not an official verified pledged-share QUANTITY. The
secondary 4.9-million number must not be declared proven until an
independently verified original source share count is extracted.

The P011 output explicitly prevents claims that Sept29 XBRL rules out
later share issues, or that an Oct11 fully diluted valuation has been
verified. Corporate-action bridge from Sept29 until the price date
and actual pledge quantity remain separate independent checks.

## Operational control

- Source: src/marketlab/hg007_special_shp.py
- Collector: scripts/collect_hg007_special_shp.py
- Tests: tests/test_hg007_special_shp.py
- Workflow: .github/workflows/hg007-post-qip-special-xbrl.yml

Original source bytes and receipt:

research/hg007/inoxgreen-post-qip-special/

The workflow makes a bounded first on-merge attempt with retry
windows. If NSE blocks the attachment, the source gap is preserved
as an independent GitHub Actions artifact rather than fabricated
ownership or company shares.

## Investment/readiness boundary

No QIP company enterprise value, earnings normalization, WWIL
closing-date assumption, Authum minority conversion probability,
stock expected return, signal backtest, capital position, or
recommendation is authorized.

Original HG005 (March-FD denominator at Oct1 price), P008
(corrected Sep29-issued basic share references), and P009
(28-case stale-FD warning) remain immutable.
