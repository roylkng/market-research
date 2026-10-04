from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.events import sha256_bytes
from marketlab.marketdata import udiff_url
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss001_census import (
    ACTION_END,
    ACTION_START,
    CURRENT_SESSION,
    FINANCIAL_END,
    FINANCIAL_START,
    LIQUIDITY_SESSION_COUNT,
    build_full_market_census,
)
from marketlab.universe import load_universe_snapshot

U001_PATH = Path("research/prospective/universes/FY27-Q2-2026-09-06.json")
CALENDAR_PATH = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/NSE-CM-FY27Q2-v1.json"
)


def _write_bytes(
    root: Path,
    *,
    kind: str,
    raw: bytes,
    source_url: str,
) -> tuple[str, str]:
    sha = sha256_bytes(raw)
    suffix = Path(urlparse(source_url).path).suffix.lower() or ".bin"
    path = root / kind / "sha256" / f"{sha}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise RuntimeError(f"SS001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha, str(path)


def _payload_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if data is None:
            return []
        if not isinstance(data, list):
            raise AlphaContractError("SS001 NSE payload.data must be a list")
        return [row for row in data if isinstance(row, dict)]
    raise AlphaContractError("SS001 NSE payload must be list or object")


def _financial_pages(
    client: NSEClient,
    *,
    raw_dir: Path,
    page_size: int = 200,
    max_pages: int = 100,
) -> tuple[list[object], list[dict]]:
    payloads = []
    sources = []
    seen_page_hashes: set[str] = set()

    for page in range(1, max_pages + 1):
        payload, raw = client.integrated_filings_with_raw(
            from_date="01-04-2026",
            to_date="04-10-2026",
            page=page,
            size=page_size,
        )
        sha, path = _write_bytes(
            raw_dir,
            kind="integrated-filing-discovery",
            raw=raw,
            source_url=NSEClient.INTEGRATED_FILING_ENDPOINT.url,
        )
        if sha in seen_page_hashes:
            raise AlphaContractError(
                "SS001 Integrated Filing pagination repeated an identical source page"
            )
        seen_page_hashes.add(sha)
        rows = _payload_rows(payload)
        payloads.append(payload)
        sources.append(
            {
                "page": page,
                "page_size": page_size,
                "row_count": len(rows),
                "raw_sha256": sha,
                "raw_path": path,
            }
        )
        if not rows or len(rows) < page_size:
            return payloads, sources

    raise AlphaContractError("SS001 Integrated Filing pagination exceeded frozen max_pages")


def _date_chunks(start: date, end: date, days: int = 60) -> list[tuple[date, date]]:
    if start > end:
        raise AlphaContractError("SS001 action window is reversed")
    chunks = []
    cursor = start
    while cursor <= end:
        chunk_end = min(end, cursor + timedelta(days=days - 1))
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _action_payloads(
    client: NSEClient,
    *,
    raw_dir: Path,
) -> tuple[list[object], list[dict]]:
    payloads = []
    sources = []
    for start, end in _date_chunks(
        date.fromisoformat(ACTION_START),
        date.fromisoformat(ACTION_END),
    ):
        payload, raw = client.corporate_actions_with_raw(
            None,
            from_date=start.strftime("%d-%m-%Y"),
            to_date=end.strftime("%d-%m-%Y"),
        )
        sha, path = _write_bytes(
            raw_dir,
            kind="corporate-action-discovery",
            raw=raw,
            source_url=NSEClient.CORPORATE_ACTION_ENDPOINT.url,
        )
        rows = _payload_rows(payload)
        payloads.append(payload)
        sources.append(
            {
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "row_count": len(rows),
                "raw_sha256": sha,
                "raw_path": path,
            }
        )
    return payloads, sources


