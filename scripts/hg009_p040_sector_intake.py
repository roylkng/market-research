#!/usr/bin/env python3
"""HG009 P040: original-document intake, NOT industry classification or trial admission.

Usage:
 python scripts/hg009_p040_sector_intake.py --manifest source_manifest.csv --out .marketlab/hg009-p040
 CSV columns: symbol,isin,url. Supply independently identified original HTTPS issuer/exchange URLs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

REPO = Path(__file__).resolve().parents[1]
QUEUE = REPO / "research/hg009/hg009-p030-sector-proof-queue-v1.json"
MAX_BYTES = 30 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_source_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("source URL must be public HTTPS without credentials")
    if parts.port not in (None, 443):
        raise ValueError("nonstandard HTTPS port forbidden")
    if parts.fragment:
        raise ValueError("URL fragment forbidden")
    hostname = parts.hostname
    # DNS check at request time is also enforced by the configured egress proxy.
    if hostname == "localhost" or hostname.endswith(".local") or hostname.endswith(".internal"):
        raise ValueError("local destination forbidden")
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if "." not in hostname:
            raise ValueError("single-label destination forbidden")
    else:
        if not ip.is_global:
            raise ValueError("nonpublic destination forbidden")
    return value


def identities(queue: dict) -> dict[tuple[str, str], str]:
    records = queue["future_source_collection_queue"]
    if len(records) != 300:
        raise ValueError("original queue must contain 300 identities")
    result: dict[tuple[str, str], str] = {}
    for item in records:
        key = (item["original_symbol"], item["frozen_isin"])
        if key in result:
            raise ValueError("duplicate frozen identity")
        result[key] = item["arm"]
    return result


def fetch_original(url: str) -> bytes:
    validate_source_url(url)
    opener = build_opener(NoRedirect())
    req = Request(url, headers={"User-Agent": "marketlab-research-evidence/1.0"})
    with opener.open(req, timeout=20) as response:
        if response.status != 200 or urlsplit(response.geturl()).geturl() != url:
            raise ValueError("non-200 or redirected source")
        size = response.headers.get("Content-Length")
        if size is not None and int(size) > MAX_BYTES:
            raise ValueError("source exceeds max bytes")
        data = response.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("empty or oversized document")
    return data


def persist(out: Path, symbol: str, isin: str, arm: str, url: str,
            data: bytes, observed_utc: str, queue_sha256: str) -> Path:
    """Create content-addressed evidence; never overwrite a differing receipt."""
    if not data:
        raise ValueError("empty evidence")
    raw_sha = digest(data)
    raw_dir = out / "raw"
    receipt_dir = out / "receipts"
    raw_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / raw_sha
    if raw_path.exists():
        if raw_path.read_bytes() != data:
            raise ValueError("content-addressed blob collision")
    else:
        fd, tmp = tempfile.mkstemp(dir=raw_dir)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
            os.link(tmp, raw_path)  # never replace existing source bytes
        except FileExistsError:
            if raw_path.read_bytes() != data:
                raise ValueError("concurrent original byte disagreement")
        finally:
            os.unlink(tmp)
    receipt = {
        "schema": "HG009-P040-SOURCE-RECEIPT-v1",
        "symbol": symbol, "isin": isin, "arm": arm,
        "source_url": url,
        "first_retrieved_at_utc": observed_utc,
        "raw_sha256": raw_sha, "raw_byte_length": len(data),
        "queue_sha256": queue_sha256,
        "classification": None, "classification_verified": False,
        "preentry_eligible": False, "trial_admitted": False,
    }
    payload = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    receipt_path = receipt_dir / f"{symbol}-{isin}-{raw_sha}.json"
    if receipt_path.exists():
        # A previous observation is never overwritten by a later fetch.
        old = json.loads(receipt_path.read_text())
        for field in ("symbol", "isin", "arm", "source_url", "raw_sha256", "queue_sha256"):
            if old[field] != receipt[field]:
                raise ValueError("receipt identity/source conflict")
        return receipt_path
    fd, tmp = tempfile.mkstemp(dir=receipt_dir)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        try:
            os.link(tmp, receipt_path)
        except FileExistsError:
            return persist(out, symbol, isin, arm, url, data, observed_utc, queue_sha256)
    finally:
        os.unlink(tmp)
    return receipt_path


def run(manifest: Path, out: Path, queue_path: Path = QUEUE) -> dict:
    queue_bytes = queue_path.read_bytes()
    known = identities(json.loads(queue_bytes))
    with manifest.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or set(reader.fieldnames) != {"symbol", "isin", "url"}:
            raise ValueError("manifest needs exactly symbol,isin,url columns")
        rows = list(reader)
    if len(rows) > 300:
        raise ValueError("manifest exceeds fixed queue")
    seen: set[tuple[str, str, str]] = set()
    results = []
    for row in rows:
        symbol, isin, url = row["symbol"], row["isin"], row["url"]
        key = (symbol, isin)
        if key not in known:
            raise ValueError(f"not in frozen cohort: {symbol}/{isin}")
        validate_source_url(url)
        identity = (symbol, isin, url)
        if identity in seen:
            raise ValueError("duplicate input source")
        seen.add(identity)
        try:
            data = fetch_original(url)
            observed = datetime.now(timezone.utc).isoformat()
            receipt_path = persist(out, symbol, isin, known[key], url, data,
                                   observed, digest(queue_bytes))
            results.append({"symbol": symbol, "isin": isin, "status": "RECEIPT_ONLY",
                            "receipt": str(receipt_path)})
        except Exception as exc:
            # Failed sources must never become classifications or successes.
            results.append({"symbol": symbol, "isin": isin, "status": "SOURCE_ERROR",
                            "reason": type(exc).__name__ + ": " + str(exc)})
    return {"requested": len(rows), "receipt_only": sum(r["status"] == "RECEIPT_ONLY" for r in results),
            "classified": 0, "trial_admitted": 0, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.out), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
