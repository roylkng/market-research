from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from marketlab.h003_candidates import (
    ALLOWED_ATTACHMENT_HOSTS,
    CANDIDATE_VERSION,
    COMMITMENT_DOMAIN_MARKERS,
    DEADLINE_MARKERS,
    EXCLUDE_MARKERS,
    EXTRACTION_RULE_ID,
    EXTRACTION_RULE_SHA256,
    FUTURE_MARKERS,
    PARSER_LIBRARY_VERSION,
    PARSER_VERSION,
    QUANTITATIVE_PATTERN,
)

PROTOCOL_ID = "H022-P001"
HYPOTHESIS_ID = "H022"
FEATURE_VERSION = "management_forward_information_delta_v1"
COHORT_ID = "FY27-Q2-2026-09-06"
COHORT_RULE_VERSION = "U001-nifty200-top100-nonfinancial-ffmc-v2"
COHORT_SHA256 = "cbe8a8042351ab6b3eb21dc796161a926559442f15314e21598fe5538877edbb"
EXPECTED_MEMBER_COUNT = 100
HISTORICAL_CUTOFF = datetime.fromisoformat("2026-09-06T12:21:06.431463+00:00")
PROSPECTIVE_START = datetime.fromisoformat("2026-09-14T18:30:00+00:00")
HISTORICAL_BASELINE_REPORT_SHA256 = (
    "45f58e5f0ee72c477ed042fd56be54b4b7c297b78532a011350a44d0a68da861"
)
HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256 = (
    "85d30df9286712c362102865c22ec3a27907e85599bd70d0c053bc95554cb34c"
)

FORBIDDEN_OUTCOME_KEYS = frozenset(
    {
        "stock_price",
        "entry_price",
        "exit_price",
        "stock_return",
        "benchmark_return",
        "future_return",
        "future_20d_return",
        "future_60d_return",
        "future_120d_return",
        "gross_excess_pp",
        "cost_adjusted_excess_pp",
        "beat_benchmark",
        "benchmark_price",
        "valuation",
        "broker_target",
        "analyst_revision",
        "momentum",
        "h019_quality_state",
        "h020_timing_state",
    }
)


class H022ProspectiveError(ValueError):
    """Raised when a prospective H022 signal cannot be sealed safely."""