def _frozen_sessions() -> list[str]:
    payload = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    if payload.get("sha256") != (
        "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
    ):
        raise AlphaContractError("SS001 frozen calendar SHA mismatch")
    sessions = [
        str(row["session_date"])
        for row in payload.get("sessions", [])
        if str(row.get("session_date") or "") <= CURRENT_SESSION
    ]
    result = sessions[-LIQUIDITY_SESSION_COUNT:]
    if len(result) != LIQUIDITY_SESSION_COUNT or result[-1] != CURRENT_SESSION:
        raise AlphaContractError("SS001 could not resolve frozen 20-session window")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen SS001-D001 full-market source census"
    )
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=25.0)
    parser.add_argument("--attempts", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = NSEClient(timeout=args.timeout_seconds, attempts=args.attempts)
    captured_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    security_raw = client.all_equity_csv()
    security_sha, security_path = _write_bytes(
        args.raw_dir,
        kind="security-master",
        raw=security_raw,
        source_url=NSEClient.ALL_EQUITY_CSV,
    )

    market_sessions = []
    market_sources = []
    for session_text in _frozen_sessions():
        session_day = date.fromisoformat(session_text)
        source_url = udiff_url(session_day)
        raw = client.archive_bytes(source_url)
        sha, path = _write_bytes(
            args.raw_dir,
            kind="udiff",
            raw=raw,
            source_url=source_url,
        )
        equities = parse_udiff_eq_panel(raw, session_date=session_day)
        market_sessions.append(
            {
                "session_date": session_text,
                "equities": equities,
            }
        )
        market_sources.append(
            {
                "session_date": session_text,
                "source_url": source_url,
                "raw_sha256": sha,
                "raw_path": path,
                "eq_row_count": len(equities),
            }
        )
        print(
            f"[market] {session_text} rows={len(equities)} sha={sha[:12]}",
            flush=True,
        )

    integrated_payloads, integrated_sources = _financial_pages(
        client,
        raw_dir=args.raw_dir,
    )
    print(
        f"[financial] pages={len(integrated_sources)} "
        f"rows={sum(row['row_count'] for row in integrated_sources)}",
        flush=True,
    )

    action_payloads, action_sources = _action_payloads(
        client,
        raw_dir=args.raw_dir,
    )
    print(
        f"[actions] chunks={len(action_sources)} "
        f"rows={sum(row['row_count'] for row in action_sources)}",
        flush=True,
    )

    u001 = load_universe_snapshot(U001_PATH)
    existing_symbols = {member.symbol.upper() for member in u001.members}

    source_metadata = {
        "captured_at_utc": captured_at,
        "security_master": {
            "source_url": NSEClient.ALL_EQUITY_CSV,
            "raw_sha256": security_sha,
            "raw_path": security_path,
        },
        "market_sources": market_sources,
        "financial_window": {
            "from_date": FINANCIAL_START,
            "to_date": FINANCIAL_END,
            "pages": integrated_sources,
            "pagination_complete": True,
        },
        "corporate_action_window": {
            "from_date": ACTION_START,
            "to_date": ACTION_END,
            "chunks": action_sources,
        },
        "all_corporate_action_chunks_acquired": True,
        "existing_u001_sha256": u001.sha256,
    }

    census = build_full_market_census(
        security_master_raw=security_raw,
        market_sessions=market_sessions,
        integrated_payloads=integrated_payloads,
        corporate_action_payloads=action_payloads,
        existing_u001_symbols=existing_symbols,
        source_metadata=source_metadata,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    panel_path = args.output / "ss001-d001-census.json"
    panel_path.write_text(
        json.dumps(
            census,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    summary = {
        key: value
        for key, value in census.items()
        if key not in {"rows", "source_metadata"}
    }
    summary["source_metadata"] = {
        "captured_at_utc": captured_at,
        "security_master_raw_sha256": security_sha,
        "market_session_count": len(market_sources),
        "integrated_filing_page_count": len(integrated_sources),
        "corporate_action_chunk_count": len(action_sources),
    }
    (args.output / "summary.json").write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
