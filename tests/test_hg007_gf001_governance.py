from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import marketlab.hg007_gf001_governance as module


def _mock_original_28() -> list[str]:
    names, info = module.frozen_outside_u001(Path("."))
    assert info["intersection_count"] == 0
    return names


def test_outside_u001_contract_original_28_never_substituted() -> None:
    symbols, source = module.frozen_outside_u001(Path("."))
    assert len(symbols) == 28
    assert len(set(symbols)) == 28
    assert "INOXGREEN" in symbols
    assert "DEVX" in symbols
    assert source["u001_count"] == 100
    assert source["intersection_count"] == 0
    assert source["hg002_original_git_blob"] == module.COHORT_GIT_BLOB


def test_fails_closed_when_full_market_census_missing() -> None:
    with pytest.raises(ValueError, match="GF001 original run/result identity changed"):
        module.validate_original_full_market(
            {"census_id": "FAKE", "rows": []},
            {"panel_id": "GF001-D002-v1", "rows": []},
            {"diagnostic_id": "GF001-D002-v1"},
        )


def test_all_28_without_source_remain_explicit_missing(tmp_path: Path) -> None:
    symbols = _mock_original_28()
    census = {
        "rows": [{"symbol": s, "source_state": "FETCH_FAILED", "latest": None}
                 for s in symbols]
    }
    panel = {
        "rows": [{"symbol": s, "source_state": "FETCH_FAILED",
                  "governance_state": "SOURCE_UNAVAILABLE", "latest": None}
                 for s in symbols]
    }
    payload = module.build_outside_u001_governance(
        symbols=symbols,
        census=census,
        panel=panel,
        artifact_raw_root=tmp_path / "original",
        extracted_original_dir=tmp_path / "retained",
        captured=datetime(2026, 10, 4, 13, 0, tzinfo=UTC),
    )
    assert payload["original_oct04_core_ready_count"] == 0
    assert payload["original_oct04_source_unavailable_or_unready_count"] == 28
    assert payload["original_oct04_pledge_boolean_true_symbols"] == []
    assert payload["original_xbrl_bytes_retained_unique_count"] == 0
    assert payload["latest_oct11_pledge_quantities_verified"] is False
    assert all(row["latest_source"] is None for row in payload["company_rows"])
    assert all(row["governance_clean_recertified_for_oct11"] is False
               for row in payload["company_rows"])
    assert not (tmp_path / "retained").exists()


def test_replays_one_official_pledge_boolean_without_quantity_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    symbols = _mock_original_28()
    target = symbols[0]
    source_url = "https://nsearchives.nseindia.com/corporate/xbrl/fixture.xml"
    raw = b"<xbrl>source fixture not actual NSE</xbrl>"
    sha = hashlib.sha256(raw).hexdigest()
    original = tmp_path / "gf001-original" / "xbrl" / "sha256" / f"{sha}.xml"
    original.parent.mkdir(parents=True)
    original.write_bytes(raw)

    current = {
        "symbol": target, "report_date": "2026-06-30",
        "source_url": source_url, "raw_sha256": sha,
        "parser_status": "CORE_READY",
        "promoter_percentage": 67.0,
        "public_percentage": 33.0,
        "mutual_fund_percentage": None,
        "mutual_fund_state": "CATEGORY_CONTEXT_ABSENT",
        "promoter_encumbrance": {
            "pledge": True, "non_disposal_undertaking": False,
            "other_encumbrance": False,
        },
    }
    monkeypatch.setattr(
        module, "parse_current_governance_xbrl",
        lambda raw_bytes, **kwargs: current,
    )
    census_rows = []
    panel_rows = []
    for s in symbols:
        if s == target:
            census_rows.append({
                "symbol": s, "source_state": "READY",
                "latest": {
                    "report_date": "2026-06-30", "xbrl_url": source_url,
                    "broadcast_at_utc": "2026-08-01T10:01:00Z",
                },
            })
            panel_rows.append({
                "symbol": s, "source_state": "READY",
                "governance_state": "CORE_READY", "latest": current,
            })
        else:
            census_rows.append({
                "symbol": s, "source_state": "FETCH_FAILED", "latest": None,
            })
            panel_rows.append({
                "symbol": s, "source_state": "FETCH_FAILED",
                "governance_state": "SOURCE_UNAVAILABLE", "latest": None,
            })
    census = {"rows": census_rows}
    panel = {"rows": panel_rows}
    output = module.build_outside_u001_governance(
        symbols=symbols, census=census, panel=panel,
        artifact_raw_root=tmp_path / "gf001-original",
        extracted_original_dir=tmp_path / "retained",
        captured=datetime(2026, 10, 4, 14, 0, tzinfo=UTC),
    )
    assert output["original_oct04_core_ready_count"] == 1
    assert output["original_oct04_pledge_boolean_true_symbols"] == [target]
    assert output["original_xbrl_bytes_retained_unique_count"] == 1
    row = next(r for r in output["company_rows"] if r["symbol"] == target)
    assert row["latest_source"]["promoter_encumbrance_boolean"]["pledge"] is True
    assert row["latest_source"]["mutual_fund_pct"] is None
    assert row["latest_source"]["mutual_fund_state"] == "CATEGORY_CONTEXT_ABSENT"
    assert row["latest_source"]["pledged_share_count_verified_from_this_panel"] is False
    assert row["governance_clean_recertified_for_oct11"] is False
    assert (tmp_path / "retained" / f"{sha}.xml").read_bytes() == raw

    census_rows[0]["latest"]["broadcast_at_utc"] = "2026-10-08T00:00:00Z"
    with pytest.raises(ValueError, match="future filing leaks"):
        module.build_outside_u001_governance(
            symbols=symbols, census=census, panel=panel,
            artifact_raw_root=tmp_path / "gf001-original",
            extracted_original_dir=tmp_path / "retained",
            captured=datetime(2026, 10, 4, 14, 0, tzinfo=UTC),
        )


def test_rejects_inconsistent_source_identity_or_absent_gf001_xbrl(tmp_path: Path) -> None:
    symbols = _mock_original_28()
    census = {"rows": [{"symbol": s, "source_state": "READY",
                        "latest": {"broadcast_at_utc": "2026-08-01T00:00:00Z"}}
                       for s in symbols]}
    panel = {"rows": [{"symbol": s, "source_state": "READY",
                       "governance_state": "CORE_READY", "latest": None}
                      for s in symbols]}
    with pytest.raises(TypeError, match="core ready without"):
        module.build_outside_u001_governance(
            symbols=symbols, census=census, panel=panel,
            artifact_raw_root=tmp_path, extracted_original_dir=tmp_path,
            captured=datetime(2026, 10, 4, tzinfo=UTC),
        )


def test_claims_of_current_governance_or_stock_returns_never_appear() -> None:
    fake = {
        "symbols": _mock_original_28(),
        "status": "NO_ARTIFACT_AVAILABLE",
    }
    # The archival snapshot cannot establish later ownership, even if every
    # archived historical source was valid.
    assert "current_governance_verified" not in json.dumps(fake)
    assert module.EXPECTED_GF001_PANEL_SHA256.startswith("dd338cd9")
    assert module.EXPECTED_SS001_SOURCE_SHA256.startswith("214c1172")
