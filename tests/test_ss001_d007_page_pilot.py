from __future__ import annotations

import pytest

from marketlab.alpha import AlphaContractError
from marketlab.ss001_d007_page_pilot import (
    EXPECTED_MODEL_CONFIG_SHA,
    EXPECTED_QUEUE_ID,
    EXPECTED_QUEUE_SHA,
    ISSUERS,
    select_page_pilot,
)


def _queue() -> dict:
    rows = []
    index = 1
    for symbol in ISSUERS:
        for page in range(3):
            segment_id = f"{symbol}:page:{page}"
            rows.append({
                "symbol": symbol,
                "segment_id": segment_id,
                "global_request_index": index,
                "prompt_envelope": {
                    "request": {
                        "segments": [{"segment_id": segment_id, "text": "x", "text_sha256": "a"}]
                    }
                },
            })
            index += 1
    # Fill to frozen request count without changing the first two per issuer.
    while len(rows) < 1240:
        symbol = ISSUERS[len(rows) % len(ISSUERS)]
        segment_id = f"{symbol}:filler:{len(rows)}"
        rows.append({
            "symbol": symbol,
            "segment_id": segment_id,
            "global_request_index": len(rows) + 1,
            "prompt_envelope": {
                "request": {
                    "segments": [{"segment_id": segment_id, "text": "x", "text_sha256": "a"}]
                }
            },
        })
    return {
        "queue_id": EXPECTED_QUEUE_ID,
        "queue_sha256": EXPECTED_QUEUE_SHA,
        "model_config_sha256": EXPECTED_MODEL_CONFIG_SHA,
        "fresh_request_count": 1240,
        "issuer_symbols": list(ISSUERS),
        "requests": rows,
        "model_inference_executed": False,
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def test_selection_is_exactly_first_two_requests_per_issuer() -> None:
    result = select_page_pilot(_queue())
    assert result["selected_request_count"] == 24
    assert result["issuer_counts"] == {symbol: 2 for symbol in ISSUERS}
    for symbol in ISSUERS:
        selected = [row for row in result["rows"] if row["symbol"] == symbol]
        assert [row["segment_id"] for row in selected] == [
            f"{symbol}:page:0",
            f"{symbol}:page:1",
        ]
    assert result["model_inference_executed"] is False
    assert result["share_action_clearance_proven"] is False


def test_selection_fails_closed_on_queue_hash_change() -> None:
    queue = _queue()
    queue["queue_sha256"] = "0" * 64
    with pytest.raises(AlphaContractError, match="queue SHA mismatch"):
        select_page_pilot(queue)
