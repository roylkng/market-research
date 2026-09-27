from __future__ import annotations

from datetime import date, datetime
from typing import Any

from marketlab.alpha import AlphaContractError, digest

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


def _parse_date(value: object) -> date:
    if not isinstance(value, str) or not value.strip():
        raise AlphaContractError("corporate-action ex-date is required")
    raw = value.strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise AlphaContractError(f"unsupported corporate-action ex-date: {value}")


def _rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        candidate = payload.get("data") or payload.get("records") or []
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]
    return []


def build_share_action_panel(
    payload: object,
    *,
    start_date: date,
    end_date: date,
    source_url: str,
    raw_sha256: str,
) -> dict[str, Any]:
    """Normalize only share-basis-changing NSE equity corporate actions.

    Dividends are intentionally ignored because AE001 v1 uses raw price features.
    Share-changing events are not adjusted retrospectively. Feature rows whose
    raw-price lookback crosses such an event are excluded instead.
    """

    if start_date > end_date:
        raise AlphaContractError("corporate-action start date exceeds end date")
    if not source_url.startswith("https://"):
        raise AlphaContractError("corporate-action source URL must be HTTPS")
    if len(raw_sha256) != 64:
        raise AlphaContractError("corporate-action raw SHA-256 is required")

    actions_by_symbol: dict[str, list[dict[str, str]]] = {}
    unresolved_by_symbol: dict[str, list[str]] = {}
    raw_rows = _rows(payload)
    relevant_rows = 0

    for row in raw_rows:
        subject = str(row.get("subject") or row.get("purpose") or "").strip()
        if not subject or not any(
            token in subject.casefold() for token in SHARE_CHANGING_ACTION_TOKENS
        ):
            continue
        relevant_rows += 1
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise AlphaContractError(
                "share-changing corporate-action row is missing symbol"
            )
        series = str(row.get("series") or "").strip().upper()
        if series and series != "EQ":
            continue
        raw_date = row.get("exDate") or row.get("ex_date")
        try:
            ex_date = _parse_date(raw_date)
        except AlphaContractError:
            unresolved_by_symbol.setdefault(symbol, []).append(subject)
            continue
        if not start_date <= ex_date <= end_date:
            continue
        actions_by_symbol.setdefault(symbol, []).append(
            {
                "ex_date": ex_date.isoformat(),
                "subject": subject,
                "series": series or "EQ",
            }
        )

    for symbol in actions_by_symbol:
        actions_by_symbol[symbol].sort(
            key=lambda row: (row["ex_date"], row["subject"])
        )
    for symbol in unresolved_by_symbol:
        unresolved_by_symbol[symbol] = sorted(set(unresolved_by_symbol[symbol]))

    panel: dict[str, Any] = {
        "schema_version": 1,
        "panel_id": "AE001-SHARE-ACTIONS-v1",
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "source_url": source_url,
        "raw_sha256": raw_sha256,
        "raw_record_count": len(raw_rows),
        "share_changing_record_count": relevant_rows,
        "actions_by_symbol": dict(sorted(actions_by_symbol.items())),
        "unresolved_by_symbol": dict(sorted(unresolved_by_symbol.items())),
        "historical_source_retrieved_prospectively": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def action_window_status(
    panel: dict[str, Any],
    *,
    symbol: str,
    start_session: str,
    end_session: str,
) -> tuple[str, tuple[dict[str, str], ...]]:
    """Classify whether a raw-price feature window is safe from share-basis changes."""

    stored = str(panel.get("panel_sha256") or "")
    unsigned = dict(panel)
    unsigned.pop("panel_sha256", None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError("share-action panel hash mismatch")

    wanted = symbol.strip().upper()
    if wanted in (panel.get("unresolved_by_symbol") or {}):
        return "UNRESOLVED", ()
    start = date.fromisoformat(start_session)
    end = date.fromisoformat(end_session)
    if end < start:
        raise AlphaContractError("share-action feature window is reversed")
    blockers = tuple(
        row
        for row in (panel.get("actions_by_symbol") or {}).get(wanted, [])
        if start < date.fromisoformat(str(row["ex_date"])) <= end
    )
    return ("BLOCKED" if blockers else "READY"), blockers
