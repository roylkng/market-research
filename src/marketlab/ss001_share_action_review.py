from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest

AUDIT_ID = "SS001-D006-v1"
PRICE_SESSION = date(2026, 10, 1)
CUTOFF = datetime.fromisoformat("2026-10-01T13:00:00+00:00")
IST = ZoneInfo("Asia/Kolkata")

SOURCE_IDS = {
    "d001": ("census_id", "SS001-D001-v1", "census_sha256", "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"),
    "d005": ("audit_id", "SS001-D005-v1", "audit_sha256", "b5fe97c3a9e83e8acbfce9cddf4eed476d60c29ca5125caa400368b4f5c7e984"),
    "p2": ("census_id", "SS002-D001-P2-v1", "census_sha256", "ad2722cf2d3605614ae892636f35e44759ec42e5951b4680f0ed270bd1b51071"),
}
ACTION_TOKENS = (
    "bonus", "rights", "split", "sub-division", "sub division",
    "consolidat", "demerg", "merg", "scheme", "buyback", "buy back",
    "capital reduction", "conversion", "warrant", "allotment",
)
ANNOUNCEMENT_FAMILIES = frozenset(
    {
        "RIGHTS_ISSUE", "PREFERENTIAL_WARRANT", "SCHEME_REORGANISATION",
        "CAPITAL_REDUCTION", "BUYBACK", "INSOLVENCY_RESOLUTION",
    }
)


def _check_source(payload: dict[str, Any], label: str) -> None:
    id_key, id_value, sha_key, sha_value = SOURCE_IDS[label]
    if payload.get(id_key) != id_value or payload.get(sha_key) != sha_value:
        raise AlphaContractError(f"D006 frozen {label} source identity mismatch")
    for field in ("return_outcomes_opened", "model_fitted", "portfolio_eligibility_allowed", "live_capital_allowed"):
        if payload.get(field) is not False:
            raise AlphaContractError(f"D006 {label} {field} must be false")