def _canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise H022ProspectiveError(
            "H022-P001 payload must contain finite JSON values"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise H022ProspectiveError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise H022ProspectiveError(f"invalid {field}: {value}") from exc
    if parsed.tzinfo is None:
        raise H022ProspectiveError(f"{field} must include timezone")
    return parsed.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _reject_forbidden_keys(payload: object, *, path: str = "root") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).strip().casefold()
            if normalized in FORBIDDEN_OUTCOME_KEYS:
                raise H022ProspectiveError(
                    f"forbidden price/outcome key at {path}.{key}"
                )
            _reject_forbidden_keys(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _reject_forbidden_keys(value, path=f"{path}[{index}]")


def validate_universe_snapshot(snapshot: dict[str, Any]) -> frozenset[str]:
    if not isinstance(snapshot, dict):
        raise H022ProspectiveError("U001 snapshot must be an object")
    stored = snapshot.get("sha256")
    unsigned = dict(snapshot)
    unsigned.pop("sha256", None)
    if stored != COHORT_SHA256 or _canonical_hash(unsigned) != COHORT_SHA256:
        raise H022ProspectiveError("U001 cohort digest changed")
    if snapshot.get("schema_version") != 2:
        raise H022ProspectiveError("U001 schema version changed")
    if snapshot.get("cohort_id") != COHORT_ID:
        raise H022ProspectiveError("unexpected U001 cohort id")
    if snapshot.get("rule_version") != COHORT_RULE_VERSION:
        raise H022ProspectiveError("U001 rule version changed")
    if snapshot.get("index_name") != "NIFTY 200":
        raise H022ProspectiveError("U001 index identity changed")
    if snapshot.get("selection_size") != EXPECTED_MEMBER_COUNT:
        raise H022ProspectiveError("U001 selection size changed")
    if (
        _timestamp(snapshot.get("captured_at_utc"), field="captured_at_utc")
        != HISTORICAL_CUTOFF
    ):
        raise H022ProspectiveError("U001 capture timestamp changed")

    members = snapshot.get("members")
    if not isinstance(members, list) or len(members) != EXPECTED_MEMBER_COUNT:
        raise H022ProspectiveError("U001 must contain exactly 100 members")

    symbols: set[str] = set()
    isins: set[str] = set()
    ranks: set[int] = set()
    prior_ffmc: float | None = None
    for member in members:
        if not isinstance(member, dict):
            raise H022ProspectiveError("U001 member must be an object")
        symbol = str(member.get("symbol") or "").strip().upper()
        isin = str(member.get("isin") or "").strip()
        rank = member.get("rank")
        ffmc = member.get("ffmc")
        industry = str(member.get("constituent_industry") or "").strip()
        if not symbol or symbol in symbols:
            raise H022ProspectiveError(f"invalid/duplicate U001 symbol: {symbol}")
        if not isin or isin in isins:
            raise H022ProspectiveError(f"invalid/duplicate U001 ISIN: {isin}")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank in ranks:
            raise H022ProspectiveError(f"invalid/duplicate U001 rank: {rank}")
        if not isinstance(ffmc, (int, float)) or isinstance(ffmc, bool):
            raise H022ProspectiveError(f"{symbol}: U001 ffmc must be numeric")
        ffmc_value = float(ffmc)
        if not math.isfinite(ffmc_value) or ffmc_value <= 0:
            raise H022ProspectiveError(f"{symbol}: U001 ffmc must be positive")
        if industry == "Financial Services":
            raise H022ProspectiveError(f"{symbol}: financial company entered U001")
        if str(member.get("series") or "").strip().upper() != "EQ":
            raise H022ProspectiveError(f"{symbol}: U001 series is not EQ")
        if prior_ffmc is not None and ffmc_value > prior_ffmc:
            raise H022ProspectiveError("U001 members are not ffmc-descending")
        prior_ffmc = ffmc_value
        symbols.add(symbol)
        isins.add(isin)
        ranks.add(rank)

    if ranks != set(range(1, EXPECTED_MEMBER_COUNT + 1)):
        raise H022ProspectiveError("U001 ranks must be exactly 1..100")
    return frozenset(symbols)


def _candidate_identity(
    candidate: dict[str, Any], *, source_id: str, symbol: str, raw_sha256: str
) -> dict[str, Any]:
    return {
        "rule_id": EXTRACTION_RULE_ID,
        "rule_sha256": EXTRACTION_RULE_SHA256,
        "candidate_version": CANDIDATE_VERSION,
        "source_id": source_id,
        "symbol": symbol,
        "raw_sha256": raw_sha256,
        "page_number": candidate["page_number"],
        "line_start": candidate["line_start"],
        "line_end": candidate["line_end"],
        "excerpt": candidate["excerpt"],
    }


def _validate_candidate(
    candidate: object,
    *,
    source_id: str,
    symbol: str,
    published: datetime,
    raw_sha256: str,
) -> None:
    if not isinstance(candidate, dict):
        raise H022ProspectiveError(f"{source_id}: candidate must be an object")
    if candidate.get("rule_id") != EXTRACTION_RULE_ID:
        raise H022ProspectiveError(f"{source_id}: candidate rule id changed")
    if candidate.get("rule_sha256") != EXTRACTION_RULE_SHA256:
        raise H022ProspectiveError(f"{source_id}: candidate rule digest changed")
    if candidate.get("candidate_version") != CANDIDATE_VERSION:
        raise H022ProspectiveError(f"{source_id}: candidate version changed")
    if candidate.get("source_id") != source_id or candidate.get("symbol") != symbol:
        raise H022ProspectiveError(f"{source_id}: candidate identity mismatch")
    if (
        _timestamp(
            candidate.get("exchange_published_at_utc"),
            field=f"{source_id}.candidate.exchange_published_at_utc",
        )
        != published
    ):
        raise H022ProspectiveError(f"{source_id}: candidate timestamp mismatch")
    if candidate.get("raw_sha256") != raw_sha256:
        raise H022ProspectiveError(f"{source_id}: candidate raw digest mismatch")
    if candidate.get("parser_version") != PARSER_VERSION:
        raise H022ProspectiveError(f"{source_id}: candidate parser version changed")
    if candidate.get("disposition") != "UNREVIEWED":
        raise H022ProspectiveError(f"{source_id}: candidate disposition changed")
    if candidate.get("disposition_reason") is not None:
        raise H022ProspectiveError(f"{source_id}: candidate has disposition reason")

    excerpt = candidate.get("excerpt")
    if not isinstance(excerpt, str) or not (20 <= len(excerpt) <= 600):
        raise H022ProspectiveError(f"{source_id}: candidate excerpt length is invalid")
    lowered = excerpt.casefold()
    stored_future_hits = candidate.get("future_markers")
    deadline_hits = [marker for marker in DEADLINE_MARKERS if marker in lowered]
    domain_hits = [marker for marker in COMMITMENT_DOMAIN_MARKERS if marker in lowered]
    quantitative_tokens = [
        token.strip()
        for token in QUANTITATIVE_PATTERN.findall(excerpt)
        if token.strip()
    ]
    if (
        not isinstance(stored_future_hits, list)
        or not stored_future_hits
        or len(stored_future_hits) != len(set(stored_future_hits))
        or stored_future_hits
        != [marker for marker in FUTURE_MARKERS if marker in stored_future_hits]
        or any(marker not in lowered for marker in stored_future_hits)
    ):
        raise H022ProspectiveError(f"{source_id}: candidate future markers changed")
    if not domain_hits or not (deadline_hits or quantitative_tokens):
        raise H022ProspectiveError(f"{source_id}: candidate no longer satisfies E002")
    if any(marker in lowered for marker in EXCLUDE_MARKERS):
        raise H022ProspectiveError(f"{source_id}: candidate contains E002 exclusion marker")
    if candidate.get("deadline_markers") != deadline_hits:
        raise H022ProspectiveError(f"{source_id}: candidate deadline markers changed")
    if candidate.get("domain_markers") != domain_hits:
        raise H022ProspectiveError(f"{source_id}: candidate domain markers changed")
    if candidate.get("quantitative_tokens") != quantitative_tokens:
        raise H022ProspectiveError(f"{source_id}: candidate quantitative tokens changed")

    for field in ("page_number", "line_start", "line_end"):
        value = candidate.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise H022ProspectiveError(f"{source_id}: candidate {field} is invalid")
    if int(candidate["line_end"]) < int(candidate["line_start"]):
        raise H022ProspectiveError(f"{source_id}: candidate line range is invalid")

    identity = _candidate_identity(
        candidate,
        source_id=source_id,
        symbol=symbol,
        raw_sha256=raw_sha256,
    )
    if candidate.get("candidate_id") != _canonical_hash(identity):
        raise H022ProspectiveError(f"{source_id}: candidate digest mismatch")


def validate_e002_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise H022ProspectiveError("E002 extraction record must be an object")
    _reject_forbidden_keys(record)
    if record.get("schema_version") != 1:
        raise H022ProspectiveError("E002 extraction record schema changed")
    if record.get("rule_id") != EXTRACTION_RULE_ID:
        raise H022ProspectiveError("E002 extraction rule id changed")
    if record.get("rule_sha256") != EXTRACTION_RULE_SHA256:
        raise H022ProspectiveError("E002 extraction rule digest changed")
    if record.get("status") != "TEXT_READY":
        raise H022ProspectiveError("P001 requires TEXT_READY E002 source")
    if record.get("failure_reason") is not None:
        raise H022ProspectiveError("TEXT_READY E002 source has failure reason")
    if record.get("parser_version") != PARSER_VERSION:
        raise H022ProspectiveError("E002 parser version changed")
    if record.get("parser_library_version") != PARSER_LIBRARY_VERSION:
        raise H022ProspectiveError("E002 parser library version changed")

    source_id = str(record.get("source_id") or "").strip()
    symbol = str(record.get("symbol") or "").strip().upper()
    if not source_id or not symbol:
        raise H022ProspectiveError("E002 source identity is missing")
    published = _timestamp(
        record.get("exchange_published_at_utc"),
        field=f"{source_id}.exchange_published_at_utc",
    )
    attachment_url = str(record.get("attachment_url") or "").strip()
    parsed_url = urlparse(attachment_url)
    if (
        parsed_url.scheme != "https"
        or (parsed_url.hostname or "").lower() not in ALLOWED_ATTACHMENT_HOSTS
    ):
        raise H022ProspectiveError(f"{source_id}: attachment URL is not approved NSE host")

    raw_sha256 = record.get("raw_sha256")
    text_sha256 = record.get("text_sha256")
    if not _is_sha256(raw_sha256) or not _is_sha256(text_sha256):
        raise H022ProspectiveError(f"{source_id}: raw/text digest is invalid")
    for field in ("raw_byte_count", "page_count", "text_char_count"):
        value = record.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise H022ProspectiveError(f"{source_id}: {field} must be positive")

    candidates = record.get("candidates")
    if not isinstance(candidates, list):
        raise H022ProspectiveError(f"{source_id}: candidates must be a list")
    if record.get("candidate_count") != len(candidates):
        raise H022ProspectiveError(f"{source_id}: candidate_count mismatch")
    seen_candidates: set[str] = set()
    for candidate in candidates:
        _validate_candidate(
            candidate,
            source_id=source_id,
            symbol=symbol,
            published=published,
            raw_sha256=str(raw_sha256),
        )
        candidate_id = str(candidate["candidate_id"])
        if candidate_id in seen_candidates:
            raise H022ProspectiveError(f"{source_id}: duplicate candidate id")
        seen_candidates.add(candidate_id)

    unsigned = dict(record)
    stored_record_id = unsigned.pop("record_id", None)
    if not _is_sha256(stored_record_id) or stored_record_id != _canonical_hash(unsigned):
        raise H022ProspectiveError(f"{source_id}: extraction record digest mismatch")


def _metrics(record: dict[str, Any]) -> dict[str, float | int]:
    validate_e002_record(record)
    candidates = record["candidates"]
    text_chars = int(record["text_char_count"])
    deadline_count = sum(1 for row in candidates if row["deadline_markers"])
    domains = {
        str(marker).strip().casefold()
        for row in candidates
        for marker in row["domain_markers"]
        if str(marker).strip()
    }
    count = len(candidates)
    scale = 10_000.0 / text_chars
    return {
        "candidate_count": count,
        "text_char_count": text_chars,
        "deadline_candidate_count": deadline_count,
        "unique_domain_count": len(domains),
        "forward_commitment_density_per_10k_chars": count * scale,
        "deadline_candidate_density_per_10k_chars": deadline_count * scale,
        "domain_breadth_density_per_10k_chars": len(domains) * scale,
        "deadline_share": deadline_count / count if count else 0.0,
    }


def source_disposition(record: dict[str, Any]) -> str:
    validate_e002_record(record)
    published = _timestamp(
        record["exchange_published_at_utc"], field="exchange_published_at_utc"
    )
    if published <= HISTORICAL_CUTOFF:
        return "HISTORICAL_BASELINE"
    if published < PROSPECTIVE_START:
        return "CONTEXT_ONLY_PRE_START"
    return "PROSPECTIVE_SIGNAL_ELIGIBLE"


def build_context_gate(
    *,
    universe_snapshot: dict[str, Any],
    discovery_manifest_sha256: str,
    covered_symbols: list[str],
    catchup_source_ids: list[str],
    completed_at_utc: str,
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe_snapshot)
    if not _is_sha256(discovery_manifest_sha256):
        raise H022ProspectiveError("catch-up discovery manifest digest is invalid")
    normalized_covered = sorted({symbol.strip().upper() for symbol in covered_symbols})
    if set(normalized_covered) != set(members):
        raise H022ProspectiveError("catch-up discovery did not cover the full U001 cohort")
    normalized_source_ids = sorted({source_id.strip() for source_id in catchup_source_ids})
    if any(not source_id for source_id in normalized_source_ids):
        raise H022ProspectiveError("catch-up source id is empty")
    completed = _timestamp(completed_at_utc, field="context_gate.completed_at_utc")
    if completed < PROSPECTIVE_START:
        raise H022ProspectiveError("catch-up gate cannot complete before prospective start")

    gate: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "historical_baseline_report_sha256": HISTORICAL_BASELINE_REPORT_SHA256,
        "historical_baseline_source_bundle_sha256": (
            HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256
        ),
        "catchup_start_exclusive_utc": _utc_text(HISTORICAL_CUTOFF),
        "catchup_end_exclusive_utc": _utc_text(PROSPECTIVE_START),
        "discovery_manifest_sha256": discovery_manifest_sha256,
        "covered_member_count": len(normalized_covered),
        "covered_symbols": normalized_covered,
        "catchup_source_count": len(normalized_source_ids),
        "catchup_source_ids": normalized_source_ids,
        "status": "COMPLETE",
        "completed_at_utc": _utc_text(completed),
        "outcome_data_attached": False,
    }
    gate["context_gate_sha256"] = _canonical_hash(gate)
    return gate


