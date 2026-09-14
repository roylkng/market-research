from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import requests

from marketlab.universe import load_universe_snapshot

NSE_HOME = "https://www.nseindia.com/"
PIT_PAGE = "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading"
PIT_ENDPOINT = "https://www.nseindia.com/api/corporates-pit"


class H024SourceProbeError(RuntimeError):
    """Raised when official NSE PIT source probing cannot proceed without guessing."""


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _nse_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise H024SourceProbeError(f"invalid ISO date: {value}") from exc
    return parsed.strftime("%d-%m-%Y")


def _session(timeout: float) -> requests.Session:
    if timeout <= 0:
        raise H024SourceProbeError("timeout must be positive")
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
    symbol: str,
    from_date: str,
    to_date: str,
    timeout: float,
    attempts: int,
) -> requests.Response:
    if attempts < 1:
        raise H024SourceProbeError("attempts must be >= 1")
    last_error: Exception | None = None
    params = {
        "symbol": symbol,
        "from_date": _nse_date(from_date),
        "to_date": _nse_date(to_date),
        "type": "individual",
    }
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(PIT_ENDPOINT, params=params, timeout=timeout)
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
    raise H024SourceProbeError(f"{symbol}: NSE PIT request failed: {last_error}")


def _rows(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise H024SourceProbeError("NSE PIT payload is not an object")
    raw = payload.get("data")
    if raw is None:
        raw = []
    if not isinstance(raw, list):
        raise H024SourceProbeError("NSE PIT payload.data is not a list")
    return [row for row in raw if isinstance(row, dict)]


def _field_family(key: str) -> str | None:
    lowered = key.casefold()
    if any(token in lowered for token in ("date", "time", "dt", "intim", "submit", "broadcast")):
        return "timestamp_like"
    if any(token in lowered for token in ("xbrl", "file", "url", "link", "attach")):
        return "url_or_file_like"
    if any(token in lowered for token in ("category", "person", "relation")):
        return "actor_like"
    if any(token in lowered for token in ("mode", "acq", "transaction", "trade")):
        return "transaction_like"
    return None


def _safe_samples(values: list[str], *, limit: int = 20) -> list[str]:
    seen: list[str] = []
    known: set[str] = set()
    for value in values:
        if not value or value in known:
            continue
        known.add(value)
        seen.append(value[:500])
        if len(seen) >= limit:
            break
    return seen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Source-only feasibility inventory for official NSE PIT Regulation 7(2) data"
    )
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--from-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--to-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.10)
    parser.add_argument("--row-samples-per-symbol", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)
    if start > end:
        raise H024SourceProbeError("from-date exceeds to-date")
    if args.pause_seconds < 0 or args.row_samples_per_symbol < 0:
        raise H024SourceProbeError("invalid pause/sample configuration")

    universe = load_universe_snapshot(args.universe)
    if len(universe.members) != 100:
        raise H024SourceProbeError("H024 probe requires frozen 100-name U001")

    session = _session(args.timeout_seconds)
    field_counts: Counter[str] = Counter()
    nonempty_field_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    security_counts: Counter[str] = Counter()
    field_values: dict[str, list[str]] = defaultdict(list)
    family_values: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    symbol_reports: list[dict[str, Any]] = []
    all_row_count = 0

    for index, member in enumerate(universe.members, start=1):
        symbol = member.symbol.upper()
        response = _request(
            session,
            symbol=symbol,
            from_date=args.from_date,
            to_date=args.to_date,
            timeout=args.timeout_seconds,
            attempts=args.attempts,
        )
        raw = response.content
        if args.raw_dir is not None:
            args.raw_dir.mkdir(parents=True, exist_ok=True)
            (args.raw_dir / f"{symbol}.json").write_bytes(raw)
        try:
            payload = response.json()
        except ValueError as exc:
            raise H024SourceProbeError(f"{symbol}: NSE PIT response is not JSON") from exc
        rows = _rows(payload)
        all_row_count += len(rows)
        observed_symbols = sorted(
            {
                _clean(row.get("symbol")).upper()
                for row in rows
                if _clean(row.get("symbol"))
            }
        )
        for row in rows:
            for key, value in row.items():
                key_text = str(key)
                field_counts[key_text] += 1
                cleaned = _clean(value)
                if cleaned:
                    nonempty_field_counts[key_text] += 1
                    if len(field_values[key_text]) < 100:
                        field_values[key_text].append(cleaned)
                    family = _field_family(key_text)
                    if family and len(family_values[family][key_text]) < 100:
                        family_values[family][key_text].append(cleaned)
            category = _clean(row.get("personCategory"))
            mode = _clean(row.get("acqMode"))
            security = _clean(row.get("secType"))
            if category:
                category_counts[category] += 1
            if mode:
                mode_counts[mode] += 1
            if security:
                security_counts[security] += 1

        symbol_reports.append(
            {
                "symbol": symbol,
                "status": "COMPLETE",
                "http_content_type": response.headers.get("Content-Type"),
                "raw_sha256": _sha256(raw),
                "raw_byte_count": len(raw),
                "row_count": len(rows),
                "observed_symbols": observed_symbols,
                "top_level_keys": sorted(str(key) for key in payload),
                "row_samples": rows[: args.row_samples_per_symbol],
            }
        )
        print(
            f"[{index:03d}/100] {symbol}: rows={len(rows)} bytes={len(raw)}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    family_inventory = {
        family: {
            key: _safe_samples(values)
            for key, values in sorted(fields.items())
        }
        for family, fields in sorted(family_values.items())
    }
    key_samples = {
        key: _safe_samples(values, limit=10) for key, values in sorted(field_values.items())
    }
    report = {
        "schema_version": 1,
        "hypothesis_candidate": "H024_INSIDER_CAPITAL_COMMITMENT",
        "probe_id": "H024-NSE-PIT-SOURCE-INVENTORY-V1",
        "purpose": (
            "Source-only feasibility and raw-schema inventory for official NSE Regulation 7(2) "
            "PIT disclosures. No market price, benchmark return, or future outcome data consumed."
        ),
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": {
            "page": PIT_PAGE,
            "endpoint": PIT_ENDPOINT,
            "type": "individual",
            "from_date": args.from_date,
            "to_date": args.to_date,
        },
        "universe_path": args.universe.as_posix(),
        "member_count": 100,
        "summary": {
            "complete_symbols": len(symbol_reports),
            "symbols_with_rows": sum(row["row_count"] > 0 for row in symbol_reports),
            "symbols_without_rows": sum(row["row_count"] == 0 for row in symbol_reports),
            "row_count": all_row_count,
        },
        "field_counts": dict(field_counts.most_common()),
        "nonempty_field_counts": dict(nonempty_field_counts.most_common()),
        "field_value_samples": key_samples,
        "field_family_inventory": family_inventory,
        "person_category_counts": dict(category_counts.most_common()),
        "acquisition_mode_counts": dict(mode_counts.most_common()),
        "security_type_counts": dict(security_counts.most_common()),
        "symbol_reports": symbol_reports,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(json.dumps(report["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
