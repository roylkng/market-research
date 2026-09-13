from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

HYPOTHESIS_ID = "H022"
FEATURE_VERSION = "management_forward_information_delta_v1"
SOURCE_RULE_ID = "H003-E002"
SOURCE_RULE_SHA256 = "5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2"
SOURCE_BUNDLE_SHA256 = "583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee"
SOURCE_REPORT_SHA256 = "cb48b1e18c76a3ea2d06b13383955c0f0c6efa6d3d65bd132ac3d5e59217ffea"
EXPECTED_SOURCE_COUNT = 794
EXPECTED_CANDIDATE_COUNT = 2692
SOURCE_CUTOFF = datetime.fromisoformat("2026-09-06T12:21:06.431463+00:00")
CHALLENGE_START = date(2025, 10, 1)


class H022Error(ValueError):
    """Raised when the frozen H022 feature panel cannot be built safely."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise H022Error("H022 payload must contain finite JSON values") from exc
    return hashlib.sha256(raw).hexdigest()


def _timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise H022Error(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise H022Error(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H022Error(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise H022Error(f"{field} must be a positive integer")
    return value


def validate_source_report(document: dict[str, Any]) -> None:
    if document.get("schema_version") != 1:
        raise H022Error("unexpected H003 candidate report schema")
    if document.get("rule_id") != SOURCE_RULE_ID:
        raise H022Error("unexpected H003 extraction rule id")
    if document.get("rule_sha256") != SOURCE_RULE_SHA256:
        raise H022Error("H003 extraction rule hash changed")
    if document.get("source_bundle_sha256") != SOURCE_BUNDLE_SHA256:
        raise H022Error("H003 source bundle changed")
    if document.get("report_sha256") != SOURCE_REPORT_SHA256:
        raise H022Error("H003 candidate report hash changed")
    if document.get("processed_source_count") != EXPECTED_SOURCE_COUNT:
        raise H022Error("H003 candidate report source count changed")
    if document.get("candidate_count") != EXPECTED_CANDIDATE_COUNT:
        raise H022Error("H003 candidate report candidate count changed")
    if document.get("complete") is not True or document.get("freeze_blockers") != []:
        raise H022Error("H003 candidate report is not complete and blocker-free")
    if document.get("source_status_counts") != {"TEXT_READY": EXPECTED_SOURCE_COUNT}:
        raise H022Error("H003 source status coverage changed")

    records = document.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_SOURCE_COUNT:
        raise H022Error("H003 candidate report must contain exactly 794 source records")

    seen_source_ids: set[str] = set()
    observed_candidates = 0
    for record in records:
        if not isinstance(record, dict):
            raise H022Error("source record must be an object")
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id or source_id in seen_source_ids:
            raise H022Error(f"invalid or duplicate source_id: {source_id}")
        seen_source_ids.add(source_id)
        if record.get("status") != "TEXT_READY":
            raise H022Error(f"{source_id}: source is not TEXT_READY")
        symbol = record.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise H022Error(f"{source_id}: symbol is missing")
        published = _timestamp(
            record.get("exchange_published_at_utc"),
            f"{source_id}.exchange_published_at_utc",
        )
        if published > SOURCE_CUTOFF:
            raise H022Error(f"{source_id}: publication is after frozen source cutoff")
        _positive_int(record.get("text_char_count"), f"{source_id}.text_char_count")
        candidates = record.get("candidates")
        if not isinstance(candidates, list):
            raise H022Error(f"{source_id}: candidates must be a list")
        if record.get("candidate_count") != len(candidates):
            raise H022Error(f"{source_id}: candidate_count mismatch")
        observed_candidates += len(candidates)
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise H022Error(f"{source_id}: candidate must be an object")
            if candidate.get("source_id") != source_id or candidate.get("symbol") != symbol:
                raise H022Error(f"{source_id}: candidate identity mismatch")
            if _timestamp(
                candidate.get("exchange_published_at_utc"),
                f"{source_id}.candidate.exchange_published_at_utc",
            ) != published:
                raise H022Error(f"{source_id}: candidate publication timestamp mismatch")
            if not isinstance(candidate.get("deadline_markers"), list):
                raise H022Error(f"{source_id}: deadline_markers must be a list")
            if not isinstance(candidate.get("domain_markers"), list):
                raise H022Error(f"{source_id}: domain_markers must be a list")

    if observed_candidates != EXPECTED_CANDIDATE_COUNT:
        raise H022Error(
            f"H003 candidate sum mismatch: expected={EXPECTED_CANDIDATE_COUNT}, "
            f"observed={observed_candidates}"
        )


def _record_metrics(record: dict[str, Any]) -> dict[str, float | int]:
    candidates = record["candidates"]
    text_chars = int(record["text_char_count"])
    candidate_count = len(candidates)
    deadline_count = sum(1 for row in candidates if row["deadline_markers"])
    domains = {
        str(marker).strip().casefold()
        for row in candidates
        for marker in row["domain_markers"]
        if str(marker).strip()
    }
    scale = 10_000.0 / text_chars
    return {
        "candidate_count": candidate_count,
        "text_char_count": text_chars,
        "deadline_candidate_count": deadline_count,
        "unique_domain_count": len(domains),
        "forward_commitment_density_per_10k_chars": candidate_count * scale,
        "deadline_candidate_density_per_10k_chars": deadline_count * scale,
        "domain_breadth_density_per_10k_chars": len(domains) * scale,
        "deadline_share": deadline_count / candidate_count if candidate_count else 0.0,
    }


def _finite_delta(current: object, prior: object) -> float:
    result = float(current) - float(prior)
    if not math.isfinite(result):
        raise H022Error("non-finite H022 feature delta")
    return result


def build_feature_panel(document: dict[str, Any]) -> dict[str, Any]:
    validate_source_report(document)
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in document["records"]:
        by_symbol[str(source["symbol"]).upper()].append(source)

    rows: list[dict[str, Any]] = []
    signal_count = 0
    no_prior_count = 0
    ambiguous_prior_count = 0

    for symbol in sorted(by_symbol):
        by_timestamp: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
        for source in by_symbol[symbol]:
            published = _timestamp(
                source["exchange_published_at_utc"],
                f"{source['source_id']}.exchange_published_at_utc",
            )
            by_timestamp[published].append(source)

        prior_group: list[dict[str, Any]] | None = None
        for published in sorted(by_timestamp):
            current_group = sorted(by_timestamp[published], key=lambda row: row["source_id"])
            for source in current_group:
                current = _record_metrics(source)
                row: dict[str, Any] = {
                    "schema_version": 1,
                    "hypothesis_id": HYPOTHESIS_ID,
                    "feature_version": FEATURE_VERSION,
                    "symbol": symbol,
                    "source_id": source["source_id"],
                    "exchange_published_at_utc": published.isoformat().replace("+00:00", "Z"),
                    "historical_split": (
                        "CHALLENGE" if published.date() >= CHALLENGE_START else "DESIGN"
                    ),
                    "survivor_panel": True,
                    "prior_source_id": None,
                    "prior_exchange_published_at_utc": None,
                    "feature_status": None,
                    "primary_signal": None,
                    "current": current,
                    "prior": None,
                    "deltas": None,
                }
                if prior_group is None:
                    row["feature_status"] = "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
                    no_prior_count += 1
                elif len(prior_group) != 1:
                    row["feature_status"] = "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP"
                    ambiguous_prior_count += 1
                else:
                    prior_source = prior_group[0]
                    prior = _record_metrics(prior_source)
                    deltas = {
                        "forward_commitment_density_delta": _finite_delta(
                            current["forward_commitment_density_per_10k_chars"],
                            prior["forward_commitment_density_per_10k_chars"],
                        ),
                        "deadline_candidate_density_delta": _finite_delta(
                            current["deadline_candidate_density_per_10k_chars"],
                            prior["deadline_candidate_density_per_10k_chars"],
                        ),
                        "domain_breadth_density_delta": _finite_delta(
                            current["domain_breadth_density_per_10k_chars"],
                            prior["domain_breadth_density_per_10k_chars"],
                        ),
                        "deadline_share_delta": _finite_delta(
                            current["deadline_share"], prior["deadline_share"]
                        ),
                    }
                    row.update(
                        {
                            "prior_source_id": prior_source["source_id"],
                            "prior_exchange_published_at_utc": prior_source[
                                "exchange_published_at_utc"
                            ],
                            "feature_status": "SIGNAL",
                            "primary_signal": deltas["forward_commitment_density_delta"],
                            "prior": prior,
                            "deltas": deltas,
                        }
                    )
                    signal_count += 1
                rows.append(row)
            prior_group = current_group

    rows.sort(key=lambda row: (row["exchange_published_at_utc"], row["symbol"], row["source_id"]))
    panel = {
        "schema_version": 1,
        "hypothesis_id": HYPOTHESIS_ID,
        "feature_version": FEATURE_VERSION,
        "source_report_sha256": SOURCE_REPORT_SHA256,
        "source_rule_id": SOURCE_RULE_ID,
        "source_rule_sha256": SOURCE_RULE_SHA256,
        "source_bundle_sha256": SOURCE_BUNDLE_SHA256,
        "universe_bias": "CURRENT_2026_U001_SURVIVOR_PANEL",
        "outcome_data_attached": False,
        "record_count": len(rows),
        "signal_count": signal_count,
        "no_prior_count": no_prior_count,
        "ambiguous_prior_count": ambiguous_prior_count,
        "design_signal_count": sum(
            1 for row in rows if row["feature_status"] == "SIGNAL" and row["historical_split"] == "DESIGN"
        ),
        "challenge_signal_count": sum(
            1
            for row in rows
            if row["feature_status"] == "SIGNAL" and row["historical_split"] == "CHALLENGE"
        ),
        "records": rows,
    }
    panel["panel_sha256"] = _canonical_hash(panel)
    return panel


def validate_feature_panel(panel: dict[str, Any]) -> None:
    stored = panel.get("panel_sha256")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if stored != _canonical_hash(unsigned):
        raise H022Error("H022 feature panel hash mismatch")
    if panel.get("source_report_sha256") != SOURCE_REPORT_SHA256:
        raise H022Error("H022 feature panel source report changed")
    if panel.get("outcome_data_attached") is not False:
        raise H022Error("H022 feature panel must not contain outcome data")
    records = panel.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_SOURCE_COUNT:
        raise H022Error("H022 feature panel record count changed")
    for row in records:
        if not isinstance(row, dict):
            raise H022Error("H022 feature row must be an object")
        forbidden = {"stock_return", "benchmark_return", "future_return", "price"}
        if forbidden.intersection(row):
            raise H022Error("H022 feature row contains prohibited outcome/price field")
