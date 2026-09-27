from datetime import date

from marketlab.alpha_actions import (
    action_window_status,
    build_share_action_panel,
    validate_share_action_panel,
)


def _panel():
    payload = [
        {
            "symbol": "AAA",
            "series": "EQ",
            "subject": "Bonus 1:1",
            "exDate": "15-Jan-2026",
        },
        {
            "symbol": "BBB",
            "series": "EQ",
            "subject": "Dividend Rs 5",
            "exDate": "16-Jan-2026",
        },
        {
            "symbol": "CCC",
            "series": "EQ",
            "subject": "Stock Split From Rs 10 To Rs 2",
            "exDate": "bad-date",
        },
    ]
    return build_share_action_panel(
        payload,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        source_url="https://www.nseindia.com/api/corporates-corporateActions?x=1",
        raw_sha256="a" * 64,
    )


def test_share_action_panel_ignores_dividends_and_blocks_basis_changes():
    panel = _panel()
    validate_share_action_panel(panel)
    assert "AAA" in panel["actions_by_symbol"]
    assert "BBB" not in panel["actions_by_symbol"]
    assert panel["share_changing_record_count"] == 2

    status, blockers = action_window_status(
        panel,
        symbol="AAA",
        start_session="2026-01-01",
        end_session="2026-01-31",
    )
    assert status == "BLOCKED"
    assert blockers[0]["ex_date"] == "2026-01-15"


def test_action_on_first_lookback_session_does_not_cross_window():
    panel = build_share_action_panel(
        [
            {
                "symbol": "AAA",
                "series": "EQ",
                "subject": "Bonus 1:1",
                "exDate": "01-Jan-2026",
            }
        ],
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        source_url="https://www.nseindia.com/api/corporates-corporateActions?x=1",
        raw_sha256="b" * 64,
    )
    status, blockers = action_window_status(
        panel,
        symbol="AAA",
        start_session="2026-01-01",
        end_session="2026-01-31",
    )
    assert status == "READY"
    assert blockers == ()


def test_unresolved_share_action_fails_closed_for_symbol():
    panel = _panel()
    status, blockers = action_window_status(
        panel,
        symbol="CCC",
        start_session="2026-01-01",
        end_session="2026-01-31",
    )
    assert status == "UNRESOLVED"
    assert blockers == ()
