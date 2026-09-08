from __future__ import annotations

from marketlab.h003_identity_redaction import company_redaction_terms


def test_generic_vehicle_descriptor_is_not_a_standalone_alias() -> None:
    terms = company_redaction_terms(
        {"company_name": "Example Vehicles Limited"},
        "EXAMPLE",
    )
    assert "Example" in terms
    assert "Vehicles" not in terms


def test_generic_motor_descriptor_is_not_a_standalone_alias() -> None:
    terms = company_redaction_terms(
        {"company_name": "Example Motors Limited"},
        "EXAMPLE",
    )
    assert "Example" in terms
    assert "Motors" not in terms
