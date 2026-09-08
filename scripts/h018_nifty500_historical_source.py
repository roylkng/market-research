from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
import run_h015_independent_challenge as h15

URL = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
REFERER = "https://www.niftyindices.com/reports/historical-data"
INDEX_NAME = "NIFTY 500"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/152.0.0.0 Safari/537.36 marketlab-h018-source-probe/1"
)
ALLOWED_HOSTS = {"niftyindices.com", "www.niftyindices.com"}


class H018HistoricalIndexError(ValueError):
    pass


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _date_token(day: date) -> str:
    return day.strftime("%d-%b-%Y")


def request_payload(start: date, end: date) -> dict[str, str]:
    if end < start:
        raise H018HistoricalIndexError("historical index end date precedes start date")
    cinfo = (
        "{'name':'NIFTY 500','startDate':'"
        + _date_token(start)
        + "','endDate':'"
        + _date_token(end)
        + "','indexName':'NIFTY 500'}"
    )
    return {"cinfo": cinfo}


def fetch_official_history(start: date, end: date) -> tuple[bytes, str]:
    response = requests.post(
        URL,
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": REFERER,
            "Origin": "https://www.niftyindices.com",
            "User-Agent": USER_AGENT,
        },
        json=request_payload(start, end),
        timeout=(10, 90),
        allow_redirects=True,
    )
    host = (urlparse(response.url).hostname or "").casefold()
    if host not in ALLOWED_HOSTS:
        raise H018HistoricalIndexError("NSE Indices history redirected outside approved hosts")
    response.raise_for_status()
    if not response.content:
        raise H018HistoricalIndexError("empty NSE Indices historical response")
    return response.content, response.url


def _positive_number(value: object, *, field: str, day: date) -> float:
    text = str(value or "").strip().replace(",", "")
    if not text or text == "-":
        raise H018HistoricalIndexError(f"missing {field} for NIFTY 500 on {day}")
    try:
        number = float(text)
    except ValueError as exc:
        raise H018HistoricalIndexError(f"invalid {field} for NIFTY 500 on {day}") from exc
    if not math.isfinite(number) or number <= 0:
        raise H018HistoricalIndexError(f"nonpositive {field} for NIFTY 500 on {day}")
    return number


