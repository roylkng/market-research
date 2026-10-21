# HG009 P035: original BSE full-equity industry and ISIN cross-exchange source

**Registered:** 21 October 2026. **Research-only.** The original NSE HG009 population is fixed at 100 selected + 100 one-signal + 100 zero-signal names; previous outcomes are unchanged.

## Concrete hypothesis

The NSE Nifty Total Market **index** original source currently provides a genuine one-level industry match to only **142 of 300** frozen exact NSE symbol+ISINs. This is unsurprising for an approximately 750-company index subset. Remaining **158** names require a new complete exchange or primary issuer source.

A publicly documented **BSE active-equity directory** may supply >3,000 equity security objects with an original **ISIN_NUMBER**, **INDUSTRY**, scrip code, BSE trading symbol and market capitalization. Unlike name-based fuzzy lookups, genuine BSE and NSE shares of the same underlying listed issuer ordinarily share their ISIN. An independent exact-ISIN join could reveal additional authentic issuer industry labels for a *new* prospective cohort, even where a company lies outside the NSE index subset.

Actual original BSE endpoint tested: https://api.bseindia.com/BseIndiaAPI/api/ListofScripData_new/w?Group=&Scripcode=&segment=Equity&status=Active&scripName=

The field schema, access and actual coverage must be proven. Third-party examples of the endpoint do not substitute for official raw BSE bytes.

## Source-admission and scientific controls

1. One ordinary public HTTPS GET with a real UTC retrieval clock, no login or access circumvention and no redirect. An inaccessible response is an explicit signed **BLOCKED_BSE_ORIGINAL_ACCESS** source attempt, not a zero-company industry file.
2. Admit only a plausible >3,000-row JSON list or a uniquely identifiable >3,000-row list property. Retain original bytes content-addressed and SHA-256 signed, plus independent original replay. Do not guess nested malformed schemas or cut the data to favoured stocks.
3. Locate ISIN, industry, BSE ticker and source market-cap columns only from exact original observed schema names. Join **all 300** frozen NSE issuer identities on exact ISIN. Conflicting duplicate source ISINs, absent/changed securities or incompatible status/segment are missing, not arbitrarily chosen.
4. A BSE one-level **INDUSTRY** cell is not the full NSE four-tier macro/sector/industry/basic-industry. Its taxonomy must be reconciled separately, including financial, shipping, holding and multi-segment businesses. Report all 300 missing issuer industry flags.
5. If source includes **Mktcap**, this is neither verified historical NSE free-float capitalization nor current parent fully diluted share value. Validate definition and value against original dated balance-sheet/shares and BSE capital source before accepting any size factor.
6. Official source first retrieved October 21 **cannot** be backdated to the initial October 15 HG009 experiment. Source only for a separately preregistered future cohort after adequate coverage and other gates. Never rewrite the negative Oct15 H1 performance.
7. Market impact, margin of safety, shareholder action-adjusted total returns, historic momentum/beta, source complete financial regime and cost controls remain independent blockers. No buy recommendation or live capital.

## Acceptance

An archive receipt must show official original URL, actual first retrieval UTC, original raw SHA-256, exact 300 ISIN match coverage for all three 100-name arms and actual issuer **INDUSTRY** cells. An honest **HTTP 403/404** or BSE schema mismatch is evidence the route did not yet unlock classifications. A success still does **not** authorize a new 60/120/252-session after-cost alpha model until pre-entry industry coverage **>=90/arm and >=285/300**, true size/float, business accounting regimes, CAS, complete corporate actions and executable frictions are independently proved.

If verified BSE labels cover many of the missing 158, next work is semantic NSE-BSE taxonomy mapping with human-audited issuer segment source, **not** instant promotion to sector-neutral P&L.
