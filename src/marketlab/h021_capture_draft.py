from __future__ import annotations

from datetime import date

from marketlab.h021_capture import (
    CANONICAL_BATCH_SPEC_PATH,
    CANONICAL_COMPARISON_CONTRACT_PATH,
    CANONICAL_PROTOCOL_PATH,
    CANONICAL_SOURCE_VERSION,
    CANONICAL_UNIVERSE_BLOB_SHA,
    CANONICAL_UNIVERSE_PATH,
    validate_capture_inputs,
)

DRAFT_SCHEMA_VERSION = 1
DRAFT_STATE = "ACQUISITION_INCOMPLETE"
PENDING_STATE = "PENDING"


def _batch_id_for_rank(batch_spec: dict, rank: int) -> str:
    matches = [
        batch["batch_id"]
        for batch in batch_spec["batches"]
        if batch["rank_min"] <= rank <= batch["rank_max"]
    ]
    if len(matches) != 1:
        raise ValueError(f"rank {rank} does not belong to exactly one frozen batch")
    return matches[0]


def build_capture_draft(
    capture_date_ist: str,
    universe: dict,
    batch_spec: dict,
    *,
    version: int = 1,
    correction_reason: str | None = None,
) -> dict:
    try:
        parsed_date = date.fromisoformat(capture_date_ist)
    except (TypeError, ValueError) as exc:
        raise ValueError("capture_date_ist must be ISO YYYY-MM-DD") from exc
    if parsed_date.isoformat() != capture_date_ist:
        raise ValueError("capture_date_ist must be canonical ISO YYYY-MM-DD")

    if not isinstance(version, int) or isinstance(version, bool) or version <= 0:
        raise ValueError("version must be a positive integer")
    if version > 1 and (not isinstance(correction_reason, str) or not correction_reason.strip()):
        raise ValueError("capture versions greater than v1 require correction_reason")
    if version == 1 and correction_reason is not None:
        raise ValueError("v1 capture draft must not carry correction_reason")

    input_errors = validate_capture_inputs(universe, batch_spec)
    if input_errors:
        raise ValueError({"capture_input_errors": input_errors})

    observations: list[dict] = []
    for member in sorted(universe["members"], key=lambda item: item["rank"]):
        rank = member["rank"]
        observations.append(
            {
                "symbol": member["symbol"],
                "company_name": member.get("company_name"),
                "isin": member["isin"],
                "series": member.get("series"),
                "constituent_industry": member.get("constituent_industry"),
                "universe_rank": rank,
                "batch_id": _batch_id_for_rank(batch_spec, rank),
                "data_state": PENDING_STATE,
                "retrieval_notes": "",
                "fiscal_period": "",
                "period_ending": None,
                "consensus_eps": None,
                "eps_currency": None,
                "revenue_growth_forecast_pct": None,
                "profit_growth_estimate_pct": None,
                "analyst_count": None,
                "target_price_inr": None,
                "source_observed_market_date": None,
                "source_url": "",
                "source_status": PENDING_STATE,
            }
        )

    logical_capture_id = f"{capture_date_ist}-full-u001-v{version}"
    draft = {
        "draft_schema_version": DRAFT_SCHEMA_VERSION,
        "draft_state": DRAFT_STATE,
        "schema_version": 1,
        "hypothesis_id": "H021",
        "logical_capture_id": logical_capture_id,
        "capture_date_ist": capture_date_ist,
        "captured_at_utc": None,
        "source_version": CANONICAL_SOURCE_VERSION,
        "universe_path": CANONICAL_UNIVERSE_PATH,
        "universe_git_blob_sha": CANONICAL_UNIVERSE_BLOB_SHA,
        "protocol_path": CANONICAL_PROTOCOL_PATH,
        "comparison_contract_path": CANONICAL_COMPARISON_CONTRACT_PATH,
        "batch_spec_path": CANONICAL_BATCH_SPEC_PATH,
        "outcomes_opened": False,
        "live_capital_allowed": False,
        "observations": observations,
    }
    if correction_reason is not None:
        draft["correction_reason"] = correction_reason.strip()
    return draft
