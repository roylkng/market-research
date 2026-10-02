from copy import deepcopy

import pytest

from marketlab.rm001_d013_r1 import (
    BRSR_PAGE_URL,
    build_r1_report,
    discover_brsr_api_candidates,
    evaluate_endpoint_correspondence,
    extract_first_party_script_urls,
    match_filing_to_dedicated_rows,
    normalize_dedicated_brsr_row,
)


def _filing(
    *,
    year="FY2024-25",
    score="a",
    app_id="APP123",
    symbol="TEST",
    submitted="2025-07-31T18:55:09",
    period_start="2024-04-01",
    period_end="2025-03-31",
):
    return {
        "year": year,
        "sample_score": score,
        "stable_identity": "CIN:L000000000000000001",
        "app_id": app_id,
        "symbol": symbol,
        "submission_timestamp_raw": "31-Jul-2025 18:55:09",
        "submission_timestamp_parsed": submitted,
        "reporting_period_start": period_start,
        "reporting_period_end": period_end,
        "nic": {
            "distinct_nic_count": 1,
            "status": "READY_SINGLE_NIC",
            "weights": {"6201": 1.0},
        },
    }


def _row(
    *,
    app_id="APP123",
    symbol="TEST",
    broadcast="31-Jul-2025 18:55:10",
    financial_year="2024-25",
    resource="https://nseindia.com/xbrl/APP123.xml",
):
    return {
        "symbol": symbol,
        "appId": app_id,
        "financialYear": financial_year,
        "broadcastDateTime": broadcast,
        "xbrlFile": resource,
    }


def test_extract_first_party_scripts_only():
    html = b"""
    <html><body>
      <script src="/assets/app.js"></script>
      <script src="https://www.nseindia.com/assets/brsr.js"></script>
      <script src="https://cdn.example.com/evil.js"></script>
    </body></html>
    """
    assert extract_first_party_script_urls(html) == [
        "https://www.nseindia.com/assets/app.js",
        "https://www.nseindia.com/assets/brsr.js",
    ]


def test_endpoint_discovery_uses_brsr_neighborhood_and_is_deterministic():
    scripts = {
        "https://www.nseindia.com/a.js": (
            b'const generic="/api/foo";'
            b'const label="Business Responsibility and Sustainability";'
            b'const x="/api/corporate-brsr";'
        ),
        "https://www.nseindia.com/b.js": (
            b'let title="BRSR sustainability";'
            b'let endpoint="/api/brsr-filings";'
        ),
    }
    candidates = discover_brsr_api_candidates(scripts)
    assert [row["endpoint_path"] for row in candidates] == [
        "/api/brsr-filings",
        "/api/corporate-brsr",
    ]
    assert candidates[0]["relevance_token_count"] >= 2
    assert len(candidates[0]["occurrences"][0]["script_sha256"]) == 64


def test_normalize_row_prefers_explicit_dissemination_over_received():
    row = {
        **_row(),
        "exchangeReceivedTime": "31-Jul-2025 18:55:09",
        "exchangeDisseminationTime": "31-Jul-2025 18:55:10",
    }
    normalized = normalize_dedicated_brsr_row(row)
    assert normalized["symbol"] == "TEST"
    assert normalized["app_id"] == "APP123"
    assert normalized["reporting_period_start"] == "2024-04-01"
    assert normalized["reporting_period_end"] == "2025-03-31"
    assert normalized["public_time_status"] == "READY"
    assert normalized["public_time_field"] == "exchangeDisseminationTime"
    assert normalized["public_time_utc"].endswith("+00:00")


