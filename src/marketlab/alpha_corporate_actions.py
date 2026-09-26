from __future__ import annotations

import json
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

SHARE_CHANGING_ACTION_TOKENS = (
    "bonus",
    "split",
    "sub-division",
    "subdivision",
    "consolidation",
    "rights",
    "demerger",
    "spin-off",
    "spin off",
    "reduction of capital",
    "scheme of arrangement",
    "merger",
    "amalgamation",
)

ACTION_LEDGER_ID = "AE001-CORPORATE-ACTIONS-v1"


def _action_rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "records"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
        return []
    return []


def _parse_action_date(value: object) -> date:
    if not isinstance(value, str):
        raise AlphaContractError("corporate-action ex-date is required")
    raw = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = time.strptime(raw, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    raise AlphaContractError(f"unsupported corporate-action ex-date: {value}")


def is_share_changing_action(subject: str) -> bool:
    text = subject.casefold()
    return any(token in text for token in SHARE_CHANGING_ACTION_TOKENS)


def parse_share_changing_actions(payload: object) -> dict[str, dict[str, Any]]:
    """Parse only actions capable of breaking raw-price comparability."""

    grouped: dict[str, dict[str, Any]] = {}
    for row in _action_rows(payload):
        series = str(row.get("series") or row.get("Series") or "").strip().upper()
        if series and series != "EQ":
            continue
        subject = str(
            row.get("subject")
            or row.get("purpose")
            or row.get("Purpose")
            or ""
        ).strip()
        if not subject or not is_share_changing_action(subject):
            continue
        symbol = str(
            row.get("symbol")
            or row.get("SYMBOL")
            or row.get("Symbol")
            or ""
        ).strip().upper()
        if not symbol:
            raise AlphaContractError(
                "share-changing corporate action lacks symbol"
            )
        state = grouped.setdefault(
            symbol,
            {
                "symbol": symbol,
                "status": "READY",
                "actions": [],
                "unresolved_subjects": [],
            },
        )
        raw_date = (
            row.get("exDate")
            or row.get("ex_date")
            or row.get("EX-DATE")
            or row.get("exDateStr")
        )
        try:
            action_date = _parse_action_date(raw_date)
        except AlphaContractError:
            state["status"] = "UNRESOLVED"
            state["unresolved_subjects"].append(subject)
            continue
        state["actions"].append(
            {
                "ex_date": action_date.isoformat(),
                "subject": subject,
            }
        )

    for state in grouped.values():
        unique = {
            (row["ex_date"], row["subject"]): row
            for row in state["actions"]
        }
        state["actions"] = [
            unique[key]
            for key in sorted(unique)
        ]
        state["unresolved_subjects"] = sorted(
            set(state["unresolved_subjects"])
        )
    return grouped


CorporateActionFetcher = Callable[
    [str, str], tuple[object, bytes, str]
]


def date_chunks(
    start_date: date,
    end_date: date,
    *,
    chunk_days: int = 60,
) -> list[tuple[date, date]]:
    if start_date > end_date:
        raise AlphaContractError("corporate-action start exceeds end")
    if chunk_days < 1:
        raise AlphaContractError("corporate-action chunk_days must be positive")
    chunks = []
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(
            end_date,
            cursor + timedelta(days=chunk_days - 1),
        )
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def acquire_corporate_action_ledger(
    *,
    start_date: date,
    end_date: date,
    fetcher: CorporateActionFetcher,
    raw_dir: str | Path | None = None,
    chunk_days: int = 60,
) -> dict[str, Any]:
    raw_root = Path(raw_dir) if raw_dir is not None else None
    sources = []
    combined: dict[str, dict[str, Any]] = {}

    for start, end in date_chunks(
        start_date,
        end_date,
        chunk_days=chunk_days,
    ):
        from_text = start.strftime("%d-%m-%Y")
        to_text = end.strftime("%d-%m-%Y")
        payload, raw, source_url = fetcher(from_text, to_text)
        if not raw:
            raise AlphaContractError(
                f"empty corporate-action evidence for {from_text}:{to_text}"
            )
        raw_sha = sha256_bytes(raw)
        if raw_root is not None:
            raw_root.mkdir(parents=True, exist_ok=True)
            path = raw_root / f"{start.isoformat()}_{end.isoformat()}_{raw_sha}.json"
            if path.exists() and path.read_bytes() != raw:
                raise AlphaContractError(
                    f"corporate-action raw path collision: {path}"
                )
            path.write_bytes(raw)

        parsed = parse_share_changing_actions(payload)
        for symbol, state in parsed.items():
            merged = combined.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "status": "READY",
                    "actions": [],
                    "unresolved_subjects": [],
                },
            )
            if state["status"] != "READY":
                merged["status"] = "UNRESOLVED"
            merged["actions"].extend(state["actions"])
            merged["unresolved_subjects"].extend(
                state["unresolved_subjects"]
            )

        sources.append(
            {
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "source_url": source_url,
                "raw_sha256": raw_sha,
            }
        )

    records = []
    for symbol in sorted(combined):
        state = combined[symbol]
        unique = {
            (row["ex_date"], row["subject"]): row
            for row in state["actions"]
        }
        state["actions"] = [
            unique[key]
            for key in sorted(unique)
        ]
        state["unresolved_subjects"] = sorted(
            set(state["unresolved_subjects"])
        )
        records.append(state)

    ledger = {
        "schema_version": 1,
        "ledger_id": ACTION_LEDGER_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "coverage_start_date": start_date.isoformat(),
        "coverage_end_date": end_date.isoformat(),
        "source_chunks": sources,
        "record_count": len(records),
        "records": records,
        "no_record_means_no_share_changing_action_in_covered_source": True,
        "historical_source_retrieved_prospectively": False,
        "live_capital_allowed": False,
    }
    ledger["ledger_sha256"] = digest(ledger)
    return ledger


