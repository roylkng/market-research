# H004-HR002 earnings subengine replay v2

Status: **historical reconstruction, not out-of-sample validation**

V1 was discarded before interpretation because its parser assumed the prior-year comparison was embedded in the current XBRL and misread display rounding as storage units. V2 compares two original NSE XBRL filings and treats XBRL numeric values as actual INR.

This is the earnings-inflection subengine only. Corporate-catalyst and turnaround-only anchors, delivery-volume confirmation, sector-relative confirmation, a full-market momentum baseline, and Nifty 500 excess-return evaluation remain outside this subreplay.

```json
{
  "by_calendar_quarter": {
    "2025-Q4": {
      "events": 882,
      "future_explosive": 18,
      "stage2_hits": 0,
      "stage2_precision": 0.0,
      "stage2_recall": 0.0,
      "stage2_signals": 26
    },
    "2026-Q1": {
      "events": 981,
      "future_explosive": 44,
      "stage2_hits": 3,
      "stage2_precision": 0.08333333333333333,
      "stage2_recall": 0.09090909090909091,
      "stage2_signals": 36
    },
    "2026-Q2": {
      "events": 5,
      "future_explosive": 1,
      "stage2_hits": 0,
      "stage2_precision": 0.0,
      "stage2_recall": 0.0,
      "stage2_signals": 1
    },
    "2026-Q3": {
      "events": 353,
      "future_explosive": 17,
      "stage2_hits": 1,
      "stage2_precision": 0.047619047619047616,
      "stage2_recall": 0.11764705882352941,
      "stage2_signals": 21
    }
  },
  "counts": {
    "future_explosive_result_events": 80,
    "primary_evaluable_events": 2221,
    "result_event_tape_baseline_hits": 32,
    "result_event_tape_baseline_signals": 1006,
    "stage1_signals": 172,
    "stage2_hits": 4,
    "stage2_signals": 84,
    "strict_quality_stage2_hits": 3,
    "strict_quality_stage2_signals": 73
  },
  "coverage": {
    "below_discovery_liquidity": 1237,
    "current_filings": 7567,
    "current_xbrl_not_quarterly_or_unparseable": 345,
    "financially_evaluable_events": 3023,
    "insufficient_forward_price_history": 40,
    "insufficient_price_history": 336,
    "market_evaluable_events": 5189,
    "missing_price_symbol": 242,
    "missing_prior_year_filing": 1810,
    "missing_symbol_on_decision_session": 523,
    "prior_period_mismatch": 2,
    "prior_xbrl_fetch_failure": 1,
    "prior_xbrl_not_quarterly_or_unparseable": 8
  },
  "data_contract": {
    "current_financials": "original NSE Integrated Filing Financials XBRL",
    "market_data": "official NSE UDiFF daily bhavcopy",
    "pre_event_price_policy": "last close observable before filing; intraday filings use prior-session close proxy",
    "prior_financials": "same-basis same-quarter original NSE Integrated or legacy XBRL",
    "xbrl_units": "actual INR, normalized only for display PAT crore"
  },
  "event_window": {
    "end": "2026-07-31",
    "start": "2025-10-01"
  },
  "experiment": "H004-HR002-EARNINGS-SUBENGINE-V2",
  "live_capital_allowed": false,
  "metrics": {
    "median_lead_sessions_to_25pct": 11.5,
    "median_stage2_close_20d_return_pct": -0.8097993884960575,
    "median_stage2_max_20d_return_pct": 5.170149855761408,
    "result_event_tape_baseline_precision": 0.03180914512922465,
    "result_event_tape_baseline_recall": 0.6125,
    "stage1_recall_of_future_explosive_result_events": 0.1,
    "stage2_precision": 0.047619047619047616,
    "stage2_recall_of_future_explosive_result_events": 0.075,
    "strict_quality_stage2_precision": 0.0410958904109589
  },
  "miss_taxonomy": {
    "NO_EARNINGS_INFLECTION": 56,
    "NO_STAGE2_TRIGGER": 2,
    "PRE_MOMENTUM_RULE": 16
  },
  "price_window": {
    "end": "2026-08-31",
    "start": "2025-05-01"
  },
  "schema_version": 2,
  "stage1_valid_sessions": 10,
  "status": "HISTORICAL_RECONSTRUCTION_NOT_OUT_OF_SAMPLE"
}
```

The full H004 promotion gate remains closed unless the complete historical reconstruction and frozen prospective cohorts satisfy the predeclared requirements.
