from datetime import date

from marketlab.marketdata import audit_price_basis_actions


def test_price_basis_version_changes_when_holding_period_share_basis_changes():
    entry = audit_price_basis_actions(
        [], raw_payload=b"[]", symbol="TEST",
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 5),
    )
    exit_basis = audit_price_basis_actions(
        [{"symbol": "TEST", "subject": "Bonus 1:1", "exDate": "20-Oct-2026"}],
        raw_payload=b"bonus", symbol="TEST",
        start_date=date(2026, 10, 1), end_date=date(2026, 11, 2),
    )
    assert entry.status == "READY" and exit_basis.status == "READY"
    assert entry.version != exit_basis.version
