"""Sequential public-source recovery. Denials are retained, never treated as missing values."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import requests
from acquire_h005_corpus import ALLOWED, dump, retain

from marketlab.nse import NSEAcquisitionError, NSEClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    root = Path(parser.parse_args().root)
    candidates = json.loads((root / "candidate-events-v4.json").read_text())
    previous = json.loads((root / "content-manifest-v4.json").read_text())
    available = {m["url"]: m for m in previous if m["status"] == "OK"}
    work = {}
    for candidate in candidates:
        for role in ("current", "prior"):
            record = candidate.get(role)
            if record and record["url"] not in available:
                work.setdefault(record["url"], role)
    # Deterministic distribution across issuers and dates, independent of labels.
    ordered = sorted(work, key=lambda url: hashlib.sha256(url.encode()).hexdigest())
    client = NSEClient(timeout=15, attempts=1)
    client._initialize_session()
    results = []
    interval = 0.20
    consecutive_denials = 0
    started = time.monotonic()
    stop_reason = None
    for url in ordered:
        if time.monotonic() - started > 2100:
            stop_reason = "BOUNDED_RUN_CHECKPOINT"
            break
        if urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED:
            raise ValueError("unsupported source host")
        request_started = time.monotonic()
        try:
            response = client.session.get(url, timeout=(8, 15))
            if urlparse(response.url).hostname not in ALLOWED:
                raise ValueError("unexpected public source redirect")
            if response.status_code in (403, 429):
                consecutive_denials += 1
                interval = max(interval, 0.75)
                record = {"url": url, "kind": work[url] + "-serial-xbrl", "status": "HTTP_DENIED",
                          "http_status": response.status_code, "retry_after": response.headers.get("Retry-After")}
                results.append(record)
                dump(root / "serial-source-manifest.json", results)
                if consecutive_denials >= 3:
                    stop_reason = "REPEATED_DENIALS_STOPPED_WITHOUT_BYPASS"
                    break
                retry = response.headers.get("Retry-After", "")
                time.sleep(min(120, max(15, float(retry))) if retry.isdigit() else 15)
                continue
            response.raise_for_status()
            raw = response.content
            if not raw or len(raw) > 20_000_000:
                raise ValueError("empty or oversized filing")
            document = ET.fromstring(raw)
            if document.tag.rsplit("}", 1)[-1].lower() != "xbrl":
                raise ValueError("not an XBRL document")
            meta = retain(root, raw, url, work[url] + "-serial-xbrl")
            meta["client"] = "SEQUENTIAL_INITIALIZED_PUBLIC_NSE_SESSION"
            results.append(meta)
            available[url] = meta
            consecutive_denials = 0
        except (NSEAcquisitionError, ET.ParseError, requests.RequestException, ValueError) as exc:
            results.append({"url": url, "kind": work[url] + "-serial-xbrl",
                            "status": "FETCH_FAILED", "error": str(exc)})
        finally:
            time.sleep(max(0, interval - (time.monotonic() - request_started)))
        if len(results) % 100 == 0:
            dump(root / "serial-source-manifest.json", results)
            print("serial sources", len(results), "/", len(ordered), dict(Counter(m["status"] for m in results)), flush=True)
    for candidate in candidates:
        for role in ("current", "prior"):
            record = candidate.get(role)
            if record and record["url"] in available:
                record["content_url"] = record["url"]
    dump(root / "serial-source-manifest.json", results)
    dump(root / "content-manifest-v5.json", previous + results)
    dump(root / "candidate-events-v5.json", candidates)
    summary = {
        "status": "SOURCE_ACQUISITION_NOT_MODEL_VALIDATION",
        "planned_requests": len(ordered), "attempted_requests": len(results),
        "request_status": dict(Counter(m["status"] for m in results)),
        "stop_reason": stop_reason,
        "candidate_variant_rows": len(candidates),
        "current_original_available": sum(c["current"].get("content_url", c["current"]["url"]) in available for c in candidates),
        "prior_original_available": sum(c["prior"] is not None and c["prior"].get("content_url", c["prior"]["url"]) in available for c in candidates),
        "holdout_returns_opened": False, "live_capital_allowed": False,
    }
    dump(root / "serial-source-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
