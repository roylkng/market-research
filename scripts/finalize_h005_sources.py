"""Complete retained public filing sources using ordinary initialized NSE sessions."""
from __future__ import annotations

import argparse
import json
import threading
import time
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from acquire_h005_corpus import ALLOWED, dump, retain
from marketlab.nse import NSEClient

LOCAL = threading.local()


def fetch_initialized(root: Path, url: str, kind: str) -> dict:
    """Use the same public session for initialization and retrieval. No authentication."""
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED:
        raise ValueError("unsupported public source host")
    if not hasattr(LOCAL, "client"):
        LOCAL.client = NSEClient(timeout=18, attempts=1)
        LOCAL.client._initialize_session()
    try:
        response = LOCAL.client.session.get(url, timeout=(8, 18))
        if urlparse(response.url).hostname not in ALLOWED:
            raise ValueError("unexpected source redirect")
        response.raise_for_status()
        raw = response.content
        if not raw or len(raw) > 20_000_000:
            raise ValueError("empty or oversized source")
        document = ET.fromstring(raw)
        if document.tag.rsplit("}", 1)[-1].lower() != "xbrl":
            raise ValueError("source does not contain an XBRL root")
        result = retain(root, raw, url, kind)
        result["client"] = "INITIALIZED_PUBLIC_NSE_SESSION"
        return result
    except Exception as exc:
        return {"url": url, "kind": kind, "status": "FETCH_FAILED", "error": str(exc)}
    finally:
        time.sleep(0.03)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    root = Path(parser.parse_args().root)
    candidates = json.loads((root / "candidate-events-v3.json").read_text())
    previous = json.loads((root / "content-manifest-v3.json").read_text())
    available = {m["url"]: m for m in previous if m["status"] == "OK"}
    work = {}
    for candidate in candidates:
        for role in ("current", "prior"):
            record = candidate.get(role)
            if record and record["url"] not in available:
                work[record["url"]] = role + "-initialized-xbrl"
    restored = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch_initialized, root, url, kind) for url, kind in sorted(work.items())]
        for future in as_completed(futures):
            restored.append(future.result())
            if len(restored) % 500 == 0:
                print("initialized sources", len(restored), "/", len(work), flush=True)
    restored.sort(key=lambda r: r["url"])
    available.update({m["url"]: m for m in restored if m["status"] == "OK"})
    for candidate in candidates:
        for role in ("current", "prior"):
            record = candidate.get(role)
            if record and record["url"] in available:
                record["content_url"] = record["url"]
    dump(root / "initialized-source-manifest.json", restored)
    dump(root / "content-manifest-v4.json", previous + restored)
    dump(root / "candidate-events-v4.json", candidates)
    summary = {
        "status": "SOURCE_RECOVERY_NOT_MODEL_VALIDATION",
        "requests": len(work),
        "request_status": dict(Counter(m["status"] for m in restored)),
        "candidate_variant_rows": len(candidates),
        "current_original_available": sum(c["current"].get("content_url", c["current"]["url"]) in available for c in candidates),
        "prior_original_available": sum(c["prior"] is not None and c["prior"].get("content_url", c["prior"]["url"]) in available for c in candidates),
        "holdout_returns_opened": False,
        "live_capital_allowed": False,
    }
    dump(root / "initialized-source-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
