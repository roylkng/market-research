from datetime import date, timedelta

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.alpha_delivery import DeliveryObservation
from marketlab.alpha_market import DailyEquityObservation
from marketlab.alpha_t004_prospective import (
    append_t004_decision,
    build_t004_current_feature_rows,
    build_t004_decision_artifact,
    new_t004_decision_ledger,
    validate_t004_decision_ledger,
)


def _market_row(day, close, *, symbol="TEST", isin="INE000000001"):
    prior = close / 1.001
    return DailyEquityObservation(
        session_date=day,
        symbol=symbol,
        isin=isin,
        open_price=prior,
        high_price=close * 1.01,
        low_price=prior * 0.99,
        close_price=close,
        previous_close=prior,
        volume=100_000,
        turnover_inr=30_000_000,
        trade_count=1_000,
    )


def _udiff_current(day):
    import csv
    import io
    import zipfile

    fields = [
        "TradDt",
        "Sgmt",
        "Src",
        "FinInstrmTp",
        "ISIN",
        "TckrSymb",
        "SctySrs",
        "OpnPric",
        "HghPric",
        "LwPric",
        "ClsPric",
        "PrvsClsgPric",
        "TtlTradgVol",
        "TtlTrfVal",
        "TtlNbOfTxsExctd",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "TradDt": day,
            "Sgmt": "CM",
            "Src": "NSE",
            "FinInstrmTp": "STK",
            "ISIN": "INE000000001",
            "TckrSymb": "TEST",
            "SctySrs": "EQ",
            "OpnPric": "100",
            "HghPric": "103",
            "LwPric": "99",
            "ClsPric": "102",
            "PrvsClsgPric": "100",
            "TtlTradgVol": "100000",
            "TtlTrfVal": "30000000",
            "TtlNbOfTxsExctd": "1000",
        }
    )
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        archive.writestr("bhav.csv", text.getvalue())
    return raw.getvalue()


def _delivery_current(day):
    import csv
    import io

    fields = [
        "SYMBOL",
        "SERIES",
        "DATE1",
        "AVG_PRICE",
        "TTL_TRD_QNTY",
        "TURNOVER_LACS",
        "NO_OF_TRADES",
        "DELIV_QTY",
        "DELIV_PER",
    ]
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=fields)
    writer.writeheader()
    writer.writerow(
        {
            "SYMBOL": "TEST",
            "SERIES": "EQ",
            "DATE1": day,
            "AVG_PRICE": "101",
            "TTL_TRD_QNTY": "100000",
            "TURNOVER_LACS": "300",
            "NO_OF_TRADES": "1000",
            "DELIV_QTY": "40000",
            "DELIV_PER": "40.00",
        }
    )
    return text.getvalue().encode()


def _history():
    start = date(2026, 7, 2)
    market = []
    close = 80.0
    for index in range(60):
        day = start + timedelta(days=index)
        close *= 1.001
        row = _market_row(day.isoformat(), close)
        market.append(
            {
                "session_date": day.isoformat(),
                "equities": [row.__dict__],
                "udiff_sha256": f"{index + 1:064x}",
            }
        )

    delivery = []
    for index, session in enumerate(market[-20:]):
        row = DeliveryObservation(
            session_date=session["session_date"],
            symbol="TEST",
            avg_price=90.0 + index,
            traded_qty=100_000,
            turnover_lacs=300.0,
            trade_count=1_000,
            delivery_qty=40_000 + index,
            delivery_pct=(40_000 + index) / 100_000,
        )
        delivery.append(
            {
                "session_date": session["session_date"],
                "source_quality": {
                    "status": "READY",
                    "complete_row_count": 1,
                    "violating_row_count": 0,
                    "max_abs_diff_pp": 0.0,
                    "tolerance_pp": 0.05,
                },
                "raw_sha256": f"{index + 101:064x}",
                "rows": [row.__dict__],
            }
        )
    return market, delivery


def test_t004_builds_frozen_27_feature_common_row():
    market, delivery = _history()
    rows, diagnostics = build_t004_current_feature_rows(
        prior_market_sessions=market,
        current_market_raw=_udiff_current("2026-09-30"),
        prior_delivery_sessions=delivery,
        current_delivery_raw=_delivery_current("30-Sep-2026"),
        session_date="2026-09-30",
        corporate_action_payload=[],
    )
    assert len(rows) == 1
    assert len(rows[0]["values"]) == 27
    assert all(value == pytest.approx(0.5) for value in rows[0]["values"].values())
    assert diagnostics["common_row_count"] == 1


def test_t004_prediction_must_be_sealed_after_scoring_but_before_cutoff(monkeypatch):
    rows = [
        {
            "symbol": f"S{index:03d}",
            "isin": f"INE{index:09d}",
            "values": {"x": 0.5},
        }
        for index in range(500)
    ]
    monkeypatch.setattr(
        "marketlab.alpha_t004_prospective.validate_frozen_t004_models",
        lambda artifact: None,
    )
    monkeypatch.setattr(
        "marketlab.alpha_t004_prospective.build_t004_current_feature_rows",
        lambda **kwargs: (
            rows,
            {
                "common_row_count": 500,
                "feature_rows_sha256": "f" * 64,
                "exclusions": {},
            },
        ),
    )
    monkeypatch.setattr(
        "marketlab.alpha_t004_prospective._score_model",
        lambda model, rows: [
            {
                "symbol": row["symbol"],
                "isin": row["isin"],
                "prediction": 0.1,
            }
            for row in rows
        ],
    )
    models = {
        "artifact_id": "AE001-T004-FROZEN-MODELS-v1",
        "artifact_sha256": "a" * 64,
        "base_model": {"model_sha256": "b" * 64},
        "augmented_model": {"model_sha256": "c" * 64},
    }
    attempt = {
        "session_date": "2026-09-30",
        "eligible_before_cutoff": True,
        "attempt_sha256": "d" * 64,
        "captured_at_utc": "2026-09-30T12:00:00+00:00",
    }
    with pytest.raises(AlphaContractError, match="missed decision cutoff"):
        build_t004_decision_artifact(
            session_date="2026-09-30",
            sc001_attempt=attempt,
            prior_market_sessions=[{"session_date": "2026-09-29"}] * 60,
            current_market_raw=b"x",
            prior_delivery_sessions=[{"session_date": "2026-09-29"}] * 20,
            current_delivery_raw=b"y",
            corporate_action_payload=[],
            corporate_action_raw=b"z",
            frozen_models=models,
            sealed_at_utc="2026-09-30T13:00:01+00:00",
        )


def test_t004_decision_ledger_is_append_only_and_unique_by_session():
    artifact = {
        "session_date": "2026-09-30",
        "artifact_sha256": "a" * 64,
        "sealed_at_utc": "2026-09-30T12:45:00+00:00",
        "common_row_count": 900,
        "sc001_attempt_sha256": "b" * 64,
        "base_model_sha256": "c" * 64,
        "augmented_model_sha256": "d" * 64,
        "outcomes_attached": False,
    }
    ledger = append_t004_decision(
        new_t004_decision_ledger(),
        decision_artifact=artifact,
        artifact_path=(
            "research/prospective/ae001-t004/decisions/"
            "2026-09-30-v1.json.gz"
        ),
    )
    validate_t004_decision_ledger(ledger)
    assert ledger["decision_count"] == 1
    with pytest.raises(AlphaContractError, match="already exists"):
        append_t004_decision(
            ledger,
            decision_artifact=artifact,
            artifact_path="duplicate",
        )