def validate_context_gate(gate: dict[str, Any], universe_snapshot: dict[str, Any]) -> None:
    members = validate_universe_snapshot(universe_snapshot)
    if not isinstance(gate, dict):
        raise H022ProspectiveError("P001 context gate must be an object")
    _reject_forbidden_keys(gate)
    stored = gate.get("context_gate_sha256")
    unsigned = dict(gate)
    unsigned.pop("context_gate_sha256", None)
    if not _is_sha256(stored) or stored != _canonical_hash(unsigned):
        raise H022ProspectiveError("P001 context gate digest mismatch")
    expected_identity = {
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "historical_baseline_report_sha256": HISTORICAL_BASELINE_REPORT_SHA256,
        "historical_baseline_source_bundle_sha256": (
            HISTORICAL_BASELINE_SOURCE_BUNDLE_SHA256
        ),
        "catchup_start_exclusive_utc": _utc_text(HISTORICAL_CUTOFF),
        "catchup_end_exclusive_utc": _utc_text(PROSPECTIVE_START),
    }
    for key, expected in expected_identity.items():
        if gate.get(key) != expected:
            raise H022ProspectiveError(f"P001 context gate {key} changed")
    if gate.get("status") != "COMPLETE" or gate.get("outcome_data_attached") is not False:
        raise H022ProspectiveError("P001 context gate is not complete/outcome-free")
    covered = gate.get("covered_symbols")
    if not isinstance(covered, list) or set(covered) != set(members):
        raise H022ProspectiveError("P001 context gate cohort coverage changed")
    if gate.get("covered_member_count") != EXPECTED_MEMBER_COUNT:
        raise H022ProspectiveError("P001 context gate member count changed")
    source_ids = gate.get("catchup_source_ids")
    if not isinstance(source_ids, list) or len(source_ids) != len(set(source_ids)):
        raise H022ProspectiveError("P001 context gate source ids are invalid")
    if gate.get("catchup_source_count") != len(source_ids):
        raise H022ProspectiveError("P001 context gate source count mismatch")
    if not _is_sha256(gate.get("discovery_manifest_sha256")):
        raise H022ProspectiveError("P001 context gate discovery digest is invalid")
    if (
        _timestamp(gate.get("completed_at_utc"), field="context_gate.completed_at_utc")
        < PROSPECTIVE_START
    ):
        raise H022ProspectiveError("P001 context gate completed before prospective start")


