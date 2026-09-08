# H004-HR003 full-market denominator

Status: **historical reconstruction, not out-of-sample validation**

The contract was frozen before output inspection. This run defines the full liquid-market explosive-opportunity denominator and a price/volume-only baseline. It contains no accounting, filing, catalyst, valuation or news features.

```json
{
  "data_contract": {
    "discovery_liquidity": "INR 25 lakh <= median prior-20 traded value < INR 2 crore",
    "episode_label": "next-session-open max high over next 20 symbol sessions >= +25%",
    "market_source": "official NSE UDiFF daily bhavcopy",
    "momentum_score": "equal mean of daily cross-sectional percentile ranks: 5d return, 20d return, volume ratio",
    "primary_liquidity": "median prior-20 traded value >= INR 2 crore"
  },
  "decision_window": {
    "end": "2026-07-31",
    "start": "2025-10-01"
  },
  "discovery_episode_count": 1051,
  "experiment": "H004-HR003-FULL-MARKET-DENOMINATOR",
  "live_capital_allowed": false,
  "market_sessions_loaded": 331,
  "momentum_baselines": [
    {
      "episode_recall": 0.005198487712665407,
      "episode_recall_count": 11,
      "hit_count": 41,
      "median_close_20d_return_pct": -5.267625777934709,
      "median_lead_sessions_before_25pct": 0,
      "median_max_20d_return_pct": 10.18416255297089,
      "precision": 0.20098039215686275,
      "signal_count": 204,
      "top_n_per_day": 1
    },
    {
      "episode_recall": 0.013232514177693762,
      "episode_recall_count": 28,
      "hit_count": 69,
      "median_close_20d_return_pct": -4.73451732554167,
      "median_lead_sessions_before_25pct": 0.0,
      "median_max_20d_return_pct": 9.815414194937834,
      "precision": 0.16911764705882354,
      "signal_count": 408,
      "top_n_per_day": 2
    },
    {
      "episode_recall": 0.023156899810964082,
      "episode_recall_count": 49,
      "hit_count": 102,
      "median_close_20d_return_pct": -3.5707617032531114,
      "median_lead_sessions_before_25pct": 1,
      "median_max_20d_return_pct": 9.592500345925004,
      "precision": 0.16666666666666666,
      "signal_count": 612,
      "top_n_per_day": 3
    },
    {
      "episode_recall": 0.05387523629489603,
      "episode_recall_count": 114,
      "hit_count": 153,
      "median_close_20d_return_pct": -3.2218655089381096,
      "median_lead_sessions_before_25pct": 1.0,
      "median_max_20d_return_pct": 9.514872531638641,
      "precision": 0.15,
      "signal_count": 1020,
      "top_n_per_day": 5
    },
    {
      "episode_recall": 0.12145557655954631,
      "episode_recall_count": 257,
      "hit_count": 320,
      "median_close_20d_return_pct": -2.759195402298853,
      "median_lead_sessions_before_25pct": 1,
      "median_max_20d_return_pct": 9.341187285096709,
      "precision": 0.1568627450980392,
      "signal_count": 2040,
      "top_n_per_day": 10
    }
  ],
  "price_window": {
    "end": "2026-08-31",
    "start": "2025-05-01"
  },
  "primary_episode_count": 2116,
  "primary_episodes_by_quarter": {
    "2025-Q4": 279,
    "2026-Q1": 972,
    "2026-Q2": 648,
    "2026-Q3": 217
  },
  "primary_unique_symbols": 1070,
  "schema_version": 1,
  "status": "HISTORICAL_RECONSTRUCTION_NOT_OUT_OF_SAMPLE",
  "symbols_loaded": 2960,
  "top_symbols_by_episode_count": [
    [
      "KERNEX",
      7
    ],
    [
      "SKYGOLD",
      7
    ],
    [
      "AEROFLEX",
      6
    ],
    [
      "AVALON",
      6
    ],
    [
      "KMEW",
      6
    ],
    [
      "PRECWIRE",
      6
    ],
    [
      "RAIN",
      6
    ],
    [
      "ACUTAAS",
      6
    ],
    [
      "APOLLOPIPE",
      5
    ],
    [
      "BLISSGVS",
      5
    ],
    [
      "BLSE",
      5
    ],
    [
      "CUPID",
      5
    ],
    [
      "DREDGECORP",
      5
    ],
    [
      "FILATEX",
      5
    ],
    [
      "GRWRHITECH",
      5
    ],
    [
      "GENESYS",
      5
    ],
    [
      "INFOBEAN",
      5
    ],
    [
      "IOLCP",
      5
    ],
    [
      "KIRLOSENG",
      5
    ],
    [
      "MCLOUD",
      5
    ]
  ]
}
```
