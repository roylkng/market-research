"""P034 source-only NSE all-listed-security master original gzip feasibility."""

from __future__ import annotations

import copy
import csv
import functools
import gzip
import hashlib
import io
import json
from pathlib import Path

import pytest

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs
from marketlab.hg009_p034_mii_security import (
    SOURCE_URL,
    _column,
    _frozen,
    analyze_original,
    archive,
    replay_originals,
)

ROOT = Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def _sample_source() -> bytes:
    original, selected = load_hg009_inputs(ROOT)
    controls = json.loads((
        ROOT / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    members = [(row["symbol"], row["isin"]) for row in selected["selected"]]
    for arm in ("ONE_LANE", "ZERO_LANE"):
        members.extend(
            (row["symbol"], row["isin"]) for row in controls["controls"][arm]
        )
    assert len(members) == 300
    assert original["identity_count"] == 2319
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "Symbol", "ISIN", "Series", "IssuedCapital",
        "SecurityStatus", "AdditionalSourceField",
    ])
    writer.writeheader()
    for i, (symbol, isin) in enumerate(members):
        marker = "".join(
            hashlib.sha256(f"p034-{i}-{j}".encode()).hexdigest()
            for j in range(7)
        )
        writer.writerow({
            "Symbol": symbol,
            "ISIN": isin,
            "Series": "EQ",
            "IssuedCapital": "10000000",
            "SecurityStatus": "2",
            "AdditionalSourceField": marker,
        })
    for i in range(2800):
        marker = "".join(
            hashlib.sha256(f"p034-dummy-{i}-{j}".encode()).hexdigest()
            for j in range(7)
        )
        writer.writerow({
            "Symbol": f"OTHER{i:05d}",
            "ISIN": f"INE{i:09d}",
            "Series": "EQ",
            "IssuedCapital": "10000000",
            "SecurityStatus": "2",
            "AdditionalSourceField": marker,
        })
    return gzip.compress(output.getvalue().encode(), mtime=0)


def test_300_source_identity_joins_do_not_invent_four_tier_sector_or_float():
    src = _sample_source()
    assert len(src) >= 300_000
    j = analyze_original(
        root=ROOT,
        original_gzip=src,
        first_observed_at_utc="2026-10-21T11:15:00Z",
    )
    assert j["official_source_url"] == SOURCE_URL
    assert j["original_instrument_row_count"] == 3100
    assert j["exact_symbol_isin_count"] == 300
    assert sum(
        row["exact_source_matches"]
        for row in j["exact_identity_coverage_by_arm"].values()
    ) == 300
    assert j["published_column_names_that_look_like_sector"] == []
    assert j["published_column_names_that_look_like_float"] == []
    assert "IssuedCapital" in j[
        "published_column_names_that_look_like_trading_status"
    ]
    assert j["NSE_master_issued_capital_is_current_fully_diluted_float"] is False
    assert j["new_prospective_industry_model_authorized"] is False
    assert j["original_future_price_labels_opened"] is False
    assert j["live_capital_allowed"] is False
    assert len(j["original_source_company_states"]) == 300
    assert all(
        row["verified_sector"] is None
        and row["expected_alpha"] is None
        for row in j["original_source_company_states"]
    )