def _delta(current: object, prior: object) -> float:
    result = float(current) - float(prior)
    if not math.isfinite(result):
        raise H022ProspectiveError("non-finite prospective H022 delta")
    return result


def _signal_record_hash(record: dict[str, Any]) -> str:
    unsigned = dict(record)
    unsigned.pop("signal_record_sha256", None)
    return _canonical_hash(unsigned)


def validate_signal_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise H022ProspectiveError("P001 signal record must be an object")
    _reject_forbidden_keys(record)
    if record.get("protocol_id") != PROTOCOL_ID or record.get("hypothesis_id") != HYPOTHESIS_ID:
        raise H022ProspectiveError("P001 signal record identity changed")
    if record.get("cohort_id") != COHORT_ID or record.get("cohort_sha256") != COHORT_SHA256:
        raise H022ProspectiveError("P001 signal record cohort changed")
    if record.get("feature_version") != FEATURE_VERSION:
        raise H022ProspectiveError("P001 feature version changed")
    if record.get("outcome_data_attached") is not False:
        raise H022ProspectiveError("P001 signal record contains outcome attachment")
    if not _is_sha256(record.get("context_gate_sha256")):
        raise H022ProspectiveError("P001 signal record context-gate digest is invalid")
    stored = record.get("signal_record_sha256")
    if not _is_sha256(stored) or stored != _signal_record_hash(record):
        raise H022ProspectiveError("P001 signal record digest mismatch")
    if record.get("signal_status") not in {
        "SIGNAL",
        "NO_SIGNAL_NO_PRIOR_TRANSCRIPT",
        "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP",
    }:
        raise H022ProspectiveError("P001 signal status is invalid")
    published = _timestamp(
        record.get("exchange_published_at_utc"), field="signal.exchange_published_at_utc"
    )
    if published < PROSPECTIVE_START:
        raise H022ProspectiveError("P001 signal publication precedes prospective start")
    frozen = _timestamp(record.get("signal_frozen_at_utc"), field="signal.signal_frozen_at_utc")
    if frozen < published:
        raise H022ProspectiveError("P001 signal was frozen before publication")
    if not _is_sha256(record.get("source_record_id")):
        raise H022ProspectiveError("P001 source record id is invalid")
    if not _is_sha256(record.get("raw_sha256")) or not _is_sha256(record.get("text_sha256")):
        raise H022ProspectiveError("P001 source raw/text digest is invalid")
    status = record["signal_status"]
    if status == "SIGNAL":
        if record.get("primary_signal") is None or record.get("prior_source_id") is None:
            raise H022ProspectiveError("P001 SIGNAL is missing prior/signal")
        if not isinstance(record.get("deltas"), dict):
            raise H022ProspectiveError("P001 SIGNAL is missing deltas")
    elif record.get("primary_signal") is not None or record.get("deltas") is not None:
        raise H022ProspectiveError("P001 no-signal record contains signal values")


