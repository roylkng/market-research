from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from probe_h024_nse_pit_gg import _clean, _request, _rows, _session

APPROVED_ARCHIVE_HOSTS = frozenset({"nsearchives.nseindia.com", "archives.nseindia.com"})
INTERESTING = re.compile(
    r"promoter|director|managerial|person|category|acquir|dispos|transaction|security|"
    r"share|holding|value|quantity|mode|trade|date|relation|relative|employee|designat",
    re.IGNORECASE,
)


class H024XMLProbeError(RuntimeError):
    """Raised when current PIT XML semantics cannot be audited without guessing."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _windows(start: date, end: date, days: int = 28) -> list[tuple[date, date]]:
    result: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        window_end = min(cursor + timedelta(days=days - 1), end)
        result.append((cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return result


def _parse_broadcast(value: object) -> datetime:
    text = _clean(value)
    try:
        return datetime.strptime(text, "%d-%b-%Y %H:%M:%S").replace(tzinfo=UTC)
    except ValueError as exc:
        raise H024XMLProbeError(f"invalid PIT-GG broadcastDateTime: {text}") from exc


def _collect_rows(
    session: requests.Session,
    *,
    start: date,
    end: date,
    timeout: float,
    attempts: int,
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for window_start, window_end in _windows(start, end):
        response = _request(
            session,
            start=window_start,
            end=window_end,
            timeout=timeout,
            attempts=attempts,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise H024XMLProbeError("PIT-GG response is not JSON") from exc
        for row in _rows(payload):
            raw = json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
            digest = _sha256(raw)
            existing = deduped.get(digest)
            if existing is not None and existing != row:
                raise H024XMLProbeError("PIT-GG row digest collision with changed bytes")
            deduped[digest] = row
    return list(deduped.values())


def _eligible(row: dict[str, Any]) -> bool:
    return (
        _clean(row.get("regulation")) == "Regulation 7 (2)"
        and _clean(row.get("typeOfSubmission")) in {"Original", "Revision"}
        and bool(_clean(row.get("xmlFileName")))
    )


def _sample_rows(
    rows: list[dict[str, Any]],
    *,
    originals_per_month: int,
    revision_limit: int,
) -> list[dict[str, Any]]:
    originals: dict[str, list[dict[str, Any]]] = defaultdict(list)
    revisions: list[dict[str, Any]] = []
    for row in rows:
        if not _eligible(row):
            continue
        published = _parse_broadcast(row.get("broadcastDateTime"))
        tagged = dict(row)
        tagged["_published"] = published
        if _clean(row.get("typeOfSubmission")) == "Revision":
            revisions.append(tagged)
        else:
            originals[published.strftime("%Y-%m")].append(tagged)

    selected: list[dict[str, Any]] = []
    for month in sorted(originals):
        candidates = sorted(
            originals[month],
            key=lambda row: (
                row["_published"],
                _clean(row.get("symbol")),
                _clean(row.get("xmlFileName")),
            ),
        )
        chosen: list[dict[str, Any]] = []
        seen_symbols: set[str] = set()
        for row in candidates:
            symbol = _clean(row.get("symbol")).upper()
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            chosen.append(row)
            if len(chosen) >= originals_per_month:
                break
        selected.extend(chosen)

    revisions.sort(
        key=lambda row: (
            row["_published"],
            _clean(row.get("symbol")),
            _clean(row.get("xmlFileName")),
        ),
        reverse=True,
    )
    selected.extend(revisions[:revision_limit])

    result: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for row in selected:
        url = _clean(row.get("xmlFileName"))
        if url in seen_urls:
            continue
        seen_urls.add(url)
        cleaned = dict(row)
        cleaned.pop("_published", None)
        result.append(cleaned)
    return result


def _fetch(
    session: requests.Session,
    *,
    url: str,
    timeout: float,
    attempts: int,
) -> requests.Response:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in APPROVED_ARCHIVE_HOSTS:
        raise H024XMLProbeError(f"unapproved PIT XML URL: {url}")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(min(2**attempt, 8))
    raise H024XMLProbeError(f"PIT XML fetch failed: {url}: {last_error}")


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _context_summary(root: ET.Element) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = _clean(element.attrib.get("id"))
        if not context_id:
            continue
        dimensions: list[dict[str, str]] = []
        periods: list[str] = []
        for nested in element.iter():
            local = _local_name(nested.tag).casefold()
            if local in {"explicitmember", "typedmember"}:
                dimensions.append(
                    {
                        "kind": local,
                        "dimension": _clean(nested.attrib.get("dimension")),
                        "value": _clean(nested.text),
                    }
                )
            if local in {"instant", "startdate", "enddate"}:
                periods.append(f"{local}:{_clean(nested.text)}")
        contexts[context_id] = {"dimensions": dimensions, "periods": periods}
    return contexts


def _inventory(raw: bytes) -> dict[str, Any]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise H024XMLProbeError(f"invalid PIT XML: {exc}") from exc
    contexts = _context_summary(root)
    facts: list[dict[str, Any]] = []
    concepts: Counter[str] = Counter()
    interesting: list[dict[str, Any]] = []
    for element in root.iter():
        context_ref = _clean(element.attrib.get("contextRef") or element.attrib.get("contextref"))
        if not context_ref:
            continue
        concept = _local_name(element.tag)
        value = _clean(element.text)
        fact = {
            "concept": concept,
            "context_ref": context_ref,
            "unit_ref": _clean(element.attrib.get("unitRef") or element.attrib.get("unitref")) or None,
            "decimals": _clean(element.attrib.get("decimals")) or None,
            "value": value[:1000],
            "context": contexts.get(context_ref),
        }
        facts.append(fact)
        concepts[concept] += 1
        if INTERESTING.search(concept) or INTERESTING.search(value):
            interesting.append(fact)
    return {
        "root_tag": _local_name(root.tag),
        "fact_count": len(facts),
        "context_count": len(contexts),
        "concept_count": len(concepts),
        "concept_counts": dict(concepts.most_common()),
        "interesting_facts": interesting[:600],
        "all_fact_samples": facts[:250],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory current NSE Regulation 7(2) raw-XBRL fact semantics"
    )
    parser.add_argument("--from-date", required=True)
    parser.add_argument("--to-date", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--originals-per-month", type=int, default=6)
    parser.add_argument("--revision-limit", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--pause-seconds", type=float, default=0.08)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.from_date)
    end = date.fromisoformat(args.to_date)
    if start > end:
        raise H024XMLProbeError("from-date exceeds to-date")
    if args.originals_per_month < 1 or args.revision_limit < 0 or args.pause_seconds < 0:
        raise H024XMLProbeError("invalid sample configuration")

    discovery = _session(args.timeout_seconds)
    rows = _collect_rows(
        discovery,
        start=start,
        end=end,
        timeout=args.timeout_seconds,
        attempts=args.attempts,
    )
    selected = _sample_rows(
        rows,
        originals_per_month=args.originals_per_month,
        revision_limit=args.revision_limit,
    )
    if not selected:
        raise H024XMLProbeError("no PIT XML documents selected")

    archive = requests.Session()
    archive.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept": "application/xml,text/xml,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    reports: list[dict[str, Any]] = []
    aggregate_concepts: Counter[str] = Counter()
    statuses: Counter[str] = Counter()

    for index, row in enumerate(selected, start=1):
        url = _clean(row.get("xmlFileName"))
        try:
            response = _fetch(
                archive,
                url=url,
                timeout=args.timeout_seconds,
                attempts=args.attempts,
            )
            inventory = _inventory(response.content)
        except H024XMLProbeError as exc:
            reports.append(
                {
                    "symbol": _clean(row.get("symbol")).upper(),
                    "broadcastDateTime": _clean(row.get("broadcastDateTime")),
                    "typeOfSubmission": _clean(row.get("typeOfSubmission")),
                    "xmlFileName": url,
                    "status": "FAILED",
                    "error": str(exc),
                }
            )
            statuses["FAILED"] += 1
            continue

        raw = response.content
        if args.raw_dir is not None:
            args.raw_dir.mkdir(parents=True, exist_ok=True)
            name = f"{index:03d}-{_sha256(url.encode('utf-8'))[:16]}.xml"
            (args.raw_dir / name).write_bytes(raw)
        aggregate_concepts.update(inventory["concept_counts"])
        reports.append(
            {
                "symbol": _clean(row.get("symbol")).upper(),
                "companyName": _clean(row.get("companyName")),
                "regulation": _clean(row.get("regulation")),
                "broadcastDateTime": _clean(row.get("broadcastDateTime")),
                "exchdisstime": _clean(row.get("exchdisstime")),
                "typeOfSubmission": _clean(row.get("typeOfSubmission")),
                "revisionRemark": _clean(row.get("revisionRemark")),
                "appId": _clean(row.get("appId")),
                "prevAppId": _clean(row.get("prevAppId")),
                "ixbrl": _clean(row.get("ixbrl")),
                "xmlFileName": url,
                "status": "COMPLETE",
                "content_type": response.headers.get("Content-Type"),
                "raw_sha256": _sha256(raw),
                "raw_byte_count": len(raw),
                "inventory": inventory,
            }
        )
        statuses["COMPLETE"] += 1
        print(
            f"[{index:02d}/{len(selected):02d}] {_clean(row.get('symbol')).upper()}: "
            f"facts={inventory['fact_count']} concepts={inventory['concept_count']}",
            flush=True,
        )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    report = {
        "schema_version": 1,
        "hypothesis_candidate": "H024_INSIDER_CAPITAL_COMMITMENT",
        "probe_id": "H024-PIT-XML-SEMANTICS-V1",
        "purpose": (
            "Source-only semantic inventory of current NSE Regulation 7(2) raw XBRL documents. "
            "No market-price, benchmark-return, or future-outcome data consumed."
        ),
        "generated_at_utc": datetime.now(UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "source_window": {
            "from_date": args.from_date,
            "to_date": args.to_date,
            "discovery_endpoint": "https://www.nseindia.com/api/corporates-pit-gg",
        },
        "sampling_contract": {
            "eligible_regulation": "Regulation 7 (2)",
            "submission_types": ["Original", "Revision"],
            "originals_per_month": args.originals_per_month,
            "revision_limit": args.revision_limit,
            "selection": (
                "chronological deterministic first distinct symbols per month plus latest revisions"
            ),
        },
        "summary": {
            "discovery_row_count": len(rows),
            "selected_document_count": len(selected),
            "complete_document_count": statuses["COMPLETE"],
            "failed_document_count": statuses["FAILED"],
            "sample_symbol_count": len(
                {row["symbol"] for row in reports if row.get("symbol")}
            ),
            "aggregate_concept_count": len(aggregate_concepts),
        },
        "aggregate_concept_counts": dict(aggregate_concepts.most_common()),
        "document_reports": reports,
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }
    _write_json(args.out, report)
    print(json.dumps(report["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
