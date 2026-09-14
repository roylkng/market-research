from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from marketlab.universe import load_universe_snapshot

NSE_HOME = "https://www.nseindia.com/"
PIT_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"
PIT_GG_ENDPOINT = "https://www.nseindia.com/api/corporates-pit-gg"


class H024GGProbeError(RuntimeError):
    """Raised when the current NSE PIT discovery feed cannot be audited safely."""


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return _sha256(raw)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _nse_date(value: date) -> str:
    return value.strftime("%d-%m-%Y")


def _session(timeout: float) -> requests.Session:
    if timeout <= 0:
        raise H024GGProbeError("timeout must be positive")
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": PIT_PAGE,
        }
    )
    session.get(NSE_HOME, timeout=timeout)
    session.get(PIT_PAGE, timeout=timeout)
    return session


def _request(
    session: requests.Session,
    *,
    start: date,
    end: date,
    timeout: float,
    attempts: int,
    symbol: str | None = None,
) -> requests.Response:
    params = {
        "index": "equities",
        "from_date": _nse_date(start),
        "to_date": _nse_date(end),
    }
    if symbol:
        params["symbol"] = symbol.strip().upper()
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(
                PIT_GG_ENDPOINT,
                params=params,
                timeout=timeout,
            )
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
            try:
                session.get(NSE_HOME, timeout=timeout)
                session.get(PIT_PAGE, timeout=timeout)
            except requests.RequestException:
                pass
    raise H024GGProbeError(
        f"NSE PIT-GG request failed {start.isoformat()}..{end.isoformat()} "
        f"symbol={symbol or '*'}: {last_error}"
    )


