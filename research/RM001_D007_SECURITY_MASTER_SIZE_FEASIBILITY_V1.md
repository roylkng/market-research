# RM001 D007 NSE Security-Master Size-Source Feasibility v1

Status: FROZEN BEFORE FULL HISTORICAL SOURCE SCAN
Frozen: 2026-10-01
Live capital: DISABLED

## Objective

Determine whether the official daily NSE CM MII Security File is sufficient to
supply a point-in-time broad-universe total-market-cap / size input for RM001.

D007 is a source/data diagnostic. It opens no future-return labels and fits no
alpha or risk model.

## Official source

Daily NSE CM MII Security File:

    https://nsearchives.nseindia.com/content/cm/
    NSE_CM_security_DDMMYYYY.csv.gz

Historical audit window:

    2025-09-01 through 2026-09-25

The exact market sessions are taken from the already-established official AE001
UDiFF market panel. Non-trading calendar days are not expected to have files.

## Frozen required security-master fields

- TckrSymb
- SctySrs
- FinInstrmNm
- ISIN
- IssdCptl
- ParVal
- DelFlg

Only exact EQ symbol + ISIN identities are eligible.

Rows with dummy/test ISINs are excluded from semantic validation.

## Issued-size interpretation

The source field name is IssdCptl ("Issued Capital"). For listed EQ rows D007
treats it as the issued security count only if all of the following source-only
checks pass:

1. value is finite and strictly positive;
2. selected large-cap sanity rows are in the expected issued-share order of
   magnitude;
3. day-to-day exact symbol+ISIN values are stable except when the official source
   itself changes;
4. market-cap values computed as:

       total_market_cap_inr = official_close_price * IssdCptl

   are finite, positive and cross-sectionally plausible.

ParVal is retained as source metadata but is NOT used to divide IssdCptl.

No free-float market cap is inferred from this file unless FreeFltCptl is
materially populated in the audited EQ source.

## Join contract

Each daily Security File is joined to that same completed NSE session's official
UDiFF EQ panel using exact:

    symbol + ISIN

No symbol-only carry-forward across identity breaks.

## Full-scan feasibility gates

D007 passes the historical total-size source only if:

1. every completed AE001 market session in the frozen window has a downloadable,
   gzip-valid and parser-valid Security File;
2. at least 99.0% of real same-session UDiFF EQ identities have an exact
   Security File EQ symbol+ISIN row on every audited session;
3. at least 99.0% of exactly joined UDiFF EQ identities have finite positive
   IssdCptl on every audited session;
4. no duplicate Security File EQ symbol+ISIN identity exists within a session;
5. computed total market cap is finite and positive for every joined row used by
   the size factor;
6. no unexplained fixed source row cap is observed.

## Free-float diagnostic

FreeFltCptl completeness is reported.

If fewer than 95% of joined real EQ identities have finite positive
FreeFltCptl, D007 does not promote a free-float size input.

## Sector diagnostic

The Security File's AsstClss, ClssfctnTp, FinInstrmClssfctn and related fields
are audited for completeness.

They are NOT assumed to encode NSE Indices company industry classification.

Sector remains deferred unless a separately frozen point-in-time source provides
the four-tier company classification.

## Promotion

If D007 passes total-size gates:

- RM001-v2 may add total-market-cap size exposure;
- the exact daily Security File source and symbol+ISIN join must be retained;
- historical size exposure may be built for the audited window.

D007 cannot promote sector exposure.

No live-capital implication.
