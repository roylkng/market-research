from __future__ import annotations

import io
import zipfile
from datetime import date

from marketlab.h024_historical import (
    H024HistoricalError,
    build_frozen_sessions,
    classify_primary,
    horizon_session,
    is_revision_blocked,
    parse_share_action_audit,
    parse_udiff_candidate_bars,
    planned_entry_session,
    purchase_value_bucket,
)


def _udiff_zip(rows: list[str]) -> bytes:
    header = (
        "TradDt,Sgmt,Src,FinInstrmTp,ISIN,TckrSymb,SctySrs,OpnPric,ClsPric,TtlTrfVal\n"
    )
    body = header + "\n".join(rows) + "\n"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("bhav.csv", body)
    return out.getvalue()


def test_h024_same_calendar_day_is_never_entry() -> None:
    sessions = build_frozen_sessions(
        start_date=date(2026, 5, 4), end_date=date(2026, 5, 6)
    )
    result = planned_entry_session("04-May-2026 08:00:00", sessions)
    assert result is not None
    index, session = result
    assert index == 1
    assert session.session_date == "2026-05-05"


def test_h024_weekend_disclosure_enters_next_session() -> None:
    sessions = build_frozen_sessions(
        start_date=date(2026, 5, 1), end_date=date(2026, 5, 5)
    )
    result = planned_entry_session("03-May-2026 02:39:51", sessions)
    assert result is not None
    _, session = result
    assert session.session_date == "2026-05-04"


def test_h024_horizon_counts_entry_as_session_one() -> None:
    sessions = build_frozen_sessions(
        start_date=date(2026, 1, 1), end_date=date(2026, 9, 15)
    )
    entry_index = 80
    assert horizon_session(sessions, entry_index=entry_index, horizon=20) == sessions[99]
    assert horizon_session(sessions, entry_index=entry_index, horizon=60) == sessions[139]
    assert horizon_session(sessions, entry_index=entry_index, horizon=120) is None


def test_h024_revision_between_original_and_entry_blocks() -> None:
    sessions = build_frozen_sessions(
        start_date=date(2026, 5, 4), end_date=date(2026, 5, 6)
    )
    _, entry = planned_entry_session("04-May-2026 19:00:00", sessions) or (None, None)
    assert entry is not None
    candidate = {
        "symbol": "ABC",
        "exchange_disseminated_at_ist": "04-May-2026 19:00:00",
    }
    revisions = [
        {
            "symbol": "ABC",
            "source_id": "rev-1",
            "exchange_disseminated_at_utc": "2026-05-05T02:00:00+00:00",
        }
    ]
    blocked, blockers = is_revision_blocked(
        candidate, revisions=revisions, entry_session=entry
    )
    assert blocked is True
    assert blockers == ["rev-1"]


def test_h024_revision_after_entry_does_not_block() -> None:
    sessions = build_frozen_sessions(
        start_date=date(2026, 5, 4), end_date=date(2026, 5, 6)
    )
    _, entry = planned_entry_session("04-May-2026 19:00:00", sessions) or (None, None)
    assert entry is not None
    candidate = {
        "symbol": "ABC",
        "exchange_disseminated_at_ist": "04-May-2026 19:00:00",
    }
    revisions = [
        {
            "symbol": "ABC",
            "source_id": "rev-1",
            "exchange_disseminated_at_utc": "2026-05-05T05:00:00+00:00",
        }
    ]
    blocked, blockers = is_revision_blocked(
        candidate, revisions=revisions, entry_session=entry
    )
    assert blocked is False
    assert blockers == []


def test_h024_udiff_parser_requires_stk_eq_and_turnover() -> None:
    raw = _udiff_zip(
        [
            "2026-05-04,CM,NSE,STK,INE000A01001,ABC,EQ,100,105,25000000",
            "2026-05-04,CM,NSE,STK,INE000A01002,XYZ,BE,50,51,99999999",
        ]
    )
    bars = parse_udiff_candidate_bars(
        raw, session_date=date(2026, 5, 4), symbols={"ABC", "XYZ"}
    )
    assert sorted(bars) == ["ABC"]
    assert bars["ABC"]["isin"] == "INE000A01001"
    assert bars["ABC"]["traded_value_inr"] == 25_000_000.0


def test_h024_udiff_duplicate_eq_row_fails_closed() -> None:
    raw = _udiff_zip(
        [
            "2026-05-04,CM,NSE,STK,INE000A01001,ABC,EQ,100,105,25000000",
            "2026-05-04,CM,NSE,STK,INE000A01001,ABC,EQ,101,106,26000000",
        ]
    )
    try:
        parse_udiff_candidate_bars(
            raw, session_date=date(2026, 5, 4), symbols={"ABC"}
        )
    except H024HistoricalError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate UDiFF row must fail closed")


def test_h024_corporate_action_audit_blocks_share_changing_subjects_only() -> None:
    payload = [
        {"symbol": "ABC", "subject": "Bonus 1:1", "exDate": "12-May-2026"},
        {"symbol": "ABC", "subject": "Dividend Rs 2", "exDate": "20-May-2026"},
    ]
    audit = parse_share_action_audit(payload, symbol="ABC")
    assert audit["status"] == "READY"
    assert audit["actions"] == [
        {"ex_date": "2026-05-12", "subject": "Bonus 1:1"}
    ]


def test_h024_purchase_value_buckets_are_fixed() -> None:
    assert purchase_value_bucket(9_999_999) == "<1cr"
    assert purchase_value_bucket(10_000_000) == "1-10cr"
    assert purchase_value_bucket(100_000_000) == "10-100cr"
    assert purchase_value_bucket(1_000_000_000) == ">=100cr"


def test_h024_classification_requires_coverage_before_strength() -> None:
    primary = {
        "mature_event_count": 99,
        "complete_count": 99,
        "complete_symbol_count": 70,
        "complete_share_of_mature": 1.0,
        "mean_excess_pp": 8.0,
        "median_excess_pp": 4.0,
        "benchmark_beat_rate": 0.70,
        "cluster_bootstrap_ci_95_low_pp": 2.0,
        "robustness": {
            "first_event_per_symbol": {"mean_excess_pp": 5.0},
            "non_overlapping_60": {"mean_excess_pp": 5.0},
        },
    }
    assert classify_primary(primary) == "INSUFFICIENT_COVERAGE"


def test_h024_classification_strong_requires_positive_robustness() -> None:
    primary = {
        "mature_event_count": 120,
        "complete_count": 110,
        "complete_symbol_count": 60,
        "complete_share_of_mature": 110 / 120,
        "mean_excess_pp": 5.0,
        "median_excess_pp": 2.0,
        "benchmark_beat_rate": 0.60,
        "cluster_bootstrap_ci_95_low_pp": 1.0,
        "robustness": {
            "first_event_per_symbol": {"mean_excess_pp": 3.0},
            "non_overlapping_60": {"mean_excess_pp": -0.1},
        },
    }
    assert classify_primary(primary) == "INCONCLUSIVE"