def parse_official_history(
    raw: bytes,
    *,
    start: date,
    end: date,
) -> dict[date, dict[str, float]]:
    try:
        envelope = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H018HistoricalIndexError("invalid NSE Indices response envelope") from exc
    encoded = envelope.get("d") if isinstance(envelope, dict) else None
    if not isinstance(encoded, str):
        raise H018HistoricalIndexError("NSE Indices response missing encoded data field")
    try:
        rows = json.loads(encoded)
    except json.JSONDecodeError as exc:
        raise H018HistoricalIndexError("invalid NSE Indices encoded row payload") from exc
    if not isinstance(rows, list):
        raise H018HistoricalIndexError("NSE Indices historical rows must be a list")

    result: dict[date, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = " ".join(str(row.get("Index Name") or row.get("indexName") or "").split())
        if name.casefold() != INDEX_NAME.casefold():
            continue
        date_text = str(row.get("HistoricalDate") or row.get("Date") or "").strip()
        parsed: date | None = None
        for fmt in ("%d %b %Y", "%d-%b-%Y"):
            try:
                value = time.strptime(date_text, fmt)
                parsed = date(value.tm_year, value.tm_mon, value.tm_mday)
                break
            except ValueError:
                continue
        if parsed is None or not (start <= parsed <= end):
            continue
        if parsed in result:
            raise H018HistoricalIndexError(f"duplicate NIFTY 500 history row on {parsed}")
        result[parsed] = {
            "open": _positive_number(row.get("OPEN") or row.get("Open"), field="open", day=parsed),
            "high": _positive_number(row.get("HIGH") or row.get("High"), field="high", day=parsed),
            "low": _positive_number(row.get("LOW") or row.get("Low"), field="low", day=parsed),
            "close": _positive_number(row.get("CLOSE") or row.get("Close"), field="close", day=parsed),
        }
    if not result:
        raise H018HistoricalIndexError("no usable NIFTY 500 rows in official history response")
    return result


def cross_validate_checkpoints(
    history: dict[date, dict[str, float]],
    checkpoint_root: Path,
) -> dict[str, object]:
    checkpoints = checkpoint_root / "checkpoints"
    if not checkpoints.is_dir():
        raise H018HistoricalIndexError("H018 checkpoint directory missing")
    overlap = 0
    exact_open = 0
    exact_close = 0
    max_open_diff = 0.0
    max_close_diff = 0.0
    missing_history: list[str] = []

    for path in sorted(checkpoints.glob("*.json")):
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        if checkpoint.get("status") != "COMMON_SESSION":
            continue
        day = date.fromisoformat(str(checkpoint["date"]))
        expected = history.get(day)
        if expected is None:
            missing_history.append(day.isoformat())
            continue
        index_meta = checkpoint["index"]
        raw_path = checkpoint_root / str(index_meta["raw_path"])
        raw = raw_path.read_bytes()
        if sha256(raw) != index_meta["sha256"]:
            raise H018HistoricalIndexError(f"retained daily index source hash mismatch on {day}")
        daily = h15.parse_nifty500_source_date(raw, day)
        open_diff = abs(float(daily["open"]) - float(expected["open"]))
        close_diff = abs(float(daily["close"]) - float(expected["close"]))
        max_open_diff = max(max_open_diff, open_diff)
        max_close_diff = max(max_close_diff, close_diff)
        exact_open += int(open_diff == 0)
        exact_close += int(close_diff == 0)
        overlap += 1

    if missing_history:
        raise H018HistoricalIndexError(
            f"official historical source missing {len(missing_history)} retained common sessions"
        )
    if overlap < 300:
        raise H018HistoricalIndexError(f"insufficient official-source overlap: {overlap}")
    if max_open_diff > 0.011 or max_close_diff > 0.011:
        raise H018HistoricalIndexError(
            "official historical source does not reproduce retained daily NIFTY 500 OHLC"
        )
    return {
        "overlap_common_sessions": overlap,
        "exact_open_match_count": exact_open,
        "exact_close_match_count": exact_close,
        "max_open_abs_difference": max_open_diff,
        "max_close_abs_difference": max_close_diff,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2013, 11, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2017, 5, 31))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    raw, final_url = fetch_official_history(args.start, args.end)
    history = parse_official_history(raw, start=args.start, end=args.end)
    validation = cross_validate_checkpoints(history, args.checkpoint_root)
    dates = sorted(history)
    if dates[0] > date(2013, 11, 1) or dates[-1] < date(2017, 5, 31):
        raise H018HistoricalIndexError("official NIFTY 500 history does not span frozen H018 window")
    if len(history) < 800:
        raise H018HistoricalIndexError(f"insufficient NIFTY 500 historical rows: {len(history)}")

    raw_dir = args.out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(raw)
    (raw_dir / digest).write_bytes(raw)
    summary = {
        "schema_version": 1,
        "status": "SOURCE_EQUIVALENCE_PROBE_ONLY",
        "live_capital_allowed": False,
        "market_selection_outcomes_opened": False,
        "source_owner": "NSE Indices Limited",
        "source_host": urlparse(final_url).hostname,
        "source_endpoint": "/Backpage.aspx/getHistoricaldatatabletoString",
        "source_sha256": digest,
        "source_bytes": len(raw),
        "requested_start": args.start.isoformat(),
        "requested_end": args.end.isoformat(),
        "row_count": len(history),
        "first_row_date": dates[0].isoformat(),
        "last_row_date": dates[-1].isoformat(),
        **validation,
    }
    (args.out / "probe-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
