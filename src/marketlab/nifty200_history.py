from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import yaml


class Nifty200HistoryError(ValueError):
    """Raised when point-in-time Nifty 200 membership cannot be proven exactly."""


@dataclass(frozen=True)
class HistoricalIndexMember:
    symbol: str
    financial: bool
    dummy: bool
    origin: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "financial": self.financial,
            "dummy": self.dummy,
            "origin": self.origin,
        }


def canonical_hash(payload: Any) -> str:
    try:
        raw = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Nifty200HistoryError("historical index payload must contain finite JSON") from exc
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_registry(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)
    try:
        document = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Nifty200HistoryError(f"could not load Nifty 200 history registry: {exc}") from exc
    if not isinstance(document, dict):
        raise Nifty200HistoryError("Nifty 200 history registry root must be a mapping")
    if document.get("id") != "NIFTY200-HISTORICAL-MEMBERSHIP-V1":
        raise Nifty200HistoryError("unexpected Nifty 200 history registry id")
    if document.get("status") != "FROZEN_HISTORICAL_RECONSTRUCTION":
        raise Nifty200HistoryError("Nifty 200 history registry must remain frozen")
    if document.get("index_id") != "NIFTY_200":
        raise Nifty200HistoryError("historical membership registry is not for Nifty 200")
    if document.get("integrity", {}).get("live_capital") is not False:
        raise Nifty200HistoryError("historical membership reconstruction must keep live capital disabled")
    if document.get("integrity", {}).get("prospective_equivalence_claimed") is not False:
        raise Nifty200HistoryError("historical membership reconstruction cannot claim prospective equivalence")
    return document


def load_anchor(registry: dict[str, Any], *, repo_root: str | Path = ".") -> dict[str, HistoricalIndexMember]:
    anchor = registry.get("anchor")
    if not isinstance(anchor, dict):
        raise Nifty200HistoryError("registry is missing anchor")
    path = Path(repo_root) / str(anchor.get("csv") or "")
    if not path.is_file():
        raise Nifty200HistoryError(f"Nifty 200 anchor does not exist: {path}")
    actual_sha = file_sha256(path)
    if actual_sha != anchor.get("raw_sha256"):
        raise Nifty200HistoryError(
            f"Nifty 200 anchor hash changed: declared={anchor.get('raw_sha256')} actual={actual_sha}"
        )
    try:
        rows = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    except (OSError, UnicodeDecodeError) as exc:
        raise Nifty200HistoryError(f"could not parse Nifty 200 anchor: {exc}") from exc
    if len(rows) != 201:
        raise Nifty200HistoryError(f"expected 201 anchor rows including dummy, found {len(rows)}")
    state: dict[str, HistoricalIndexMember] = {}
    for row in rows:
        symbol = str(row.get("Symbol") or "").strip().upper()
        industry = str(row.get("Industry") or "").strip()
        if not symbol:
            raise Nifty200HistoryError("anchor contains a blank symbol")
        if symbol in state:
            raise Nifty200HistoryError(f"anchor contains duplicate symbol: {symbol}")
        state[symbol] = HistoricalIndexMember(
            symbol=symbol,
            financial=industry.casefold() == "financial services",
            dummy=symbol.startswith("DUMMY"),
            origin="anchor:2025-01-29",
        )
    return state


def _remove_exact(state: dict[str, HistoricalIndexMember], symbol: str, *, event_label: str) -> None:
    symbol = symbol.strip().upper()
    if symbol not in state:
        raise Nifty200HistoryError(f"{event_label}: expected constituent missing: {symbol}")
    del state[symbol]


def _remove_any(
    state: dict[str, HistoricalIndexMember], symbols: list[str], *, event_label: str
) -> str:
    normalized = [str(symbol).strip().upper() for symbol in symbols]
    present = [symbol for symbol in normalized if symbol in state]
    if len(present) != 1:
        raise Nifty200HistoryError(
            f"{event_label}: expected exactly one live alias from {normalized}, found {present}"
        )
    del state[present[0]]
    return present[0]


def _add(
    state: dict[str, HistoricalIndexMember],
    *,
    symbol: str,
    financial: bool,
    dummy: bool,
    event_label: str,
) -> None:
    normalized = symbol.strip().upper()
    if not normalized:
        raise Nifty200HistoryError(f"{event_label}: blank addition symbol")
    if normalized in state:
        raise Nifty200HistoryError(f"{event_label}: addition already exists: {normalized}")
    state[normalized] = HistoricalIndexMember(
        symbol=normalized,
        financial=bool(financial),
        dummy=bool(dummy),
        origin=event_label,
    )


def _rename(
    state: dict[str, HistoricalIndexMember], *, old: str, new: str, event_label: str
) -> None:
    old_symbol = old.strip().upper()
    new_symbol = new.strip().upper()
    if old_symbol not in state:
        raise Nifty200HistoryError(f"{event_label}: rename source missing: {old_symbol}")
    if new_symbol in state:
        raise Nifty200HistoryError(f"{event_label}: rename target already exists: {new_symbol}")
    member = state.pop(old_symbol)
    state[new_symbol] = replace(member, symbol=new_symbol, origin=event_label)


