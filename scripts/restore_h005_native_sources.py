"""Recover public native filings with the repository's established archive client."""
from __future__ import annotations

import argparse
import json
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from acquire_h005_corpus import dump, retain
from marketlab.nse import NSEClient

LOCAL = threading.local()
CALENDAR_DOCUMENTS = (
    "CMTR65587.pdf", "CMTR71775.pdf", "CMTR70319.pdf", "CMTR72349.pdf",
    "CMTR73362.pdf", "CMTR75479.pdf",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    root = Path(parser.parse_args().root)
    candidates = json.loads((root / "candidate-events-v2.json").read_text())
    old_manifest = json.loads((root / "content-manifest-v2.json").read_text())
    available = {m["url"]: m for m in old_manifest if m["status"] == "OK"}
    work = {}
    for candidate in candidates:
        for role in ("current", "prior"):
            record = candidate.get(role)
            if record and record["url"] not in available:
                work[record["url"]] = role + "-native-xbrl"
    for filename in CALENDAR_DOCUMENTS:
        work["https://nsearchives.nseindia.com/content/circulars/" + filename] = "calendar-circular"

    def fetch(item):
        url, kind = item
        if not hasattr(LOCAL, "client"):
            LOCAL.client = NSEClient(timeout=18, attempts=1)
        try:
            return retain(root, LOCAL.client.archive_bytes(url), url, kind)
        except Exception as exc:
            # One attempt per original URL. No proxies, alternate credentials or login bypass.
            return {"url": url, "kind": kind, "status": "FETCH_FAILED", "error": str(exc)}

    restored = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch, item) for item in sorted(work.items())]
        for future in as_completed(futures):
            restored.append(future.result())
            if len(restored) % 250 == 0:
                print("restored", len(restored), "/", len(work), flush=True)
    restored.sort(key=lambda m: m["url"])
    available.update({m["url"]: m for m in restored if m["status"] == "OK"})
    for candidate in candidates:
        for role in ("current", "prior"):
            record = candidate.get(role)
            if record and record["url"] in available:
                record["content_url"] = record["url"]
    dump(root / "native-restoration-manifest.json", restored)
    dump(root / "candidate-events-v3.json", candidates)
    dump(root / "content-manifest-v3.json", old_manifest + restored)
    summary = {
        "status": "SOURCE_RESTORATION_NOT_VALIDATION",
        "client": "marketlab.nse.NSEClient.archive_bytes",
        "requests": len(work),
        "request_status": dict(Counter(m["status"] for m in restored)),
        "candidate_variant_rows": len(candidates),
        "current_original_available": sum(c["current"].get("content_url", c["current"]["url"]) in available for c in candidates),
        "prior_original_available": sum(c["prior"] is not None and c["prior"].get("content_url", c["prior"]["url"]) in available for c in candidates),
        "holdout_returns_opened": False,
        "live_capital_allowed": False,
    }
    dump(root / "restoration-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
