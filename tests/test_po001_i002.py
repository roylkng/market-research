from marketlab.alpha import digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_model import ModelExample
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS
from marketlab.po001_i002 import run_po001_i002
from marketlab.rm001 import FACTOR_NAMES


def _definitions():
    return [
        {
            "name": definition.name,
            "family": definition.family,
            "version": definition.version,
            "description": definition.description,
            "lookback_sessions": definition.lookback_sessions,
            "availability_lag_sessions": definition.availability_lag_sessions,
        }
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]


def _feature_panel(count=20):
    definitions = _definitions()
    rows = []
    for index in range(count):
        rows.append(
            {
                "feature_session": "2026-08-31",
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "values": {
                    definition["name"]: (index + 1) / (count + 1)
                    for definition in definitions
                },
            }
        )
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-I002",
        "transform": "WITHIN_SESSION_TIE_AWARE_PERCENTILE_V1",
        "feature_definitions": definitions,
        "corporate_action_ledger_sha256": "a" * 64,
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _risk_state(count=20):
    rows = []
    for index in range(count):
        centered = 2 * ((index + 1) / (count + 1)) - 1
        rows.append(
            {
                "symbol": f"S{index:03d}",
                "isin": f"INE{index:09d}",
                "exposures": {
                    "MARKET_COMMON": 1.0,
                    "BETA60_RELATIVE": centered * 0.2,
                    "MOMENTUM20": centered,
                    "VOLATILITY60": -centered * 0.5,
                    "LIQUIDITY": centered * 0.3,
                },
                "idiosyncratic_variance_daily": 0.00001,
                "idiosyncratic_status": "OBSERVED",
            }
        )
    state = {
        "schema_version": 1,
        "model_id": "RM001-v1-DEVELOPMENT",
        "as_of_session": "2026-08-31",
        "factor_names": list(FACTOR_NAMES),
        "factor_covariance_daily": [
            [0.000001 if i == j else 0.0 for j in range(len(FACTOR_NAMES))]
            for i in range(len(FACTOR_NAMES))
        ],
        "rows": rows,
        "deferred_factors": {
            "SIZE": "POINT_IN_TIME_MARKET_CAP_SOURCE_NOT_FROZEN",
            "SECTOR": "POINT_IN_TIME_COMPANY_CLASSIFICATION_SOURCE_NOT_FROZEN",
        },
        "live_capital_allowed": False,
    }
    state["state_sha256"] = digest(state)
    return state


def _market_panel():
    panel = {
        "schema_version": 1,
        "panel_id": "TEST-MARKET",
        "sessions": [],
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _action_ledger():
    ledger = {
        "schema_version": 1,
        "ledger_id": "AE001-CORPORATE-ACTIONS-v1",
        "coverage_start_date": "2025-09-01",
        "coverage_end_date": "2026-08-31",
        "records": [],
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = digest(ledger)
    return ledger


def test_i002_purges_fold2_training_and_does_not_open_decision_outcome(
    monkeypatch,
):
    names = [
        definition.name
        for definition in [*PRICE_VOLUME_DEFINITIONS, *DELIVERY_DEFINITIONS]
    ]
    examples = []
    for index in range(120):
        examples.append(
            ModelExample(
                symbol=f"T{index:03d}",
                isin=f"INT{index:09d}",
                feature_session="2026-06-01",
                entry_session="2026-06-02",
                exit_session="2026-06-10",
                horizon_sessions=5,
                features={
                    name: (index + feature_index + 1) / 200.0
                    for feature_index, name in enumerate(names)
                },
                target_excess_return=(index - 60) / 10000.0,
            )
        )
    examples.append(
        ModelExample(
            symbol="LATE",
            isin="INELATE000001",
            feature_session="2026-06-29",
            entry_session="2026-06-30",
            exit_session="2026-07-06",
            horizon_sessions=5,
            features={name: 0.5 for name in names},
            target_excess_return=0.5,
        )
    )

    monkeypatch.setattr(
        "marketlab.po001_i002.build_action_safe_horizon_examples",
        lambda **kwargs: ({5: examples}, {}),
    )
    monkeypatch.setattr(
        "marketlab.po001_i002.MIN_COMMON_IDENTITIES",
        20,
    )
    monkeypatch.setattr(
        "marketlab.po001_i002.TOP_DECILE_SHARE",
        1.0,
    )
    monkeypatch.setattr(
        "marketlab.po001_i002._score_model",
        lambda model, rows: [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "prediction": 0.01 + index * 0.0005,
            }
            for index, row in enumerate(rows)
        ],
    )

    artifact = run_po001_i002(
        delivery_feature_panel=_feature_panel(),
        market_panel=_market_panel(),
        action_ledger=_action_ledger(),
        risk_state=_risk_state(),
    )

    assert artifact["realized_outcome_opened"] is False
    assert artifact["source_end_date"] == "2026-08-31"
    assert artifact["alpha_source"]["fold"] == 2
    assert (
        artifact["alpha_source"]["training_last_exit_session"]
        < artifact["alpha_source"]["validation_start_session"]
    )
    assert artifact["alpha_source"]["training_example_count"] == 120
    assert artifact["common_identity_count"] == 20
    assert artifact["interpretation_limits"][
        "post_decision_market_sources_acquired"
    ] is False
