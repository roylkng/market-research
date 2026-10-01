import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_delivery import DELIVERY_DEFINITIONS
from marketlab.alpha_futures import FUTURES_DEFINITIONS
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_options import (
    OPTIONS_DEFINITIONS,
    acquire_historical_options_panel,
    augment_feature_panel_with_options,
    options_features,
)
from marketlab.alpha_options_source import OptionContractObservation
from marketlab.alpha_snapshot import PRICE_VOLUME_DEFINITIONS


def _contract(
    *,
    strike,
    option_type,
    settlement,
    oi,
    change_oi,
    volume,
    expiry="2026-10-27",
    symbol="TEST",
):
    return OptionContractObservation(
        session_date="2026-09-25",
        symbol=symbol,
        financial_instrument_id=f"{strike}-{option_type}",
        expiry_date=expiry,
        strike_price=float(strike),
        option_type=option_type,
        settlement_price=float(settlement),
        previous_close=float(settlement),
        underlying_price=100.0,
        open_interest=float(oi),
        change_in_open_interest=float(change_oi),
        traded_contracts=float(volume),
        transferred_value_inr=100_000.0,
        trade_count=50.0,
        board_lot=100.0,
    )


def _cash():
    return DailyEquityObservation(
        session_date="2026-09-25",
        symbol="TEST",
        isin="INE000000001",
        open_price=99.0,
        high_price=102.0,
        low_price=98.0,
        close_price=100.0,
        previous_close=99.0,
        volume=100_000.0,
        turnover_inr=10_000_000.0,
        trade_count=1_000.0,
    )


def _surface(*, zero_volume=False):
    rows = []
    for strike, call_premium, put_premium in (
        (90, 11.0, 1.0),
        (100, 5.0, 4.0),
        (110, 1.0, 10.0),
    ):
        volume_call = 0 if zero_volume else 100 + strike
        volume_put = 0 if zero_volume else 200 + strike
        rows.extend(
            [
                _contract(
                    strike=strike,
                    option_type="CE",
                    settlement=call_premium,
                    oi=1_000 + strike,
                    change_oi=100,
                    volume=volume_call,
                ),
                _contract(
                    strike=strike,
                    option_type="PE",
                    settlement=put_premium,
                    oi=2_000 + strike,
                    change_oi=200,
                    volume=volume_put,
                ),
            ]
        )
    return rows


def test_t009_option_features_follow_frozen_paired_surface_formulas():
    features = options_features(
        _surface(),
        market_current=_cash(),
    )
    assert set(features) == {
        definition.name for definition in OPTIONS_DEFINITIONS
    }
    assert features["opt_nearest_abs_moneyness"] == pytest.approx(0.0)
    assert features["opt_atm_straddle_fraction"] == pytest.approx(0.09)
    assert features[
        "opt_atm_put_call_premium_imbalance"
    ] == pytest.approx(-1.0 / 9.0)

    call_oi = sum(1_000 + strike for strike in (90, 100, 110))
    put_oi = sum(2_000 + strike for strike in (90, 100, 110))
    assert features["opt_paired_put_call_oi_imbalance"] == pytest.approx(
        (put_oi - call_oi) / (put_oi + call_oi)
    )
    assert features[
        "opt_paired_put_call_change_oi_imbalance"
    ] == pytest.approx(1.0 / 3.0)
    assert features["opt_near_atm_oi_share"] == pytest.approx(
        ((1_000 + 100) + (2_000 + 100)) / (call_oi + put_oi)
    )


def test_t009_zero_volume_conventions_are_frozen_zero():
    features = options_features(
        _surface(zero_volume=True),
        market_current=_cash(),
    )
    assert features["opt_paired_put_call_volume_imbalance"] == 0.0
    assert features["opt_near_atm_volume_share"] == 0.0


def test_t009_rejects_nonpositive_reconstructed_prior_oi():
    rows = _surface()
    rows = [
        OptionContractObservation(
            **{
                **row.__dict__,
                "change_in_open_interest": row.open_interest,
            }
        )
        for row in rows
    ]
    with pytest.raises(AlphaContractError, match="prior OI"):
        options_features(rows, market_current=_cash())


