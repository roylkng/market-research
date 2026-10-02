from __future__ import annotations

import pytest

from marketlab.h023_acquisition import (
    H023AcquisitionError,
    source_from_master_row,
)


def _row(**overrides):
    row = {
        "symbol": "TCS",
        "recordId": 210064,
        "date": "31-Mar-2026",
        "broadcastDate": "17-Sep-2026 13:00:28",
        "xbrl": (
            "https://nsearchives.nseindia.com/"
            "corporate/xbrl/SHP_1724789_16092026073806_WEB.xml"
        ),
        "revisedStatus": "Revised",
        "revisionDate": "16-Sep-2026",
        "revisionRemark": "Revision made to promoter/promoter-group list",
    }
    row.update(overrides)
    return row


def test_formal_nse_revision_metadata_is_retained():
    source = source_from_master_row(_row(), symbol="TCS")
    assert source is not None
    assert source["record_id"] == "210064"
    assert source["report_date"] == "2026-03-31"
    assert source["revision_status"] == "REVISED"
    assert source["revision_date"] == "2026-09-16"
    assert source["broadcast_at_utc"] == "2026-09-17T07:30:28Z"


def test_revision_date_without_revised_status_fails_closed():
    with pytest.raises(
        H023AcquisitionError,
        match="revisionDate is present without revisedStatus",
    ):
        source_from_master_row(
            _row(revisedStatus=""),
            symbol="TCS",
        )
