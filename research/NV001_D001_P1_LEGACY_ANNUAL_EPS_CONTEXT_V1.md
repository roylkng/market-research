# NV001-D001 P1 Legacy Annual EPS Context Amendment v1

Status: **FROZEN AFTER D001 SOURCE DIAGNOSTIC, BEFORE P1 RERUN**  
Frozen: 2026-10-04  
Return outcomes opened: no  
Portfolio eligibility: disabled  
Live capital: disabled

## Why this amendment exists

NV001-D001 opened no return outcomes and fitted no model, but failed the frozen
historical-P/E coverage thresholds.

Authoritative D001 evidence:

- workflow run: `37192612272`;
- artifact ID: `11300055624`;
- panel SHA-256:
  `82ecd09c3c49ed0c1f0256def9dfc36f22bf7d4965d1fd96baecceaf8d61fa88`;
- current trailing P/E coverage: 85/100;
- companies with >=3 historical P/E observations: 0;
- companies with all four historical P/E observations: 0.

The source artifact showed the failure is concentrated in FY23/FY24 legacy NSE annual
EPS parsing, not in current P/E construction.

## Observed legacy NSE convention

A source-only audit of the exact D001 filing bytes found **174 FY23/FY24 legacy annual
XBRL filings across 88 symbols**.

All 174 observations satisfy:

- an exact non-dimensional context ID `OneD` exists;
- an exact non-dimensional context ID `FourD` exists;
- the annual EPS concept appears in both contexts;
- `FourD` has `DateOfEndOfReportingPeriod` equal to the selected fiscal year end;
- `FourD` context end date equals the selected fiscal year end;
- filing metadata has explicit April 1 financial-year start and matching March 31 end.

The legacy taxonomy encodes:

- `OneD`: fourth-quarter EPS;
- `FourD`: full-year / four-quarter EPS.

The XML duration dates themselves are quarter-like for both contexts, so a generic
350-380 day duration test cannot recover the legacy annual value.

## Frozen P1 rule

### Integrated Filing source

For `NSE_INTEGRATED_FILING`, retain D001 unchanged:

- annual EPS must come from a non-dimensional 350-380 day duration context;
- context end must equal the selected fiscal-year endpoint.

### Legacy Financial Results source

For `NSE_LEGACY_FINANCIAL_RESULTS`, annual EPS may come only from exact context ID
`FourD` when all are true:

1. `FourD` exists and is non-dimensional;
2. `FourD` context end equals the selected period end;
3. explicit filing `DateOfEndOfReportingPeriod` for `FourD` equals the selected
   period end;
4. filing `DateOfStartOfFinancialYear` is exactly April 1 of the preceding calendar
   year;
5. filing `DateOfEndOfFinancialYear` equals the selected March 31 period end;
6. accounting basis matches the already-selected basis;
7. preferred/fallback basic-EPS concept order remains unchanged.

No maximum-EPS heuristic, context-name fuzzy matching, arithmetic annualization, or
quarter summation is permitted.

## Deliberately unchanged

P1 does not change:

- U001;
- FY23-FY26 annual endpoints;
- one-basis-across-history rule;
- post-publication price-anchor rule;
- legacy/UDiFF price sources;
- current valuation date;
- positive-EPS requirement;
- any D001 feasibility threshold.

P1 remains source feasibility only. Passing it permits only a separately frozen
normalized-valuation score design.