def test_exact_app_id_linkage_beats_resource_and_period():
    filing = _filing()
    rows = [
        {"normalized": normalize_dedicated_brsr_row(_row(app_id="APP999")), "raw": {}},
        {"normalized": normalize_dedicated_brsr_row(_row()), "raw": {}},
    ]
    matched = match_filing_to_dedicated_rows(
        filing=filing,
        rows=rows,
    )
    assert matched["status"] == "MATCHED"
    assert matched["linkage_mode"] == "EXACT_APP_ID"
    assert matched["ist_abs_delta_seconds"] == pytest.approx(1.0)
    assert matched["ist_signed_delta_seconds"] == pytest.approx(1.0)
    assert matched["utc_abs_delta_seconds"] == pytest.approx(19_799.0)


def test_same_priority_duplicate_match_fails_closed():
    filing = _filing()
    first = normalize_dedicated_brsr_row(_row())
    second = normalize_dedicated_brsr_row(
        {
            **_row(resource="https://nseindia.com/other/APP123.xml"),
            "extra": "different-row",
        }
    )
    result = match_filing_to_dedicated_rows(
        filing=filing,
        rows=[
            {"normalized": first, "raw": {}},
            {"normalized": second, "raw": {}},
        ],
    )
    assert result["status"] == "AMBIGUOUS_SAME_PRIORITY_MATCH"
    assert result["linkage_mode"] == "EXACT_APP_ID"


def test_endpoint_correspondence_passes_frozen_timing_gates():
    sample = []
    rows_by_sample = {}
    query = {}
    for year_index, year in enumerate(("FY2023-24", "FY2024-25")):
        start = 2023 + year_index
        for index in range(4):
            score = f"{year_index}-{index}"
            submitted = f"{start + 1}-07-{20 + index:02d}T18:55:09"
            filing = _filing(
                year=year,
                score=score,
                app_id=f"APP{year_index}{index}",
                symbol=f"S{year_index}{index}",
                submitted=submitted,
                period_start=f"{start}-04-01",
                period_end=f"{start + 1}-03-31",
            )
            filing["submission_timestamp_raw"] = (
                f"{20 + index:02d}-Jul-{start + 1} 18:55:09"
            )
            sample.append(filing)
            normalized = normalize_dedicated_brsr_row(
                _row(
                    app_id=filing["app_id"],
                    symbol=filing["symbol"],
                    broadcast=(
                        f"{20 + index:02d}-Jul-{start + 1} 18:55:10"
                    ),
                    financial_year=f"{start}-{str(start + 1)[-2:]}",
                    resource=(
                        f"https://nseindia.com/xbrl/{filing['app_id']}.xml"
                    ),
                )
            )
            rows_by_sample[score] = [{"normalized": normalized, "raw": {}}]
            query[score] = {"variant": 1, "response_sha256": "f" * 64}

    report = evaluate_endpoint_correspondence(
        endpoint_path="/api/brsr",
        sample=sample,
        rows_by_sample=rows_by_sample,
        query_metadata_by_sample=query,
    )
    assert report["pass"] is True
    assert report["match_fraction_by_year"] == {
        "FY2023-24": 1.0,
        "FY2024-25": 1.0,
    }
    assert report["explicit_public_time_coverage"] == pytest.approx(1.0)
    assert report["ist_median_abs_delta_seconds"] == pytest.approx(1.0)
    assert report["ist_p95_abs_delta_seconds"] == pytest.approx(1.0)
    assert report["utc_median_abs_delta_seconds"] == pytest.approx(19_799.0)


def test_endpoint_correspondence_does_not_treat_submission_only_as_public():
    filing = _filing(score="x")
    row = _row()
    row.pop("broadcastDateTime")
    row["submittedAt"] = "31-Jul-2025 18:55:10"
    normalized = normalize_dedicated_brsr_row(row)
    report = evaluate_endpoint_correspondence(
        endpoint_path="/api/brsr",
        sample=[filing],
        rows_by_sample={"x": [{"normalized": normalized, "raw": {}}]},
        query_metadata_by_sample={"x": {"variant": 1}},
    )
    assert report["matched_count"] == 1
    assert report["explicit_public_time_count"] == 0
    assert report["gates"]["minimum_explicit_public_time_coverage"] is False
    assert report["pass"] is False