def seal_signal_record(
    *,
    current_record: dict[str, Any],
    context_records: list[dict[str, Any]],
    universe_snapshot: dict[str, Any],
    context_gate: dict[str, Any],
    signal_frozen_at_utc: str,
    cohort_end_utc: str | None = None,
) -> dict[str, Any]:
    members = validate_universe_snapshot(universe_snapshot)
    validate_context_gate(context_gate, universe_snapshot)
    validate_e002_record(current_record)
    current_symbol = str(current_record["symbol"]).strip().upper()
    if current_symbol not in members:
        raise H022ProspectiveError(f"{current_symbol}: source is outside frozen U001 cohort")
    current_published = _timestamp(
        current_record["exchange_published_at_utc"], field="current.exchange_published_at_utc"
    )
    if current_published < PROSPECTIVE_START:
        raise H022ProspectiveError("current source is not prospectively eligible")
    if cohort_end_utc is not None:
        cohort_end = _timestamp(cohort_end_utc, field="cohort_end_utc")
        if current_published >= cohort_end:
            raise H022ProspectiveError("current source belongs to successor U001 cohort")

    frozen_at = _timestamp(signal_frozen_at_utc, field="signal_frozen_at_utc")
    gate_completed = _timestamp(
        context_gate["completed_at_utc"], field="context_gate.completed_at_utc"
    )
    if frozen_at < current_published or frozen_at < gate_completed:
        raise H022ProspectiveError("signal freeze precedes publication or catch-up completion")

    current_source_id = str(current_record["source_id"])
    seen_context: set[str] = set()
    same_symbol_context: list[dict[str, Any]] = []
    for context in context_records:
        validate_e002_record(context)
        source_id = str(context["source_id"])
        if source_id == current_source_id:
            raise H022ProspectiveError("current source is duplicated in context records")
        if source_id in seen_context:
            raise H022ProspectiveError(f"duplicate context source id: {source_id}")
        seen_context.add(source_id)
        published = _timestamp(
            context["exchange_published_at_utc"],
            field=f"{source_id}.exchange_published_at_utc",
        )
        if published > current_published:
            raise H022ProspectiveError(f"{source_id}: future context would leak into signal")
        symbol = str(context["symbol"]).strip().upper()
        if symbol == current_symbol:
            same_symbol_context.append(context)

    grouped: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for context in same_symbol_context:
        published = _timestamp(
            context["exchange_published_at_utc"], field="context.exchange_published_at_utc"
        )
        if published < current_published:
            grouped[published].append(context)

    current_metrics = _metrics(current_record)
    prior_source: dict[str, Any] | None = None
    prior_group_source_ids: list[str] = []
    signal_status: str
    prior_metrics: dict[str, float | int] | None = None
    deltas: dict[str, float] | None = None
    primary_signal: float | None = None

    if not grouped:
        signal_status = "NO_SIGNAL_NO_PRIOR_TRANSCRIPT"
    else:
        latest_timestamp = max(grouped)
        latest_group = sorted(grouped[latest_timestamp], key=lambda row: str(row["source_id"]))
        prior_group_source_ids = [str(row["source_id"]) for row in latest_group]
        if len(latest_group) != 1:
            signal_status = "NO_SIGNAL_AMBIGUOUS_PRIOR_TIMESTAMP"
        else:
            signal_status = "SIGNAL"
            prior_source = latest_group[0]
            prior_metrics = _metrics(prior_source)
            deltas = {
                "forward_commitment_density_delta": _delta(
                    current_metrics["forward_commitment_density_per_10k_chars"],
                    prior_metrics["forward_commitment_density_per_10k_chars"],
                ),
                "deadline_candidate_density_delta": _delta(
                    current_metrics["deadline_candidate_density_per_10k_chars"],
                    prior_metrics["deadline_candidate_density_per_10k_chars"],
                ),
                "domain_breadth_density_delta": _delta(
                    current_metrics["domain_breadth_density_per_10k_chars"],
                    prior_metrics["domain_breadth_density_per_10k_chars"],
                ),
                "deadline_share_delta": _delta(
                    current_metrics["deadline_share"], prior_metrics["deadline_share"]
                ),
            }
            primary_signal = deltas["forward_commitment_density_delta"]

    secondary_features = None
    if deltas is not None:
        secondary_features = {
            "deadline_candidate_density_delta": deltas[
                "deadline_candidate_density_delta"
            ],
            "operating_domain_breadth_density_delta": deltas[
                "domain_breadth_density_delta"
            ],
            "explicit_deadline_share_delta": deltas["deadline_share_delta"],
            "current_forward_commitment_density_level": current_metrics[
                "forward_commitment_density_per_10k_chars"
            ],
        }

    record: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "feature_version": FEATURE_VERSION,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "context_gate_sha256": context_gate["context_gate_sha256"],
        "source_id": current_source_id,
        "symbol": current_symbol,
        "exchange_published_at_utc": _utc_text(current_published),
        "source_record_id": current_record["record_id"],
        "raw_sha256": current_record["raw_sha256"],
        "text_sha256": current_record["text_sha256"],
        "source_disposition": "PROSPECTIVE_SIGNAL_ELIGIBLE",
        "prior_source_id": prior_source["source_id"] if prior_source else None,
        "prior_exchange_published_at_utc": (
            _utc_text(
                _timestamp(
                    prior_source["exchange_published_at_utc"],
                    field="prior.exchange_published_at_utc",
                )
            )
            if prior_source
            else None
        ),
        "prior_source_disposition": (
            source_disposition(prior_source) if prior_source else None
        ),
        "prior_group_source_ids": prior_group_source_ids,
        "current": current_metrics,
        "prior": prior_metrics,
        "primary_signal": primary_signal,
        "secondary_features": secondary_features,
        "deltas": deltas,
        "signal_status": signal_status,
        "signal_frozen_at_utc": _utc_text(frozen_at),
        "outcome_data_attached": False,
    }
    record["signal_record_sha256"] = _canonical_hash(record)
    validate_signal_record(record)
    return record


