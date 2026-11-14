"""Retain complete statements and annuals missing from the first metadata selection.

No document is overwritten. Case-only 32 MiB annual allowance leaves production
storage limits unchanged. Newspaper excerpts do not replace full statements.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from marketlab.company_change import ChangeError, canonical_hash
from marketlab.company_change_pipeline import check_url
from marketlab.company_change_store import EvidenceStore
from marketlab.nse import NSEClient

HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com", "efclimited.in", "www.efclimited.in",
         "www.nrail.com", "nrail.com", "www.balajiamines.com", "balajiamines.com"}
SOURCES = {
    "EFCIL_spv_sale": "https://nsearchives.nseindia.com/corporate/EFCILTD_05092026000338_EFC_Reg_30_-_Intimation_of_Sale_US.pdf",
    "NRAIL_full_results": "https://nsearchives.nseindia.com/corporate/NRAIL_03112026172319_OutcomeResults03112026.pdf",
    "NRAIL_agm_annual": "https://nsearchives.nseindia.com/corporate/NRAIL_04082026173237_SE_Intimation_Notice_of_AGM.pdf",
    "BALAMINES_full_results": "https://nsearchives.nseindia.com/corporate/BALAMINES_02112026183657_Outcome_Final.pdf",
    "BALAMINES_annual_full": "https://www.balajiamines.com/ar2026/assets/Balaji%20AR%202026.pdf",
    "BALAMINES_regulatory": "https://nsearchives.nseindia.com/corporate/BALAMINES_03112026183949_Disclosure_Signed.pdf",
    "BPL_annual_full": "https://nsearchives.nseindia.com/corporate/BPL_02092026184848_Revised_AR_2026.pdf",
}
INDEXES = {"EFCIL": "https://efclimited.in/investor-relation/annual-reports/",
           "NRAIL": "https://www.nrail.com/nrail-annual-reports"}


def fetch(url):
    with requests.Session() as client:
        client.trust_env = False
        for _ in range(4):
            check_url(url, HOSTS)
            with client.get(url, stream=True, allow_redirects=False, timeout=(10, 60),
                            headers={"User-Agent": "MarketLab-CC001/1.0 internal research"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = urljoin(url, response.headers.get("Location", ""))
                    continue
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 32 * 1024 * 1024:
                        raise ChangeError("case document exceeds 32 MiB")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                if not raw:
                    raise ChangeError("empty case source")
                return raw, url
        raise ChangeError("too many case source redirects")


def annual_link(raw, url):
    links = []
    for a in BeautifulSoup(raw, "html.parser").find_all("a", href=True):
        href = urljoin(url, a["href"])
        context = a.find_parent("tr") or a.parent
        text = context.get_text(" ", strip=True) + " " + href
        if href.lower().endswith(".pdf") and re.search(r"2025\s*[-–/]\s*(?:20)?26|2026", text):
            links.append(href)
    links = list(dict.fromkeys(links))
    if len(links) != 1:
        raise ChangeError("exact FY26 annual link unresolved")
    return links[0]


def capture(root):
    records, errors, total = [], [], 0
    with EvidenceStore(root) as store:
        folder = store.root / "supplements"
        folder.mkdir(exist_ok=True)
        def retain(name, url, supplied=None):
            nonlocal total
            raw, final = (supplied, url) if supplied is not None else fetch(url)
            total += len(raw)
            if total > 128 * 1024 * 1024:
                raise ChangeError("supplement acquisition budget exceeded")
            cap = store.capture(raw, {"url": url, "final_url": final,
                "origin": "HTTP_RESPONSE_BYTES", "lane": "NEXT-FOUR-SUPPLEMENTS"})
            suffix = ".pdf" if raw.startswith(b"%PDF") else ".json" if raw[:1] in (b"[", b"{") else ".html"
            path = folder / (name + suffix)
            path.write_bytes(raw)
            record = {"name": name, "url": url, "path": path.relative_to(root).as_posix(),
                      "raw_sha256": cap["raw_sha256"], "observed_at": cap["captured_at"]}
            records.append(record)
            if suffix == ".pdf":
                doc = PdfReader(io.BytesIO(raw))
                if doc.is_encrypted or len(doc.pages) > 450:
                    raise ChangeError("oversized/encrypted supplement")
                pages = [{"page": n + 1, "text": p.extract_text() or ""} for n, p in enumerate(doc.pages)]
                path.with_suffix(".pages.json").write_text(json.dumps(pages), encoding="utf-8")
                record["pages"] = len(pages)
            return raw
        for name, url in SOURCES.items():
            try:
                retain(name, url)
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, requests.RequestException) as exc:
                errors.append({"name": name, "url": url, "reason": str(exc)[:400]})
        for symbol, url in INDEXES.items():
            try:
                raw = retain(symbol + "_annual_index", url)
                retain(symbol + "_annual_full", annual_link(raw, url))
            except (ValueError, TypeError, KeyError, RuntimeError, OSError, requests.RequestException) as exc:
                errors.append({"name": symbol + "_annual_index", "url": url, "reason": str(exc)[:400]})
        client = NSEClient(timeout=20, attempts=2)
        try:
            rows, raw = client.corporate_announcements_with_raw("NRAIL", from_date="01-07-2026", to_date="31-07-2026")
            retain("NRAIL_july_rows", "https://www.nseindia.com/api/corporate-announcements", supplied=raw)
            rows = rows.get("data") if isinstance(rows, dict) else rows
            ratings = [r for r in rows if r.get("symbol") == "NRAIL" and "credit rating" in str(r.get("desc", "")).lower()]
            for n, row in enumerate(ratings[:2]):
                retain("NRAIL_rating_" + str(n), row["attchmntFile"])
        except (ValueError, TypeError, KeyError, RuntimeError, OSError, requests.RequestException) as exc:
            errors.append({"name": "NRAIL_july_rating", "reason": str(exc)[:400]})
        finally:
            client.session.close()
        report = {"records": records, "errors": errors, "observed_at": store.clock(),
                  "acquired_bytes": total, "model_called": False, "production_state_modified": False}
        report["report_sha256"] = canonical_hash(report)
        (root / "supplement-manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.workspace)
    print(json.dumps(result))
    raise SystemExit(int(bool(result["errors"])))
