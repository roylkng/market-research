from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import acquire_hg007_sambhv_original as module


def _bytes() -> bytes:
    return b"%PDF-1.7\n" + b"X" * 130000 + b"\n%%EOF\n"


def _pages() -> list[str]:
    pages = ["Investor content" * 50 for _ in range(43)]
    pages[0] = (
        "Sambhv Steel Tubes Limited, to the NSE  August 03, 2026. "
        "Quarter ending June 30 2026"
    )
    pages[8] = (
        "Future Roadmap Vision 2030. 1.2 MMTPA growth. "
        "Phase-I: 0.36 MMTPA Stainless steel coils with estimated "
        "CAPEX INR 8,100 Million, commissioning by Q4FY27. "
        "Setting up round-the-clock 25 MW Power Plant at Kesda "
        "in Phase-I with estimated CAPEX INR 1,250 Million, "
        "targeted for commissioning by Q4FY27."
    )
    return pages


def test_distinct_steel_and_captive_power_capex_proven_only_as_issuer_statement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "_pages", lambda raw: _pages())
    src = module.verify_original_issuer_roadmap(_bytes())
    assert src["page_count"] == 43
    assert src["roadmap_page_number"] == 9
    assert src["source_declared_steel_capacity_mmtpa"] == 0.36
    assert src["source_declared_steel_capex_inr_crore"] == 810
    assert src["source_declared_power_capacity_mw"] == 25
    assert src["source_declared_power_capex_inr_crore"] == 125
    assert src["both_stated_target_commissioning"] == "Q4FY27"
    assert src["power_plant_is_economically_required_for_steel_ebitda_verified"] is False
    assert src["both_capex_budgets_proven_fully_funded_or_spent"] is False


def test_stale_generic_filing_or_missing_power_capex_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = _pages()
    bad[0] = bad[0].replace("August 03, 2026", "November 03, 2026")
    monkeypatch.setattr(module, "_pages", lambda raw: bad)
    with pytest.raises(ValueError, match="issuer/date mismatch"):
        module.verify_original_issuer_roadmap(_bytes())

    bad = _pages()
    bad[8] = bad[8].replace("1,250", "1,050")
    monkeypatch.setattr(module, "_pages", lambda raw: bad)
    with pytest.raises(ValueError, match="1,250"):
        module.verify_original_issuer_roadmap(_bytes())


def test_403_denial_is_recorded_and_not_evaded(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class Response:
        status_code = 403
        content = b"Forbidden"
        url = module.ORIGINAL_URL

    def get(url: str, **kwargs: object) -> Response:
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(module.requests, "get", get)
    packet, raw = module.acquire_sambhv_original(attempts=3, sleep_seconds=0)
    assert raw is None
    assert packet["status"] == "ACCESS_BLOCKED"
    assert packet["raw_sha256"] is None
    assert packet["live_capital_allowed"] is False
    assert calls == [(module.ORIGINAL_URL, calls[0][1])]
    assert calls[0][1]["allow_redirects"] is False


def test_http200_html_not_accepted_as_official_investor_presentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        content = b"<html>Current quarter login</html>"
        url = module.ORIGINAL_URL

    monkeypatch.setattr(module.requests, "get", lambda *a, **kw: Response())
    packet, raw = module.acquire_sambhv_original(attempts=1)
    assert packet["status"] == "INVALID_SOURCE"
    assert raw is None


def test_sha_and_original_source_retention_never_promote_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(module, "_pages", lambda raw: _pages())

    class Response:
        status_code = 200
        content = _bytes()
        url = module.ORIGINAL_URL

    monkeypatch.setattr(module.requests, "get", lambda *a, **kw: Response())
    packet, raw = module.acquire_sambhv_original(attempts=1)
    assert raw is not None
    assert packet["status"] == "ORIGINAL_ISSUER_PDF_BYTES_AND_ROADMAP_IDENTITY_VERIFIED"
    assert packet["steel_power_budget_aggregation_authorized"] is False
    assert packet["steel_phase_1_commissioning_verified"] is False
    assert packet["power_phase_1_commissioning_verified"] is False
    assert packet["stock_target_or_expected_return_calculated"] is False
    module.save_original(tmp_path, packet, raw)
    original = tmp_path / "raw" / "sha256" / (packet["raw_sha256"]+".pdf")
    assert original.read_bytes() == _bytes()
    assert json.loads((tmp_path/"source-receipt-v1.json").read_text()) == packet
    module.save_original(tmp_path, packet, raw)
    modified = dict(packet, raw_sha256="0"*64)
    with pytest.raises(ValueError, match="raw PDF/evidence disagree"):
        module.save_original(tmp_path, modified, raw)
    assert hashlib.sha256(original.read_bytes()).hexdigest() == packet["raw_sha256"]


def test_retry_bounds_reject_invalid_settings() -> None:
    with pytest.raises(ValueError, match="retry count"):
        module.acquire_sambhv_original(attempts=5)
    with pytest.raises(ValueError, match="bounded source retry delay"):
        module.acquire_sambhv_original(attempts=1, sleep_seconds=-1)
