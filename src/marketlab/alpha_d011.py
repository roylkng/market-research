from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.h023_ownership import previous_quarter_end

D011_ID = "AE001-D011-v1"
D011_SAMPLE_RANKS = (
    1, 5, 9, 13, 17, 21, 25, 29, 33, 37,
    41, 45, 49, 53, 57, 61, 65, 69, 73, 77,
    81, 85, 89, 93, 97,
)
D011_REPORT_DATES = (
    "2024-03-31",
    "2024-06-30",
    "2024-09-30",
    "2024-12-31",
    "2025-03-31",
    "2025-06-30",
    "2025-09-30",
    "2025-12-31",
    "2026-03-31",
    "2026-06-30",
)
CURRENT_SOURCE_COVERAGE_MIN = 0.90
CURRENT_PARSE_READY_COVERAGE_MIN = 0.90
ADJACENT_PAIR_READY_COVERAGE_MIN = 0.80


def sample_symbols(universe: dict[str, Any]) -> tuple[str, ...]:
    members = universe.get("members")
    if not isinstance(members, list):
        raise AlphaContractError("D011 universe members are missing")
    by_rank = {}
    for row in members:
        if not isinstance(row, dict):
            continue
        rank = row.get("rank")
        symbol = str(row.get("symbol") or "").strip().upper()
        if isinstance(rank, int) and symbol:
            if rank in by_rank:
                raise AlphaContractError(f"D011 duplicate universe rank: {rank}")
            by_rank[rank] = symbol
    missing = [rank for rank in D011_SAMPLE_RANKS if rank not in by_rank]
    if missing:
        raise AlphaContractError(
            f"D011 sample ranks missing from frozen universe: {missing}"
        )
    symbols = tuple(by_rank[rank] for rank in D011_SAMPLE_RANKS)
    if len(set(symbols)) != len(symbols):
        raise AlphaContractError("D011 sampled symbols are not unique")
    return symbols


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AlphaContractError(f"D011 invalid timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise AlphaContractError("D011 timestamp must be timezone-aware")
    return parsed


def _sources_for_date(
    sources: list[dict[str, Any]],
    *,
    report_date: str,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in sources
        if str(row.get("report_date") or "") == report_date
    ]
    rows.sort(
        key=lambda row: (
            _timestamp(str(row["broadcast_at_utc"])),
            str(row["record_id"]),
        )
    )
    return rows


def first_current_source(
    sources: list[dict[str, Any]],
    *,
    report_date: str,
) -> tuple[dict[str, Any] | None, bool]:
    rows = _sources_for_date(sources, report_date=report_date)
    if not rows:
        return None, False
    first_time = _timestamp(str(rows[0]["broadcast_at_utc"]))
    tied = [
        row
        for row in rows
        if _timestamp(str(row["broadcast_at_utc"])) == first_time
    ]
    if len(tied) != 1:
        return None, True
    return dict(tied[0]), False


def prior_source_at_current_broadcast(
    sources: list[dict[str, Any]],
    *,
    current_report_date: str,
    current_broadcast_at_utc: str,
) -> tuple[dict[str, Any] | None, bool]:
    prior_date = previous_quarter_end(current_report_date)
    cutoff = _timestamp(current_broadcast_at_utc)
    rows = [
        row
        for row in _sources_for_date(sources, report_date=prior_date)
        if _timestamp(str(row["broadcast_at_utc"])) <= cutoff
    ]
    if not rows:
        return None, False
    latest_time = _timestamp(str(rows[-1]["broadcast_at_utc"]))
    tied = [
        row
        for row in rows
        if _timestamp(str(row["broadcast_at_utc"])) == latest_time
    ]
    if len(tied) != 1:
        return None, True
    return dict(tied[0]), False


def _semantic_drift_error(error: object) -> bool:
    text = str(error or "").casefold()
    markers = (
        "unexpected mutual fund",
        "expected one exact mutual fund context",
        "expected one mutual fund shareholding fact",
    )
    return any(marker in text for marker in markers)


def build_d011_result(
    *,
    universe: dict[str, Any],
    master_status_by_symbol: dict[str, dict[str, Any]],
    sources_by_symbol: dict[str, list[dict[str, Any]]],
    evidence_by_source_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    symbols = sample_symbols(universe)
    if set(master_status_by_symbol) != set(symbols):
        raise AlphaContractError(
            "D011 master status does not exactly cover frozen sample"
        )
    if set(sources_by_symbol) != set(symbols):
        raise AlphaContractError(
            "D011 source map does not exactly cover frozen sample"
        )

    expected_current = len(symbols) * len(D011_REPORT_DATES)
    target_current_dates = D011_REPORT_DATES[1:]
    expected_pairs = len(symbols) * len(target_current_dates)

    current_found = 0
    current_ready = 0
    pair_source_found = 0
    pair_ready = 0
    ambiguity_count = 0
    semantic_drift_count = 0
    selected_source_ids: set[str] = set()
    earliest_broadcast: datetime | None = None
    latest_broadcast: datetime | None = None
    reason_counts: Counter[str] = Counter()
    observations = []

    for symbol in symbols:
        sources = sources_by_symbol[symbol]
        for report_date in D011_REPORT_DATES:
            current, current_ambiguous = first_current_source(
                sources,
                report_date=report_date,
            )
            if current_ambiguous:
                ambiguity_count += 1
                reason_counts["CURRENT_SOURCE_AMBIGUOUS"] += 1
                current = None
            current_evidence = None
            if current is not None:
                current_found += 1
                source_id = str(current["source_id"])
                selected_source_ids.add(source_id)
                broadcast = _timestamp(str(current["broadcast_at_utc"]))
                earliest_broadcast = (
                    broadcast
                    if earliest_broadcast is None
                    else min(earliest_broadcast, broadcast)
                )
                latest_broadcast = (
                    broadcast
                    if latest_broadcast is None
                    else max(latest_broadcast, broadcast)
                )
                current_evidence = evidence_by_source_id.get(source_id)
                if (
                    isinstance(current_evidence, dict)
                    and current_evidence.get("status") == "READY"
                ):
                    current_ready += 1
                else:
                    reason = str(
                        (current_evidence or {}).get("status")
                        or "CURRENT_EVIDENCE_MISSING"
                    )
                    reason_counts[reason] += 1
                    if _semantic_drift_error(
                        (current_evidence or {}).get("error")
                    ):
                        semantic_drift_count += 1
            else:
                if not current_ambiguous:
                    reason_counts["CURRENT_SOURCE_MISSING"] += 1

            prior = None
            prior_evidence = None
            prior_ambiguous = False
            if report_date in target_current_dates and current is not None:
                prior, prior_ambiguous = prior_source_at_current_broadcast(
                    sources,
                    current_report_date=report_date,
                    current_broadcast_at_utc=str(
                        current["broadcast_at_utc"]
                    ),
                )
                if prior_ambiguous:
                    ambiguity_count += 1
                    reason_counts["PRIOR_SOURCE_AMBIGUOUS"] += 1
                    prior = None
                if prior is not None:
                    pair_source_found += 1
                    prior_id = str(prior["source_id"])
                    selected_source_ids.add(prior_id)
                    prior_evidence = evidence_by_source_id.get(prior_id)
                    current_ok = (
                        isinstance(current_evidence, dict)
                        and current_evidence.get("status") == "READY"
                    )
                    prior_ok = (
                        isinstance(prior_evidence, dict)
                        and prior_evidence.get("status") == "READY"
                    )
                    if current_ok and prior_ok:
                        pair_ready += 1
                    else:
                        if not prior_ok:
                            reason = str(
                                (prior_evidence or {}).get("status")
                                or "PRIOR_EVIDENCE_MISSING"
                            )
                            reason_counts[reason] += 1
                            if _semantic_drift_error(
                                (prior_evidence or {}).get("error")
                            ):
                                semantic_drift_count += 1
                elif not prior_ambiguous:
                    reason_counts["PRIOR_SOURCE_MISSING_AT_CURRENT_TIME"] += 1

            observations.append(
                {
                    "symbol": symbol,
                    "report_date": report_date,
                    "current_source_id": (
                        None if current is None else current["source_id"]
                    ),
                    "current_evidence_status": (
                        None
                        if current_evidence is None
                        else current_evidence.get("status")
                    ),
                    "prior_source_id": (
                        None if prior is None else prior["source_id"]
                    ),
                    "prior_evidence_status": (
                        None
                        if prior_evidence is None
                        else prior_evidence.get("status")
                    ),
                }
            )

    master_ready = sum(
        status.get("status") == "READY"
        for status in master_status_by_symbol.values()
    )
    current_source_coverage = current_found / expected_current
    current_ready_coverage = current_ready / expected_current
    pair_source_coverage = pair_source_found / expected_pairs
    pair_ready_coverage = pair_ready / expected_pairs

    passed = (
        master_ready == len(symbols)
        and current_source_coverage >= CURRENT_SOURCE_COVERAGE_MIN
        and current_ready_coverage >= CURRENT_PARSE_READY_COVERAGE_MIN
        and pair_ready_coverage >= ADJACENT_PAIR_READY_COVERAGE_MIN
        and ambiguity_count == 0
        and semantic_drift_count == 0
    )

    result: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": D011_ID,
        "status": (
            "PASS_SOURCE_FEASIBILITY"
            if passed
            else "FAIL_SOURCE_FEASIBILITY"
        ),
        "evidence_class": "SOURCE_FEASIBILITY_NO_RETURN_OUTCOMES",
        "sample_symbol_count": len(symbols),
        "sample_symbols": list(symbols),
        "report_dates": list(D011_REPORT_DATES),
        "expected_symbol_quarter_count": expected_current,
        "expected_adjacent_pair_count": expected_pairs,
        "master_ready_symbol_count": master_ready,
        "current_source_count": current_found,
        "current_source_coverage": current_source_coverage,
        "current_parse_ready_count": current_ready,
        "current_parse_ready_coverage": current_ready_coverage,
        "adjacent_pair_source_count": pair_source_found,
        "adjacent_pair_source_coverage": pair_source_coverage,
        "adjacent_pair_parse_ready_count": pair_ready,
        "adjacent_pair_parse_ready_coverage": pair_ready_coverage,
        "selected_unique_source_count": len(selected_source_ids),
        "source_ambiguity_count": ambiguity_count,
        "semantic_drift_count": semantic_drift_count,
        "reason_counts": dict(sorted(reason_counts.items())),
        "earliest_selected_broadcast_at_utc": (
            None
            if earliest_broadcast is None
            else earliest_broadcast.isoformat()
        ),
        "latest_selected_broadcast_at_utc": (
            None
            if latest_broadcast is None
            else latest_broadcast.isoformat()
        ),
        "promotion_gates": {
            "all_sample_master_responses_ready": (
                master_ready == len(symbols)
            ),
            "current_source_coverage_min": CURRENT_SOURCE_COVERAGE_MIN,
            "current_source_coverage_pass": (
                current_source_coverage >= CURRENT_SOURCE_COVERAGE_MIN
            ),
            "current_parse_ready_coverage_min": (
                CURRENT_PARSE_READY_COVERAGE_MIN
            ),
            "current_parse_ready_coverage_pass": (
                current_ready_coverage >= CURRENT_PARSE_READY_COVERAGE_MIN
            ),
            "adjacent_pair_parse_ready_coverage_min": (
                ADJACENT_PAIR_READY_COVERAGE_MIN
            ),
            "adjacent_pair_parse_ready_coverage_pass": (
                pair_ready_coverage >= ADJACENT_PAIR_READY_COVERAGE_MIN
            ),
            "no_source_ambiguity": ambiguity_count == 0,
            "no_semantic_drift": semantic_drift_count == 0,
        },
        "observations": observations,
        "return_labels_opened": False,
        "model_fit_performed": False,
        "may_authorize_new_trial_design": passed,
        "may_authorize_returns": False,
        "may_promote_to_ab001": False,
        "live_capital_allowed": False,
    }
    result["result_sha256"] = digest(result)
    return result
