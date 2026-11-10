"""Bounded original-source acquisition for one KRSNAA underwriting case.

No production-state write, model call, investment approval or backdated entry.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path
from urllib.parse import urlencode

from pypdf import PdfReader

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_pipeline import fetch_original
from marketlab.company_change_prices import archive_close
from marketlab.company_change_store import EvidenceStore
from marketlab.nse import NSEClient

IDENTITY = {"symbol": "KRSNAA", "isin": "INE08LI01020", "scope": "CONSOLIDATED"}
HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com", "krsnaadiagnostics.com",
         "www.krsnaadiagnostics.com", "www.icra.in", "icra.in"}
FILES = {
    "h1fy27_results": "https://nsearchives.nseindia.com/corporate/KRSNAA_02112026150758_543328_1_.pdf",
    "h1fy27_presentation": "https://nsearchives.nseindia.com/corporate/KRSNAA_02112026184753_543328.pdf",
    "h1fy27_transcript": "https://nsearchives.nseindia.com/corporate/KRSNAA_07112026191611_543328_Signed__1_.pdf",
    "delhi_project": "https://nsearchives.nseindia.com/corporate/KRSNAA_03112026143546_543328.pdf",
    "credit_20260629": "https://nsearchives.nseindia.com/corporate/KRSNAA_29062026173557_543328.pdf",
    "fy26_results": "https://krsnaadiagnostics.com/investor-docs/2026/Financial%20Results/Financial%20Results%20for%20the%20quarter%20and%20year%20ended%20March%2031%2C%202026.pdf",
    "fy26_presentation": "https://nsearchives.nseindia.com/corporate/KRSNAA_25052026234133_543328_Investor_Presentation.pdf",
    "h1fy27_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1751044_02112026032524_WEB.xml",
    "h1fy26_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1568517_07112025074342_WEB.xml",
    "fy26_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1672754_25052026090920_WEB.xml",
    "fy25_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1436740_12052025091029_WEB.xml",
    "q1fy27_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1714189_14082026123032_WEB.xml",
}
WINDOWS = (("01-09-2026", "30-09-2026"), ("01-10-2026", "31-10-2026"),
           ("01-11-2026", "10-11-2026"))


def selected_disclosures(rows: list) -> list[dict]:
    """Bounded source locator, not a ranking or semantic verification."""
    patterns = (r"annual report", r"allotment|warrant|preferential", r"income tax|appellate",
                r"sale of|equipment|capital efficien|monetiz", r"transcript", r"general update")
    result, seen = [], set(FILES.values())
    for pattern in patterns:
        taken = 0
        for row in rows:
            if not isinstance(row, dict) or row.get("symbol") != IDENTITY["symbol"]:
                continue
            url = row.get("attchmntFile")
            label = " ".join(str(row.get(k, "")) for k in ("desc", "attchmntText"))
            if (isinstance(url, str) and url.lower().endswith(".pdf") and url not in seen
                    and re.search(pattern, label, re.IGNORECASE)):
                result.append({"url": url, "row": row, "row_sha256": canonical_hash(row)})
                seen.add(url)
                taken += 1
                if len(result) >= 8:
                    return result
                if taken >= 2:
                    break
    return result


def capture(workspace: Path) -> dict:
    errors, sources, discovered = [], [], []
    client = NSEClient(timeout=20, attempts=2)
    total_bytes = 0
    with EvidenceStore(workspace) as store:
        originals = store.root / "originals"
        originals.mkdir(exist_ok=True)
        def retain(name, url, metadata=None):
            nonlocal total_bytes
            try:
                raw, final_url = fetch_original(url, HOSTS)
                if total_bytes + len(raw) > 160 * 1024 * 1024:
                    raise ChangeError("case acquisition byte budget exceeded")
                total_bytes += len(raw)
                cap = store.capture(raw, {"url": url, "final_url": final_url,
                    "origin": "HTTP_RESPONSE_BYTES", "case": "KRSNAA-20261110", **(metadata or {})})
                is_pdf = raw.startswith(b"%PDF")
                suffix = ".pdf" if is_pdf else ".xml"
                path = originals / (name + suffix)
                path.write_bytes(raw)
                record = {"name": name, "url": url, "sha256": cap["raw_sha256"],
                    "capture_id": cap["id"], "observed_at": cap["captured_at"],
                    "bytes": len(raw), "path": str(path.relative_to(store.root))}
                sources.append(record)
                if is_pdf:
                    reader = PdfReader(io.BytesIO(raw))
                    if reader.is_encrypted or len(reader.pages) > 400:
                        raise ChangeError("PDF exceeds case page limit")
                    pages = [{"page": i + 1, "text": p.extract_text() or ""}
                             for i, p in enumerate(reader.pages)]
                    (originals / (name + ".pages.json")).write_text(json.dumps(pages), encoding="utf-8")
                    record["pages"] = len(pages)
            except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
                errors.append({"name": name, "url": url, "reason": str(exc)[:400]})
        try:
            for start, end in WINDOWS:
                try:
                    payload, raw = client.corporate_announcements_with_raw("KRSNAA", from_date=start, to_date=end)
                    url = client.CORPORATE_ANNOUNCEMENT_ENDPOINT.url + "?" + urlencode({
                        "index": "equities", "symbol": "KRSNAA", "from_date": start, "to_date": end})
                    cap = store.capture(raw, {"url": url, "origin": "HTTP_RESPONSE_BYTES", "case": "KRSNAA-20261110"})
                    rows = payload.get("data") if isinstance(payload, dict) else payload
                    if not isinstance(rows, list):
                        raise ChangeError("announcement response lacks row list")
                    (originals / ("announcements_" + start + ".json")).write_bytes(raw)
                    sources.append({"name": "discovery_" + start, "url": url,
                        "sha256": cap["raw_sha256"], "observed_at": cap["captured_at"],
                        "path": "originals/announcements_" + start + ".json", "bytes": len(raw)})
                    discovered += selected_disclosures(rows)
                except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
                    errors.append({"stage": "discovery", "window": [start, end], "reason": str(exc)[:400]})
            for name, url in FILES.items():
                retain(name, url)
            seen = set(FILES.values())
            for i, item in enumerate(discovered[:24]):
                if item["url"] not in seen:
                    retain(f"discovered_{i:02d}", item["url"], {"exchange_row": item["row"],
                           "exchange_row_sha256": item["row_sha256"]})
                    seen.add(item["url"])
            quote = None
            try:
                quote = archive_close(store, IDENTITY)
            except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
                errors.append({"stage": "price", "reason": str(exc)[:400]})
            report = {"case": "KRSNAA-20261110", "identity": IDENTITY, "observed_at": store.clock(),
                      "sources": sources, "quote": quote, "errors": errors,
                      "acquired_document_bytes": total_bytes, "live_capital_allowed": False,
                      "model_called": False, "source_semantics_verified": False}
            report["report_sha256"] = canonical_hash(report)
            (store.root / "capture-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report
        finally:
            client.session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.workspace)
    print(json.dumps(result, indent=2))
    raise SystemExit(int(bool(result["errors"])))
