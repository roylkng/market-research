from __future__ import annotations

import csv
import io

import pytest

from marketlab import h022_historical_universe as historical


def _csv_bytes(symbols: list[str]) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(
        out,
        fieldnames=["Company Name", "Industry", "Symbol", "Series", "ISIN Code"],
        lineterminator="\n",
    )
    writer.writeheader()
    for index, symbol in enumerate(symbols):
        writer.writerow(
            {
                "Company Name": f"Company {symbol}",
                "Industry": "Industry",
                "Symbol": symbol,
                "Series": "EQ",
                "ISIN Code": f"INE{index:09d}",
            }
        )
    return out.getvalue().encode()


def _rule() -> dict:
    raw = """
schema_version: 1
id: H022-UH001
hypothesis_id: H022
status: FROZEN_HISTORICAL_UNIVERSE_RECONSTRUCTION
live_capital_allowed: false
anchor:
  source_url: https://example.test/nifty200.csv
  expected_as_of: 2026-08-31
  expected_constituent_count: 3
  required_columns: [Company Name, Industry, Symbol, Series, ISIN Code]
periodic_reconstitution:
  effective_date: 2026-03-30
  expected_excluded_count: 1
  expected_included_count: 1
  excluded:
    - {company_name: Old Co, symbol: OLD}
  included:
    - {company_name: New Co, symbol: NEW}
base_membership_intervals:
  - {interval_id: old, start: 2025-10-01, end: 2026-03-29}
  - {interval_id: new, start: 2026-03-30, end: 2026-09-06}
temporary_demerger_constituents:
  treatment: metadata_only
  events: []
ad_hoc_base_membership_audit:
  status: REQUIRED_BEFORE_EXPANDED_OUTCOME_EVALUATION
expanded_universe:
  expected_union_members_if_no_other_permanent_substitutions: 4
"""
    return historical.load_rule(raw)


def _u001() -> dict:
    return {"members": [{"symbol": "AAA"}, {"symbol": "BBB"}]}


def test_reverse_reconstruction_preserves_count_and_expands_union() -> None:
    document = historical.reconstruct_historical_membership(
        _csv_bytes(["AAA", "BBB", "NEW"]),
        rule=_rule(),
        current_u001_payload=_u001(),
    )
    historical.validate_reconstruction(document)

    assert document["anchor_member_count"] == 3
    assert document["pre_march_member_count"] == 3
    assert document["expanded_union_member_count"] == 4
    assert document["membership_intervals"][0]["symbols"] == ["AAA", "BBB", "OLD"]
    assert document["membership_intervals"][1]["symbols"] == ["AAA", "BBB", "NEW"]
    assert document["expanded_union_additional_vs_current_u001_symbols"] == ["NEW", "OLD"]
    assert document["historical_u001_reconstructed"] is False
    assert document["outcome_data_attached"] is False


def test_included_symbol_must_exist_in_anchor() -> None:
    with pytest.raises(historical.HistoricalUniverseError, match="included symbols missing"):
        historical.reconstruct_historical_membership(
            _csv_bytes(["AAA", "BBB", "CCC"]),
            rule=_rule(),
            current_u001_payload=_u001(),
        )


def test_excluded_symbol_must_not_remain_in_anchor() -> None:
    with pytest.raises(historical.HistoricalUniverseError, match="excluded symbols unexpectedly remain"):
        historical.reconstruct_historical_membership(
            _csv_bytes(["AAA", "OLD", "NEW"]),
            rule=_rule(),
            current_u001_payload={"members": [{"symbol": "AAA"}]},
        )


def test_current_u001_must_be_subset_of_anchor() -> None:
    with pytest.raises(historical.HistoricalUniverseError, match="outside Nifty 200 anchor"):
        historical.reconstruct_historical_membership(
            _csv_bytes(["AAA", "BBB", "NEW"]),
            rule=_rule(),
            current_u001_payload={"members": [{"symbol": "ZZZ"}]},
        )


def test_reconstruction_hash_detects_mutation() -> None:
    document = historical.reconstruct_historical_membership(
        _csv_bytes(["AAA", "BBB", "NEW"]),
        rule=_rule(),
        current_u001_payload=_u001(),
    )
    document["expanded_union_member_count"] = 99
    with pytest.raises(historical.HistoricalUniverseError, match="hash mismatch"):
        historical.validate_reconstruction(document)
