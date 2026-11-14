"""Bounded original-source capture for the next four company evaluations.

Isolated research only. Historical references never become prospective fills.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from pypdf import PdfReader

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_context import discover_history, parse_document, source_time
from marketlab.company_change_pipeline import fetch_original
from marketlab.company_change_prices import parse_bhavcopy
from marketlab.company_change_store import EvidenceStore
from marketlab.nse import NSEClient

COMPANIES = {
    "EFCIL": {"isin": "INE886D01026", "scope": "CONSOLIDATED"},
    "NRAIL": {"isin": "INE740D01017", "scope": "STANDALONE"},
    "BALAMINES": {"isin": "INE050E01027", "scope": "CONSOLIDATED"},
    "BPL": {"isin": "INE110A01019", "scope": "CONSOLIDATED"},
}
HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
WINDOWS = (("01-08-2026", "31-08-2026"), ("01-09-2026", "30-09-2026"),
           ("01-10-2026", "31-10-2026"), ("01-11-2026", "10-11-2026"))
GROUPS = (
    ("annual", r"annual report", 1),
    ("results", r"financial results|outcome of board", 1),
    ("presentation", r"investor presentation", 1),
    ("transcript", r"transcript", 1),
    ("risk_funding", r"credit rating|allotment|warrant|rights issue|litigation|warning|regulatory action|order.*authority", 3),
    ("operations", r"commercial production|commencement|capacity addition|acquisition|sale of|general update", 2),
)


def select(rows: list, symbol: str) -> list[dict]:
    """Metadata only locates originals, never supplies financial facts."""
    valid = []
    for row in rows:
        if not isinstance(row, dict) or row.get("symbol") != symbol:
            continue
        url = row.get("attchmntFile")
        if not isinstance(url, str) or not url.lower().endswith(".pdf"):
            continue
        try:
            published = source_time(row["an_dt"]).isoformat()
        except (ValueError, TypeError, KeyError):
            continue
        if published[:10] > "2026-11-10":
            continue
        valid.append((published, url, row))
    valid.sort(reverse=True, key=lambda r: (r[0], r[1]))
    selected, seen = [], set()
    for group, pattern, limit in GROUPS:
        count = 0
        for published, url, row in valid:
            text = " ".join(str(row.get(k, "")) for k in ("desc", "attchmntText"))
            if url in seen or not re.search(pattern, text, re.IGNORECASE):
                continue
            selected.append({"group": group, "url": url, "published_at": published,
                             "exchange_row": row, "row_sha256": canonical_hash(row)})
            seen.add(url)
            count += 1
            if count == limit:
                break
    return selected


def capture(workspace: Path) -> dict:
    sources, errors, companies = [], [], []
    total_bytes = 0
    with EvidenceStore(workspace) as store:
        original = store.root / "originals"
        original.mkdir(exist_ok=True)
        def retain(name, url, metadata=None, supplied=None):
            nonlocal total_bytes
            raw, final = (supplied, url) if supplied is not None else fetch_original(url, HOSTS)
            if total_bytes + len(raw) > 240 * 1024 * 1024:
                raise ChangeError("four-company source budget exceeded")
            total_bytes += len(raw)
            cap = store.capture(raw, {"url": url, "final_url": final, "origin": "HTTP_RESPONSE_BYTES",
                                     "case": "NEXT-FOUR-20261110", **(metadata or {})})
            suffix = ".pdf" if raw.startswith(b"%PDF") else ".json" if raw[:1] in (b"[", b"{") else ".xml"
            target = original / (name + suffix)
            target.write_bytes(raw)
            record = {"name": name, "url": url, "raw_sha256": cap["raw_sha256"],
                      "capture_id": cap["id"], "observed_at": cap["captured_at"],
                      "path": target.relative_to(store.root).as_posix(), "bytes": len(raw),
                      "metadata": metadata or {}}
            sources.append(record)
            if suffix == ".pdf":
                pdf = PdfReader(io.BytesIO(raw))
                if pdf.is_encrypted or len(pdf.pages) > 450:
                    raise ChangeError("original PDF exceeds bounded review size")
                pages = [{"page": i + 1, "text": page.extract_text() or ""} for i, page in enumerate(pdf.pages)]
                target.with_suffix(".pages.json").write_text(json.dumps(pages), encoding="utf-8")
                record["pages"] = len(pages)
            return raw, record
        for symbol, fields in COMPANIES.items():
            ident = {"symbol": symbol, **fields}
            client = NSEClient(timeout=20, attempts=2)
            result = {"identity": ident, "financial_periods": [], "disclosure_count_received": 0}
            try:
                try:
                    history, receipts = discover_history(client, store, ident, "2026-09-30")
                    result["history_receipts"] = receipts
                    selected = [x for x in history if x["period_end"] in {
                        "2026-09-30", "2026-06-30", "2026-03-31", "2025-09-30", "2025-03-31"}]
                    for item in selected[:5]:
                        try:
                            raw, rec = retain(symbol + "_" + item["period_end"], item["url"], item)
                            result["financial_periods"] += parse_document(raw, item["url"], ident,
                                rec["observed_at"], item["published_at"], store=store)
                        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                            errors.append({"symbol": symbol, "stage": "financial_document", "url": item["url"], "reason": str(exc)[:400]})
                except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                    errors.append({"symbol": symbol, "stage": "history", "reason": str(exc)[:400]})
                announcements = []
                for start, end in WINDOWS:
                    try:
                        payload, raw = client.corporate_announcements_with_raw(symbol, from_date=start, to_date=end)
                        url = client.CORPORATE_ANNOUNCEMENT_ENDPOINT.url + "?" + urlencode({
                            "index": "equities", "symbol": symbol, "from_date": start, "to_date": end})
                        retain(symbol + "_announcements_" + start, url, supplied=raw)
                        rows = payload.get("data") if isinstance(payload, dict) else payload
                        if not isinstance(rows, list):
                            raise ChangeError("announcement source lacks a row list")
                        announcements += rows
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                        errors.append({"symbol": symbol, "stage": "announcements", "reason": str(exc)[:400]})
                result["disclosure_count_received"] = len(announcements)
                for i, item in enumerate(select(announcements, symbol)):
                    try:
                        retain(symbol + "_" + item["group"] + "_" + str(i), item["url"], item)
                    except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                        errors.append({"symbol": symbol, "stage": "disclosure", "url": item["url"], "reason": str(exc)[:400]})
            finally:
                client.session.close()
            companies.append(result)
        quotes = []
        try:
            url = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261109_F_0000.csv.zip"
            raw, final_url = fetch_original(url, HOSTS)
            cap = store.capture(raw, {"url": url, "final_url": final_url, "origin": "HTTP_RESPONSE_BYTES"})
            (original / "prices_20261109.zip").write_bytes(raw)
            for symbol, fields in COMPANIES.items():
                q = parse_bhavcopy(raw, {"symbol": symbol, **fields}, date(2026, 11, 9), cap["captured_at"])
                quotes.append({**q, "source_url": url, "reference_only_not_current_fill": True})
        except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
            errors.append({"stage": "price", "reason": str(exc)[:400]})
        report = {"case": "NEXT-FOUR-20261110", "observed_at": store.clock(), "sources": sources,
                  "companies": companies, "quotes": quotes, "errors": errors,
                  "acquired_bytes": total_bytes, "live_capital_allowed": False, "model_called": False,
                  "scope": "BOUNDED_PRIMARY_SOURCE_REVIEW_NOT_ALL_MARKET_OR_AUTONOMOUS_FACT_APPROVAL"}
        report["report_sha256"] = canonical_hash(report)
        (store.root / "capture-manifest.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.workspace)
    print(json.dumps({k: v for k, v in result.items() if k not in {"sources", "companies"}}, indent=2))
    raise SystemExit(int(bool(result["errors"])))