def test_300_company_exact_join_rejects_relabelled_isin_and_duplicate_rows():
    raw = gzip.decompress(_sample_source())
    frozen = _frozen(ROOT)
    symbol, identity = next(iter(frozen.items()))
    wrong = raw.replace(
        f"{symbol},{identity['isin']},EQ".encode(),
        f"{symbol},INE999999999,EQ".encode(),
        1,
    )
    j = analyze_original(
        root=ROOT,
        original_gzip=gzip.compress(wrong, mtime=0),
        first_observed_at_utc="2026-10-21T11:15:00Z",
    )
    row = next(x for x in j["original_source_company_states"] if x["symbol"] == symbol)
    assert row["state"] == "BLOCKED_ORIGINAL_SOURCE_ISIN_OR_SERIES_DIFFER"
    assert j["exact_symbol_isin_count"] == 299

    # Duplicated original rows are never silently treated as two good sources.
    lines = raw.splitlines(keepends=True)
    duplicate = next(
        x for x in lines
        if x.startswith(f"{symbol},{identity['isin']},EQ".encode())
    )
    altered = b"".join(lines + [duplicate])
    j = analyze_original(
        root=ROOT, original_gzip=gzip.compress(altered, mtime=0),
        first_observed_at_utc="2026-10-21T11:15:00Z",
    )
    row = next(x for x in j["original_source_company_states"] if x["symbol"] == symbol)
    assert row["state"] == "BLOCKED_DUPLICATE_EXACT_INSTRUMENT"
    assert j["exact_symbol_isin_count"] == 299


def test_misidentified_schema_is_not_promoted_to_valid_stock_classification():
    raw = gzip.decompress(_sample_source())
    no_isin = raw.replace(b"Symbol,ISIN,Series,", b"Symbol,UnknownId,Series,", 1)
    j = analyze_original(
        root=ROOT, original_gzip=gzip.compress(no_isin, mtime=0),
        first_observed_at_utc="2026-10-21T11:15:00Z",
    )
    assert j["strict_recognized_identity_columns"]["isin"] is None
    assert j["exact_symbol_isin_count"] == 0
    assert all(
        x["state"] == "BLOCKED_MISSING_EXACT_IDENTITY_COLUMNS"
        for x in j["original_source_company_states"]
    )
    assert _column(["sym", "ISIN", "Series"], "symbol") is None


def test_original_source_provenance_first_seen_and_byte_tampering_fail_closed():
    src = _sample_source()
    with pytest.raises(AlphaContractError, match="before protocol registration"):
        analyze_original(
            root=ROOT, original_gzip=src,
            first_observed_at_utc="2026-10-20T11:15:00Z",
        )
    with pytest.raises(AlphaContractError, match="valid original gzip"):
        analyze_original(
            root=ROOT, original_gzip=b"x" * 600_000,
            first_observed_at_utc="2026-10-21T11:15:00Z",
        )


def test_original_gzip_and_signed_replay_is_independent_of_json_copies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from marketlab import hg009_p034_mii_security as p034

    original = _frozen(ROOT)
    monkeypatch.setattr(p034, "_frozen", lambda root: original)
    src = _sample_source()
    report = archive(
        root=tmp_path, original_gzip=src,
        first_observed_at_utc="2026-10-21T11:15:00Z",
    )
    assert report["report_sha256"]
    assert (tmp_path / report["original_repo_path"]).read_bytes() == src
    result = replay_originals(tmp_path)
    assert result["state"] == "VERIFIED_MII_ORIGINAL_REPLAY"
    assert result["original_source_count"] == 1
    assert result["original_sources"][0]["exact_300_identity_matches"] == 300
    original_json = next((tmp_path / p034.RECEIPT_DIR).glob("*.json"))
    damaged = json.loads(original_json.read_text(encoding="utf-8"))
    damaged["exact_symbol_isin_count"] = 301
    original_json.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(AlphaContractError, match="signed receipt tampered"):
        replay_originals(tmp_path)


def test_model_drift_cannot_be_hidden_by_resigning_a_report():
    j = analyze_original(
        root=ROOT, original_gzip=_sample_source(),
        first_observed_at_utc="2026-10-21T11:15:00Z",
    )
    changed = copy.deepcopy(j)
    changed["original_source_company_states"][0]["verified_sector"] = "Invented"
    changed["report_sha256"] = digest({
        k: v for k, v in changed.items() if k != "report_sha256"
    })
    assert changed != j
    assert changed["new_prospective_industry_model_authorized"] is False
    # Only archive()/replay_originals() can admit a source packet.
    # Re-signing unsupported classifications cannot manufacture source bytes.
