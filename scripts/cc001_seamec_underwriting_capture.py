"""Bounded original-source capture for a specific investment case, not a backtest.

No production state or model inference. Retain acquisition clocks and failures.
The public exchange response locates filings, but does not verify their semantics.
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

IDENTITY = {"symbol": "SEAMECLTD", "isin": "INE497B01018", "scope": "CONSOLIDATED"}
HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com", "seamec.in", "www.seamec.in"}
FILES = {
    "annual_fy26": "https://seamec.in/upload/01-09-2026SEAMEC%20LIMITED_ANNUAL%20REPORT%202025-26_2MB.pdf",
    "board_results_20261103": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_03112026160546_OutcomeofBoardMeetingBSENSE03112026.pdf",
    "board_results_fy26": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_18052026184817_OutcomeofBM18May2026.pdf",
    "anant_takeover": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_14102026160821_NSEBSETakeoverofVesselSEAMECANANT14102026.pdf",
    "anant_charter": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_21102026170338_NSEBSECharterwithHALforSEAMECANANT2102026.pdf",
    "credit_revision": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_14102026124556_NSEBSECreditRating14102026.pdf",
    "commencement_20261108": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_08112026134330_BSENSECommencementPRPXSEAMECPRINCESS08112026.pdf",
    "award_20261107": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_07112026190157_BSENSELOAconsortiumPOSHSEAMECPRPX07112026.pdf",
    "presentation_20261103": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_03112026174156_BSENSEIntimationofInvestorPResentation03112026.pdf",
    "presentation_20260518": "https://nsearchives.nseindia.com/corporate/SEAMECLTD_18052026201032_BSENSEIntimationofInvestorPResentation18052026.pdf",
    "fy26_concall": "https://seamec.in/upload/Earning%20Concall%20Transcript%20for%20Q4%20FY%202026.pdf",
    "h1fy27_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1751839_03112026043640_WEB.xml",
    "h1fy26_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1569779_10112025040345_WEB.xml",
    "fy26_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1668874_18052026065814_WEB.xml",
    "fy25_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1453562_27052025081801_WEB.xml",
    "q1fy27_xml": "https://nsearchives.nseindia.com/corporate/xbrl/INTEGRATED_FILING_INDAS_1714033_13082026075718_WEB.xml",
}


def selected_disclosures(rows: list) -> list[dict]:
    """A bounded source locator, not a materiality classifier or a market census."""
    result, seen = [], set(FILES.values())
    patterns = (r"annual report", r"financial results|outcome of board", r"shareholding",
                r"transcript", r"anant", r"gallant")
    for pattern in patterns:
        for row in rows:
            if not isinstance(row, dict) or row.get("symbol") != IDENTITY["symbol"]:
                continue
            url = row.get("attchmntFile", "")
            label = " ".join(str(row.get(k, "")) for k in ("desc", "attchmntText"))
            if re.search(pattern, label, re.IGNORECASE) and isinstance(url, str) and url.endswith(".pdf") and url not in seen:
                result.append({"url": url, "row_sha256": canonical_hash(row), "row": row})
                seen.add(url)
                if len(result) >= 12:
                    return result
                # One latest matching source per window/category is enough for this case.
                break
    return result


def capture(workspace: Path) -> dict:
    errors, sources, discovered = [], [], []
    client = NSEClient(timeout=20, attempts=2)
    with EvidenceStore(workspace) as store:
        def retain(name: str, url: str, metadata: dict | None = None):
            try:
                raw, final_url = fetch_original(url, HOSTS)
                cap = store.capture(raw, {"url": url, "final_url": final_url,
                    "origin": "HTTP_RESPONSE_BYTES", "case": "SEAMEC-20261109", **(metadata or {})})
                is_pdf = raw.startswith(b"%PDF")
                suffix = ".pdf" if is_pdf else ".xml"
                originals = store.root / "originals"
                originals.mkdir(exist_ok=True)
                (originals / (name + suffix)).write_bytes(raw)
                record = {"name": name, "url": url, "sha256": cap["raw_sha256"],
                          "observed_at": cap["captured_at"], "bytes": len(raw),
                          "capture_id": cap["id"], "path": "originals/" + name + suffix}
                sources.append(record)
                if is_pdf:
                    reader = PdfReader(io.BytesIO(raw))
                    if len(reader.pages) > 500:
                        raise ChangeError("PDF page bound exceeded")
                    text = [{"page": i + 1, "text": page.extract_text() or ""}
                            for i, page in enumerate(reader.pages)]
                    (originals / (name + ".pages.json")).write_text(json.dumps(text), encoding="utf-8")
                    record["pages"] = len(text)
            except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
                errors.append({"stage": "document", "name": name, "url": url,
                               "reason": type(exc).__name__ + ": " + str(exc)[:400]})
        try:
            for start, end in (("01-09-2026", "03-09-2026"), ("10-10-2026", "25-10-2026"),
                               ("01-11-2026", "09-11-2026")):
                try:
                    payload, raw = client.corporate_announcements_with_raw("SEAMECLTD", from_date=start, to_date=end)
                    url = client.CORPORATE_ANNOUNCEMENT_ENDPOINT.url + "?" + urlencode({
                        "index": "equities", "symbol": "SEAMECLTD", "from_date": start, "to_date": end})
                    cap = store.capture(raw, {"url": url, "origin": "HTTP_RESPONSE_BYTES", "case": "SEAMEC-20261109"})
                    rows = payload.get("data") if isinstance(payload, dict) else payload
                    if not isinstance(rows, list):
                        raise ChangeError("announcement response has no row list")
                    discovered += selected_disclosures(rows)
                    sources.append({"name": "discovery_" + start, "url": url, "sha256": cap["raw_sha256"],
                                    "observed_at": cap["captured_at"], "bytes": len(raw)})
                except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
                    errors.append({"stage": "discovery", "window": [start, end], "reason": str(exc)[:400]})
            for name, url in FILES.items():
                retain(name, url)
            seen = set(FILES.values())
            for i, item in enumerate(discovered[:12]):
                if item["url"] not in seen:
                    retain(f"discovered_{i:02d}", item["url"], {"exchange_row_sha256": item["row_sha256"], "row": item["row"]})
                    seen.add(item["url"])
            quote = None
            try:
                quote = archive_close(store, IDENTITY)
            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                errors.append({"stage": "price", "reason": str(exc)[:400]})
            try:
                payload, raw = client.corporate_actions_with_raw("SEAMECLTD", from_date="01-04-2026", to_date="09-11-2026")
                url = client.CORPORATE_ACTION_ENDPOINT.url + "?" + urlencode({"index": "equities", "symbol": "SEAMECLTD", "from_date": "01-04-2026", "to_date": "09-11-2026"})
                cap = store.capture(raw, {"url": url, "origin": "HTTP_RESPONSE_BYTES", "case": "SEAMEC-20261109"})
                sources.append({"name": "corporate_actions", "url": url, "sha256": cap["raw_sha256"], "observed_at": cap["captured_at"]})
                (store.root / "corporate-actions.json").write_text(json.dumps(payload, indent=2))
            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
                errors.append({"stage": "corporate_actions", "reason": str(exc)[:400]})
            report = {"case": "SEAMEC-20261109", "observed_at": store.clock(), "identity": IDENTITY,
                      "sources": sources, "quote": quote, "errors": errors,
                      "live_capital_allowed": False, "source_accuracy_verified": False}
            report["report_sha256"] = canonical_hash(report)
            (store.root / "capture-manifest.json").write_text(json.dumps(report, indent=2))
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