def _rows(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise H024GGProbeError("NSE PIT-GG payload.data is not a list")
        return [row for row in data if isinstance(row, dict)]
    raise H024GGProbeError("NSE PIT-GG payload is neither object nor list")


def _windows(start: date, end: date, days: int) -> list[tuple[date, date]]:
    if days < 1:
        raise H024GGProbeError("window-days must be positive")
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        result.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return result


def _field_family(key: str) -> str | None:
    lowered = key.casefold()
    if any(token in lowered for token in ("broadcast", "date", "time", "submit", "revision")):
        return "timestamp_like"
    if any(token in lowered for token in ("ixbrl", "xbrl", "file", "url", "link", "attach")):
        return "document_like"
    if "regulation" in lowered or "submission" in lowered:
        return "filing_type_like"
    return None


def _samples(values: list[str], *, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value[:500])
        if len(result) >= limit:
            break
    return result


def _row_identity(row: dict[str, Any]) -> str:
    return _canonical_sha256(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Source-only audit of the current NSE PIT-GG insider-trading discovery feed"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--from-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--window-days", type=int, default=28)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)
    if start > end:
        raise H024GGProbeError("from-date exceeds to-date")
    if args.pause_seconds < 0:
        raise H024GGProbeError("pause-seconds must be non-negative")

    universe = load_universe_snapshot(args.universe)
    if len(universe.members) != 100:
        raise H024GGProbeError("H024 PIT-GG probe requires frozen 100-name U001")
    u001_symbols = {member.symbol.upper() for member in universe.members}

    session = _session(args.timeout_seconds)
    deduped: dict[str, dict[str, Any]] = {}
    window_reports: list[dict[str, Any]] = []
    duplicate_row_count = 0

    for index, (window_start, window_end) in enumerate(
        _windows(start, end, args.window_days), start=1
    ):
        response = _request(
            session,
            start=window_start,
            end=window_end,
            timeout=args.timeout_seconds,
            attempts=args.attempts,
        )
        raw = response.content
        if args.raw_dir is not None:
            args.raw_dir.mkdir(parents=True, exist_ok=True)
            name = f"{window_start.isoformat()}_{window_end.isoformat()}.json"
            (args.raw_dir / name).write_bytes(raw)
        try:
            payload = response.json()
        except ValueError as exc:
            raise H024GGProbeError(
                f"PIT-GG response is not JSON for {window_start}..{window_end}"
            ) from exc
        rows = _rows(payload)
        ids: list[str] = []
        for row in rows:
            row_id = _row_identity(row)
            ids.append(row_id)
            previous = deduped.get(row_id)
            if previous is not None:
                duplicate_row_count += 1
                if previous != row:
                    raise H024GGProbeError("identical PIT-GG row hash mapped to changed bytes")
                continue
            deduped[row_id] = row
        window_reports.append(
            {
                "from_date": window_start.isoformat(),
                "to_date": window_end.isoformat(),
                "row_count": len(rows),
                "unique_row_count": len(set(ids)),
                "raw_sha256": _sha256(raw),
                "raw_byte_count": len(raw),
                "content_type": response.headers.get("Content-Type"),
                "top_level_type": type(payload).__name__,
                "top_level_keys": sorted(str(key) for key in payload)
                if isinstance(payload, dict)
                else [],
            }
        )
        print(
            f"[{index:02d}] {window_start}..{window_end}: rows={len(rows)} bytes={len(raw)}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    rows = list(deduped.values())
    field_counts: Counter[str] = Counter()
    nonempty_counts: Counter[str] = Counter()
    field_values: dict[str, list[str]] = defaultdict(list)
    family_values: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    regulations: Counter[str] = Counter()
    submission_types: Counter[str] = Counter()
    revision_remarks: Counter[str] = Counter()
    symbols: Counter[str] = Counter()
    ixbrl_hosts: Counter[str] = Counter()

    for row in rows:
        symbol = _clean(row.get("symbol")).upper()
        if symbol:
            symbols[symbol] += 1
        regulation = _clean(row.get("regulation"))
        if regulation:
            regulations[regulation] += 1
        submission_type = _clean(row.get("typeOfSubmission"))
        if submission_type:
            submission_types[submission_type] += 1
        revision = _clean(row.get("revisionRemark"))
        if revision:
            revision_remarks[revision] += 1
        ixbrl = _clean(row.get("ixbrl"))
        if ixbrl:
            host = ixbrl.split("/", 3)[2].casefold() if ixbrl.startswith("https://") else "NON_HTTPS"
            ixbrl_hosts[host] += 1
        for key, value in row.items():
            key_text = str(key)
            field_counts[key_text] += 1
            cleaned = _clean(value)
            if not cleaned:
                continue
            nonempty_counts[key_text] += 1
            if len(field_values[key_text]) < 200:
                field_values[key_text].append(cleaned)
            family = _field_family(key_text)
            if family and len(family_values[family][key_text]) < 200:
                family_values[family][key_text].append(cleaned)

    u001_rows = [row for row in rows if _clean(row.get("symbol")).upper() in u001_symbols]
    broadcast_values = [
        _clean(row.get("broadcastDateTime"))
        for row in rows
        if _clean(row.get("broadcastDateTime"))
    ]
    ixbrl_values = [_clean(row.get("ixbrl")) for row in rows if _clean(row.get("ixbrl"))]
    report = {
        "schema_version": 1,
        "hypothesis_candidate": "H024_INSIDER_CAPITAL_COMMITMENT",
        "probe_id": "H024-NSE-PIT-GG-SOURCE-INVENTORY-V1",
        "purpose": (
            "Source-only audit of the current post-May-2026 NSE insider-trading discovery feed, "
            "including windowed completeness checks and iXBRL coverage. No price/return outcome consumed."
        ),
        "generated_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source": {
            "page": PIT_PAGE,
            "endpoint": PIT_GG_ENDPOINT,
            "from_date": args.from_date,
            "to_date": args.to_date,
            "window_days": args.window_days,
        },
        "universe_path": args.universe.as_posix(),
        "window_reports": window_reports,
        "summary": {
            "window_count": len(window_reports),
            "row_count": len(rows),
            "duplicate_rows_across_windows": duplicate_row_count,
            "symbol_count": len(symbols),
            "u001_row_count": len(u001_rows),
            "u001_symbol_count": len(
                {_clean(row.get("symbol")).upper() for row in u001_rows}
            ),
            "broadcast_nonempty_count": len(broadcast_values),
            "ixbrl_nonempty_count": len(ixbrl_values),
            "ixbrl_unique_count": len(set(ixbrl_values)),
        },
        "field_counts": dict(field_counts.most_common()),
        "nonempty_field_counts": dict(nonempty_counts.most_common()),
        "field_value_samples": {
            key: _samples(values, limit=12) for key, values in sorted(field_values.items())
        },
        "field_family_inventory": {
            family: {
                key: _samples(values)
                for key, values in sorted(fields.items())
            }
            for family, fields in sorted(family_values.items())
        },
        "regulation_counts": dict(regulations.most_common()),
        "submission_type_counts": dict(submission_types.most_common()),
        "revision_remark_counts": dict(revision_remarks.most_common()),
        "symbol_counts": dict(symbols.most_common()),
        "ixbrl_host_counts": dict(ixbrl_hosts.most_common()),
        "broadcast_date_time_values": _samples(broadcast_values, limit=100),
        "ixbrl_samples": _samples(ixbrl_values, limit=100),
        "row_samples": rows[:30],
        "u001_row_samples": u001_rows[:30],
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(json.dumps(report["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
