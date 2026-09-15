from __future__ import annotations

import importlib.util
from pathlib import Path

from marketlab.h024_acquisition import canonical_hash, source_from_discovery_row
from marketlab.h024_prospective import (
    append_evidence,
    append_sources,
    new_evidence_ledger,
    new_source_ledger,
)


def _load_scanner_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_h024_prospective_scan.py"
    spec = importlib.util.spec_from_file_location("run_h024_prospective_scan", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _source(
    *,
    app_id: str,
    submission_type: str = "Original",
    disseminated: str = "16-Sep-2026 18:00:02",
) -> dict:
    source = source_from_discovery_row(
        {
            "symbol": "AAA",
            "companyName": "AAA Limited",
            "regulation": "Regulation 7 (2)",
            "appId": app_id,
            "prevAppId": "",
            "typeOfSubmission": submission_type,
            "revisionRemark": "",
            "broadcastDateTime": disseminated,
            "exchdisstime": disseminated,
            "xmlFileName": (
                f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}.xml"
            ),
            "ixbrl": (
                f"https://nsearchives.nseindia.com/corporate/xbrl/{app_id}_WEB.html"
            ),
        }
    )
    assert source is not None
    return source


def _ready(source: dict) -> dict:
    return {
        "status": "READY",
        "source_id": source["source_id"],
        "xbrl_sha256": canonical_hash({"raw": source["source_id"]}),
        "date_of_filing": "2026-09-16",
        "transaction_count": 1,
        "direct_market_purchase_count": 1,
        "direct_market_purchase_value_inr": 15_000_000.0,
        "direct_market_purchase_quantity": 10_000,
        "direct_market_purchase_ownership_delta_pp": 0.05,
        "direct_market_purchase_actor_count": 1,
        "direct_market_purchase_categories": ["Promoter"],
        "direct_market_purchase_names": ["Example Insider"],
    }


def test_postboundary_original_remains_pending_after_discovery_window_rolls_forward() -> None:
    scanner = _load_scanner_module()
    pending = _source(app_id="PENDING")
    sealed = _source(app_id="SEALED")
    revision = _source(app_id="REVISION", submission_type="Revision")
    preboundary = _source(app_id="OLD", disseminated="15-Sep-2026 23:00:00")

    sources = append_sources(
        new_source_ledger(),
        [pending, sealed, revision, preboundary],
        first_seen_at_utc="2026-09-17T12:31:00Z",
    )
    evidence = append_evidence(
        new_evidence_ledger(),
        sources,
        _ready(sealed),
        frozen_at_utc="2026-09-17T12:32:00Z",
    )

    # The helper operates on canonical source state, not the current discovery response.
    # Therefore a failed post-boundary Original stays retryable even after it no longer
    # appears in a later trailing discovery window.
    retry = scanner._pending_original_sources(sources, evidence)
    assert [source["app_id"] for source in retry] == ["PENDING"]