def apply_event(state: dict[str, HistoricalIndexMember], event: dict[str, Any]) -> dict[str, Any]:
    effective = str(event.get("effective_date") or "")
    kind = str(event.get("kind") or "")
    source_url = str(event.get("source_url") or "")
    if not effective or not source_url:
        raise Nifty200HistoryError("membership event requires effective_date and source_url")
    try:
        date.fromisoformat(effective)
    except ValueError as exc:
        raise Nifty200HistoryError(f"invalid event date: {effective}") from exc
    label = f"{effective}:{kind}"
    before = sorted(state)
    details: dict[str, Any] = {}

    if kind == "REMOVE_ANY":
        details["removed"] = _remove_any(state, list(event.get("symbols") or []), event_label=label)
    elif kind == "REMOVE_GROUPS":
        removed = []
        for group in event.get("groups") or []:
            removed.append(_remove_any(state, list(group), event_label=label))
        details["removed"] = removed
    elif kind == "RECONSTITUTION":
        remove = [str(symbol).strip().upper() for symbol in event.get("remove") or []]
        additions = event.get("add") or []
        if len(remove) != len(additions):
            raise Nifty200HistoryError(f"{label}: reconstitution add/remove counts differ")
        for symbol in remove:
            _remove_exact(state, symbol, event_label=label)
        added = []
        for item in additions:
            if not isinstance(item, dict) or not isinstance(item.get("financial"), bool):
                raise Nifty200HistoryError(f"{label}: every added member requires explicit financial boolean")
            symbol = str(item.get("symbol") or "").strip().upper()
            _add(
                state,
                symbol=symbol,
                financial=item["financial"],
                dummy=False,
                event_label=label,
            )
            added.append(symbol)
        details.update({"removed": remove, "added": added})
    elif kind == "ADD_DUMMY":
        symbol = str(event.get("symbol") or "").strip().upper()
        _add(state, symbol=symbol, financial=False, dummy=True, event_label=label)
        details["added"] = [symbol]
    elif kind == "ADD_DUMMIES":
        added = []
        for raw in event.get("symbols") or []:
            symbol = str(raw).strip().upper()
            _add(state, symbol=symbol, financial=False, dummy=True, event_label=label)
            added.append(symbol)
        details["added"] = added
    elif kind == "RENAME":
        old = str(event.get("from") or "").strip().upper()
        new = str(event.get("to") or "").strip().upper()
        _rename(state, old=old, new=new, event_label=label)
        details["renamed"] = {"from": old, "to": new}
    else:
        raise Nifty200HistoryError(f"unsupported historical membership event kind: {kind}")

    return {
        "effective_date": effective,
        "kind": kind,
        "source_url": source_url,
        "before_count": len(before),
        "after_count": len(state),
        **details,
    }


def reconstruct_freezes(
    registry: dict[str, Any], *, repo_root: str | Path = "."
) -> list[dict[str, Any]]:
    state = load_anchor(registry, repo_root=repo_root)
    freeze_specs = registry.get("freeze_dates") or []
    events = registry.get("events") or []
    try:
        events = sorted(events, key=lambda event: date.fromisoformat(str(event["effective_date"])))
        freeze_specs = sorted(
            freeze_specs,
            key=lambda item: date.fromisoformat(str(item["date"])),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Nifty200HistoryError(f"invalid freeze/event chronology: {exc}") from exc

    snapshots: list[dict[str, Any]] = []
    event_cursor = 0
    applied: list[dict[str, Any]] = []
    expected_regular = int(
        registry.get("integrity", {}).get("expected_regular_constituents_at_each_freeze", -1)
    )
    for freeze in freeze_specs:
        freeze_day = date.fromisoformat(str(freeze["date"]))
        while event_cursor < len(events):
            event_day = date.fromisoformat(str(events[event_cursor]["effective_date"]))
            if event_day > freeze_day:
                break
            applied.append(apply_event(state, events[event_cursor]))
            event_cursor += 1

        members = sorted(state.values(), key=lambda member: member.symbol)
        regular = [member for member in members if not member.dummy]
        dummies = [member for member in members if member.dummy]
        investable = regular
        non_financial = [member for member in investable if not member.financial]
        if len(regular) != expected_regular:
            raise Nifty200HistoryError(
                f"freeze {freeze_day}: expected {expected_regular} regular constituents, found {len(regular)}; "
                f"dummies={[member.symbol for member in dummies]}"
            )
        payload = {
            "schema_version": 1,
            "index_id": "NIFTY_200",
            "quarter_id": str(freeze["quarter_id"]),
            "freeze_date": freeze_day.isoformat(),
            "index_member_count_including_dummies": len(members),
            "regular_member_count": len(regular),
            "dummy_symbols": [member.symbol for member in dummies],
            "investable_member_count": len(investable),
            "financial_member_count": sum(member.financial for member in investable),
            "non_financial_member_count": len(non_financial),
            "regular_members": [member.to_dict() for member in regular],
            "non_financial_symbols": [member.symbol for member in non_financial],
            "applied_event_count": len(applied),
            "applied_events": list(applied),
            "live_capital_allowed": False,
            "survivorship_bias_status": "POINT_IN_TIME_MEMBERSHIP_RECONSTRUCTED",
        }
        payload["sha256"] = canonical_hash(payload)
        snapshots.append(payload)
    return snapshots