def new_signal_ledger() -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "hypothesis_id": HYPOTHESIS_ID,
        "cohort_id": COHORT_ID,
        "cohort_sha256": COHORT_SHA256,
        "outcome_data_attached": False,
        "record_count": 0,
        "records": [],
    }
    ledger["ledger_sha256"] = _canonical_hash(ledger)
    return ledger


def validate_signal_ledger(ledger: dict[str, Any]) -> None:
    if not isinstance(ledger, dict):
        raise H022ProspectiveError("P001 ledger must be an object")
    _reject_forbidden_keys(ledger)
    stored = ledger.get("ledger_sha256")
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    if not _is_sha256(stored) or stored != _canonical_hash(unsigned):
        raise H022ProspectiveError("P001 ledger digest mismatch")
    if (
        ledger.get("protocol_id") != PROTOCOL_ID
        or ledger.get("hypothesis_id") != HYPOTHESIS_ID
        or ledger.get("cohort_id") != COHORT_ID
        or ledger.get("cohort_sha256") != COHORT_SHA256
    ):
        raise H022ProspectiveError("P001 ledger identity changed")
    if ledger.get("outcome_data_attached") is not False:
        raise H022ProspectiveError("P001 ledger contains outcomes")
    records = ledger.get("records")
    if not isinstance(records, list) or ledger.get("record_count") != len(records):
        raise H022ProspectiveError("P001 ledger record count mismatch")
    seen: set[str] = set()
    for record in records:
        validate_signal_record(record)
        source_id = str(record["source_id"])
        if source_id in seen:
            raise H022ProspectiveError(f"duplicate P001 ledger source: {source_id}")
        seen.add(source_id)


def append_signal_record(
    ledger: dict[str, Any], signal_record: dict[str, Any]
) -> dict[str, Any]:
    validate_signal_ledger(ledger)
    validate_signal_record(signal_record)
    records = [dict(row) for row in ledger["records"]]
    source_id = str(signal_record["source_id"])
    existing = next((row for row in records if row["source_id"] == source_id), None)
    if existing is not None:
        if existing.get("signal_record_sha256") == signal_record.get("signal_record_sha256"):
            return ledger
        raise H022ProspectiveError(
            f"P001 source {source_id} already exists with different immutable bytes"
        )
    records.append(dict(signal_record))
    records.sort(
        key=lambda row: (
            str(row["exchange_published_at_utc"]),
            str(row["symbol"]),
            str(row["source_id"]),
        )
    )
    updated = dict(ledger)
    updated["records"] = records
    updated["record_count"] = len(records)
    updated.pop("ledger_sha256", None)
    updated["ledger_sha256"] = _canonical_hash(updated)
    validate_signal_ledger(updated)
    return updated