def _rows_by_symbol(payload: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != 2319:
        raise AlphaContractError(f"D006 {label} requires 2319 rows")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError(f"D006 {label} row must be an object")
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol or symbol in result:
            raise AlphaContractError(f"D006 {label} duplicate/invalid symbols")
        result[symbol] = row
    return result


def _date(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC).date()
        except ValueError:
            pass
    return None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def parse_frozen_corporate_actions(
    d001_census: dict[str, Any],
    *,
    raw_by_sha: dict[str, bytes],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    _check_source(d001_census, "d001")
    meta = d001_census.get("source_metadata")
    if not isinstance(meta, dict):
        raise AlphaContractError("D006 D001 source metadata unavailable")
    action_window = meta.get("corporate_action_window")
    if not isinstance(action_window, dict):
        raise AlphaContractError("D006 corporate action window missing")
    if action_window.get("from_date") != "2025-10-05" or action_window.get("to_date") != "2026-10-04":
        raise AlphaContractError("D006 corporate action window changed")
    chunks = action_window.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != 7:
        raise AlphaContractError("D006 requires exactly 7 frozen action chunks")

    wanted = {chunk.get("raw_sha256") for chunk in chunks if isinstance(chunk, dict)}
    if len(wanted) != 7 or set(raw_by_sha) != wanted:
        raise AlphaContractError("D006 corporate action source hash accounting mismatch")
    equity_rows = []
    raw_count = 0
    for chunk in chunks:
        sha = chunk["raw_sha256"]
        raw = raw_by_sha[sha]
        if hashlib.sha256(raw).hexdigest() != sha:
            raise AlphaContractError("D006 corporate action raw SHA mismatch")
        try:
            obj = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise AlphaContractError("D006 corporate action source is not JSON") from exc
        source_rows = obj if isinstance(obj, list) else obj.get("data") if isinstance(obj, dict) else None
        if not isinstance(source_rows, list) or len(source_rows) != chunk.get("row_count"):
            raise AlphaContractError("D006 corporate action chunk row count mismatch")
        raw_count += len(source_rows)
        for row in source_rows:
            if not isinstance(row, dict):
                raise TypeError("D006 corporate action row must be an object")
            if str(row.get("series") or "").strip().upper() != "EQ":
                continue
            ex_date = _date(row.get("exDate"))
            if ex_date is None:
                raise AlphaContractError("D006 EQ corporate action ex-date unavailable")
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol:
                raise AlphaContractError("D006 EQ action symbol is unavailable")
            subject = str(row.get("subject") or "")
            equity_rows.append(
                {
                    "symbol": symbol,
                    "isin": str(row.get("isin") or "").strip(),
                    "ex_date": ex_date.isoformat(),
                    "subject": subject,
                    "candidate_capital_change": any(token in subject.casefold() for token in ACTION_TOKENS),
                    "source_raw_sha256": sha,
                }
            )
    if raw_count != d001_census.get("corporate_action_row_count"):
        raise AlphaContractError("D006 D001 raw corporate-action total mismatch")
    return equity_rows, {"raw_row_count": raw_count, "eq_row_count": len(equity_rows), "chunk_count": 7}


def _announcement_rows(p2: dict[str, Any], market_symbols: set[str]) -> list[dict[str, Any]]:
    _check_source(p2, "p2")
    rows = p2.get("events")
    if not isinstance(rows, list) or len(rows) != 2272:
        raise AlphaContractError("D006 P2 requires 2272 canonical events")
    seen_ids = set()
    current = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("D006 P2 event must be an object")
        identifier = row.get("announcement_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen_ids:
            raise AlphaContractError("D006 P2 event IDs must be unique")
        seen_ids.add(identifier)
        if row.get("mapping_state") != "CURRENT_INVESTABLE_IDENTITY":
            continue
        symbol = row.get("symbol")
        if symbol not in market_symbols:
            raise AlphaContractError("D006 P2 current symbol not in D001")
        published = _timestamp(row.get("exchange_published_at_utc"))
        if published is None:
            raise AlphaContractError("D006 P2 current event publication unavailable")
        categories = row.get("special_situation_categories")
        if not isinstance(categories, list):
            raise AlphaContractError("D006 P2 categories unavailable")
        current.append(
            {
                "symbol": symbol,
                "event_id": identifier,
                "publication_utc": published,
                "categories": tuple(categories),
                "is_capital_change_candidate": bool(ANNOUNCEMENT_FAMILIES.intersection(categories)),
            }
        )
    if len(current) != 1666:
        raise AlphaContractError("D006 P2 current-event accounting mismatch")
    return current


def build_share_action_review(
    *,
    d005_panel: dict[str, Any],
    d001_census: dict[str, Any],
    p2_census: dict[str, Any],
    raw_action_chunks: dict[str, bytes],
) -> dict[str, Any]:
    for label, payload in (("d005", d005_panel), ("d001", d001_census), ("p2", p2_census)):
        _check_source(payload, label)
    ready_source = _rows_by_symbol(d005_panel, "d005")
    market = _rows_by_symbol(d001_census, "d001")
    if set(ready_source) != set(market):
        raise AlphaContractError("D006 D005/D001 identity population differs")
    if d005_panel.get("time_and_price_ready_count") != 1960:
        raise AlphaContractError("D006 D005 ready population changed")

    action_rows, action_stats = parse_frozen_corporate_actions(
        d001_census, raw_by_sha=raw_action_chunks
    )
    announcements = _announcement_rows(p2_census, set(market))
    actions_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    announcements_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in action_rows:
        actions_by_symbol[row["symbol"]].append(row)
    for row in announcements:
        announcements_by_symbol[row["symbol"]].append(row)

    results = []
    states: Counter[str] = Counter()
    total_ready = 0
    for symbol in sorted(ready_source):
        source = ready_source[symbol]
        if source.get("source_readiness_state") != "TIME_AND_PRICE_READY":
            state = "D005_SOURCE_NOT_READY"
            relevant_actions: list[dict[str, Any]] = []
            relevant_announcements: list[dict[str, Any]] = []
        else:
            total_ready += 1
            report_date = _date(source.get("report_date"))
            if report_date is None or report_date > PRICE_SESSION:
                raise AlphaContractError("D006 invalid D005 READY report date")
            relevant_actions = [
                row
                for row in actions_by_symbol.get(symbol, [])
                if row["candidate_capital_change"]
                and report_date < date.fromisoformat(row["ex_date"]) <= PRICE_SESSION
            ]
            relevant_announcements = [
                row
                for row in announcements_by_symbol.get(symbol, [])
                if row["is_capital_change_candidate"]
                and report_date < row["publication_utc"].astimezone(IST).date()
                and row["publication_utc"] <= CUTOFF
            ]
            if relevant_actions and relevant_announcements:
                state = "BOTH_SOURCES_REVIEW_REQUIRED"
            elif relevant_actions:
                state = "CORPORATE_ACTION_REVIEW_REQUIRED"
            elif relevant_announcements:
                state = "ANNOUNCEMENT_REVIEW_REQUIRED"
            else:
                state = "NO_OBSERVED_TRIGGER_STILL_UNVERIFIED"
        states[state] += 1
        results.append(
            {
                "symbol": symbol,
                "source_readiness_state": source.get("source_readiness_state"),
                "review_state": state,
                "intervening_corporate_actions": sorted(
                    relevant_actions,
                    key=lambda item: (item["ex_date"], item["subject"]),
                ),
                "intervening_announcement_candidates": [
                    {
                        "event_id": row["event_id"],
                        "published_at_utc": row["publication_utc"].isoformat().replace("+00:00", "Z"),
                        "categories": list(row["categories"]),
                    }
                    for row in sorted(relevant_announcements, key=lambda r: (r["publication_utc"], r["event_id"]))
                ],
                "share_action_clearance_proven": False,
                "capitalization_calculation_allowed": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )
    if total_ready != 1960:
        raise AlphaContractError("D006 ready identity count differs from D005")

    gates = {
        "complete_2319_source_accounting": len(results) == 2319,
        "exact_1960_ready_source_accounting": total_ready == 1960,
        "all_7_corporate_action_chunks_verified": action_stats["chunk_count"] == 7,
        "every_eq_corporate_action_date_parsed": action_stats["eq_row_count"] > 0,
        "all_1666_current_p2_events_accounted": len(announcements) == 1666,
        "no_automatic_clearance_or_capitalization": True,
    }
    output = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "DATED_SHARE_CHANGE_REVIEW_QUEUE_NOT_CLEARANCE",
        "price_session": PRICE_SESSION.isoformat(),
        "publication_cutoff_utc": CUTOFF.isoformat().replace("+00:00", "Z"),
        "source_sha256": {k: SOURCE_IDS[k][3] for k in sorted(SOURCE_IDS)},
        "identity_count": 2319,
        "d005_time_and_price_ready_count": total_ready,
        "raw_corporate_action_source": action_stats,
        "p2_current_event_count": len(announcements),
        "review_state_counts": dict(sorted(states.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_d007_document_adjudication": all(gates.values()),
        "share_action_clearance_proven": False,
        "market_capitalization_calculated": False,
        "rows": results,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["audit_sha256"] = digest(output)
    return output
