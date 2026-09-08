#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from marketlab.nse import NSEClient

TOKENS = ("bonus", "split", "sub-division", "subdivision", "consolidation", "rights")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--episodes", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args()


def parse_ex_date(value: Any) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.title(), fmt).date()
        except ValueError:
            continue
    return None


def chunks(start: date, end: date, days: int = 60):
    cur = start
    while cur <= end:
        stop = min(end, cur + timedelta(days=days - 1))
        yield cur, stop
        cur = stop + timedelta(days=1)


def main() -> None:
    ns = parse_args()
    episodes = json.loads(Path(ns.episodes).read_text())
    if not isinstance(episodes, list):
        raise SystemExit("episodes file must contain list")
    starts = [date.fromisoformat(row["start_date"]) for row in episodes]
    hits = [date.fromisoformat(row["hit_date"]) for row in episodes]
    query_start = min(starts) - timedelta(days=45)
    query_end = max(hits)

    client = NSEClient(timeout=25, attempts=4)
    actions: list[dict[str, Any]] = []
    raw_count = 0
    for a, b in chunks(query_start, query_end):
        payload, _ = client._json_get_with_raw(
            client.CORPORATE_ACTION_ENDPOINT,
            params={
                "index": "equities",
                "from_date": a.strftime("%d-%m-%Y"),
                "to_date": b.strftime("%d-%m-%Y"),
            },
        )
        rows = payload if isinstance(payload, list) else (
            payload.get("data", []) if isinstance(payload, dict) else []
        )
        raw_count += len(rows) if isinstance(rows, list) else 0
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            subject = str(row.get("subject") or row.get("purpose") or "").strip()
            ex_date = parse_ex_date(row.get("exDate") or row.get("ex_date"))
            if not symbol or not subject or not ex_date:
                continue
            if not any(token in subject.casefold() for token in TOKENS):
                continue
            actions.append({"symbol": symbol, "subject": subject, "ex_date": ex_date.isoformat()})

    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in actions:
        by_symbol[action["symbol"]].append(action)

    affected = []
    forward_affected = []
    lookback_only = []
    for episode in episodes:
        symbol = episode["symbol"]
        start = date.fromisoformat(episode["start_date"])
        hit = date.fromisoformat(episode["hit_date"])
        lookback_start = start - timedelta(days=45)
        matches = [
            action
            for action in by_symbol.get(symbol, [])
            if lookback_start <= date.fromisoformat(action["ex_date"]) <= hit
        ]
        if not matches:
            continue
        rec = {"episode": episode, "actions": matches}
        affected.append(rec)
        if any(start <= date.fromisoformat(action["ex_date"]) <= hit for action in matches):
            forward_affected.append(rec)
        else:
            lookback_only.append(rec)

    report = {
        "schema_version": 1,
        "status": "PRICE_BASIS_AUDIT",
        "episode_count": len(episodes),
        "raw_corporate_action_rows": raw_count,
        "share_action_count": len(actions),
        "affected_episode_count": len(affected),
        "affected_episode_fraction": len(affected) / len(episodes) if episodes else None,
        "forward_window_affected_count": len(forward_affected),
        "forward_window_affected_fraction": len(forward_affected) / len(episodes) if episodes else None,
        "lookback_only_affected_count": len(lookback_only),
        "affected": affected,
    }
    Path(ns.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "affected"}, indent=2))


if __name__ == "__main__":
    main()