def validate_action_ledger(ledger: dict[str, Any]) -> None:
    stored = str(ledger.get("ledger_sha256") or "")
    unsigned = dict(ledger)
    unsigned.pop("ledger_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("corporate-action ledger hash mismatch")
    if ledger.get("ledger_id") != ACTION_LEDGER_ID:
        raise AlphaContractError("unexpected corporate-action ledger id")
    if ledger.get("live_capital_allowed") is not False:
        raise AlphaContractError("corporate-action ledger cannot allow live capital")


def action_index(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    validate_action_ledger(ledger)
    result = {}
    for row in ledger.get("records", []):
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in result:
            raise AlphaContractError(
                "corporate-action records require unique symbols"
            )
        result[symbol] = row
    return result


def blocked_actions(
    index: dict[str, dict[str, Any]],
    *,
    symbol: str,
    start_exclusive: str,
    end_inclusive: str,
) -> tuple[dict[str, str], ...]:
    state = index.get(symbol.upper())
    if state is None:
        return ()
    if state.get("status") != "READY":
        raise AlphaContractError(
            f"{symbol}: corporate-action audit unresolved"
        )
    start = date.fromisoformat(start_exclusive)
    end = date.fromisoformat(end_inclusive)
    if end < start:
        raise AlphaContractError("corporate-action window is reversed")
    return tuple(
        row
        for row in state.get("actions", [])
        if start < date.fromisoformat(str(row["ex_date"])) <= end
    )


def filter_feature_panel_for_corporate_actions(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    action_ledger: dict[str, Any],
    lookback_sessions: int = 60,
) -> dict[str, Any]:
    """Remove rows whose raw-price feature lookback crosses a share-changing action."""

    if lookback_sessions < 1:
        raise AlphaContractError("feature action lookback must be positive")
    validate_action_ledger(action_ledger)
    sessions = market_panel.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        raise AlphaContractError("market panel sessions are required")
    dates = [str(row["session_date"]) for row in sessions]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise AlphaContractError("market panel sessions are not canonical")
    index_by_date = {value: idx for idx, value in enumerate(dates)}

    coverage_start = date.fromisoformat(
        str(action_ledger["coverage_start_date"])
    )
    coverage_end = date.fromisoformat(
        str(action_ledger["coverage_end_date"])
    )
    if coverage_start > date.fromisoformat(dates[0]):
        raise AlphaContractError(
            "corporate-action coverage begins after market panel"
        )
    action_by_symbol = action_index(action_ledger)

    rows = feature_panel.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("feature panel rows must be a list")

    kept_by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
    blocked_count = 0
    unresolved_count = 0
    for row in rows:
        session = str(row["feature_session"])
        position = index_by_date.get(session)
        if position is None or position < lookback_sessions:
            raise AlphaContractError(
                f"{session}: feature session lacks action lookback"
            )
        if date.fromisoformat(session) > coverage_end:
            raise AlphaContractError(
                f"{session}: corporate-action coverage is insufficient"
            )
        start = dates[position - lookback_sessions]
        state = action_by_symbol.get(str(row["symbol"]).upper())
        if state is not None and state.get("status") != "READY":
            unresolved_count += 1
            continue
        actions = blocked_actions(
            action_by_symbol,
            symbol=str(row["symbol"]),
            start_exclusive=start,
            end_inclusive=session,
        )
        if actions:
            blocked_count += 1
            continue
        kept_by_session[session].append(dict(row))

    new_rows = []
    session_summary = []
    for session in dates:
        current = sorted(
            kept_by_session.get(session, []),
            key=lambda row: (str(row["symbol"]), str(row["isin"])),
        )
        if not current:
            continue
        universe_sha = digest(
            [
                {"symbol": row["symbol"], "isin": row["isin"]}
                for row in current
            ]
        )
        for row in current:
            row["universe_sha256"] = universe_sha
            new_rows.append(row)
        session_summary.append(
            {
                "session_date": session,
                "eligible_count": len(current),
                "universe_sha256": universe_sha,
            }
        )

    transformed = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key not in {
                "rows",
                "sessions",
                "panel_sha256",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-HISTORICAL-PRICE-VOLUME-ACTION-SAFE-v1",
        "corporate_action_ledger_sha256": action_ledger[
            "ledger_sha256"
        ],
        "corporate_action_feature_policy": (
            "EXCLUDE_IF_SHARE_CHANGING_EX_DATE_OCCURS_AFTER_60_SESSION_"
            "LOOKBACK_START_AND_ON_OR_BEFORE_FEATURE_SESSION"
        ),
        "corporate_action_blocked_feature_row_count": blocked_count,
        "corporate_action_unresolved_feature_row_count": unresolved_count,
        "session_count": len(session_summary),
        "feature_row_count": len(new_rows),
        "sessions": session_summary,
        "rows": new_rows,
    }
    transformed["panel_sha256"] = digest(transformed)
    return transformed


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