def test_t009_requires_three_paired_strikes():
    rows = [
        row
        for row in _surface()
        if row.strike_price in {90.0, 100.0}
    ]
    with pytest.raises(AlphaContractError, match="three paired"):
        options_features(rows, market_current=_cash())


def _base_definitions():
    return [
        *[
            {
                "name": definition.name,
                "family": definition.family,
                "version": definition.version,
                "description": definition.description,
                "lookback_sessions": definition.lookback_sessions,
                "availability_lag_sessions": definition.availability_lag_sessions,
            }
            for definition in [
                *PRICE_VOLUME_DEFINITIONS,
                *DELIVERY_DEFINITIONS,
                *FUTURES_DEFINITIONS,
            ]
        ],
    ]


def test_t009_augmentation_keeps_exact_identity_and_builds_47_features():
    market = {
        "schema_version": 1,
        "panel_id": "MARKET",
        "sessions": [
            {
                "session_date": "2026-09-25",
                "equities": [_cash().__dict__],
            }
        ],
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)

    definitions = _base_definitions()
    base_values = {
        row["name"]: 0.5
        for row in definitions
    }
    base = {
        "schema_version": 1,
        "panel_id": "T005-FULL37",
        "feature_definitions": definitions,
        "feature_set_sha256": digest(
            sorted(definitions, key=lambda row: row["name"])
        ),
        "sessions": [
            {
                "session_date": "2026-09-25",
                "eligible_count": 1,
                "universe_sha256": "u" * 64,
            }
        ],
        "rows": [
            {
                "feature_session": "2026-09-25",
                "decision_timestamp": "2026-09-25T18:30:00+05:30",
                "symbol": "TEST",
                "isin": "INE000000001",
                "universe_sha256": "u" * 64,
                "feature_set_sha256": "x" * 64,
                "values": base_values,
                "known_at": "2026-09-25T18:00:00+05:30",
                "outcomes_attached": False,
            }
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    base["panel_sha256"] = digest(base)

    options = {
        "schema_version": 1,
        "panel_id": "AE001-HISTORICAL-STOCK-OPTIONS-D006-v1",
        "source_hashes_sha256": "s" * 64,
        "sessions": [
            {
                "session_date": "2026-09-25",
                "status": "READY",
                "raw_sha256": "r" * 64,
                "rows": [row.__dict__ for row in _surface()],
            }
        ],
        "live_capital_allowed": False,
    }
    options["panel_sha256"] = digest(options)

    augmented = augment_feature_panel_with_options(
        feature_panel=base,
        market_panel=market,
        options_panel=options,
    )
    assert augmented["feature_row_count"] == 1
    assert len(augmented["rows"][0]["values"]) == 47
    assert augmented["rows"][0]["isin"] == "INE000000001"
    assert augmented["base_feature_panel_sha256"] == base["panel_sha256"]
    assert augmented["options_panel_sha256"] == options["panel_sha256"]


def test_t009_augmentation_excludes_symbol_without_exact_cash_identity():
    market = {
        "schema_version": 1,
        "sessions": [
            {
                "session_date": "2026-09-25",
                "equities": [
                    {
                        **_cash().__dict__,
                        "isin": "INE999999999",
                    }
                ],
            }
        ],
        "live_capital_allowed": False,
    }
    market["panel_sha256"] = digest(market)
    definitions = _base_definitions()
    base = {
        "feature_definitions": definitions,
        "rows": [
            {
                "feature_session": "2026-09-25",
                "symbol": "TEST",
                "isin": "INE000000001",
                "values": {row["name"]: 0.5 for row in definitions},
            }
        ],
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    base["panel_sha256"] = digest(base)
    options = {
        "source_hashes_sha256": "s" * 64,
        "sessions": [
            {
                "session_date": "2026-09-25",
                "status": "READY",
                "raw_sha256": "r" * 64,
                "rows": [row.__dict__ for row in _surface()],
            }
        ],
        "live_capital_allowed": False,
    }
    options["panel_sha256"] = digest(options)

    augmented = augment_feature_panel_with_options(
        feature_panel=base,
        market_panel=market,
        options_panel=options,
    )
    assert augmented["feature_row_count"] == 0
    assert augmented["exclusion_counts"][
        "CASH_IDENTITY_MISMATCH"
    ] == 1
