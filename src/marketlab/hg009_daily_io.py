"""Shared safe IO contracts for HG009 P002 entrypoint and verifier.

Keep standalone CLI imports independent of the working directory's `scripts`
package, so GitHub runners and local execution behave identically.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError
from marketlab.hg009_daily import H021_SOURCE_DIR

CALENDAR = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)
CONTROL = Path("research/hg009/hg009-p001-matched-300-company-controls-v1.json")
DAILY_OUTPUT = Path("research/hg009/daily")


def load_json_source(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"HG009 expected JSON source: {path}")
    return data


def original_source_bytes(
    root: Path, receipt: dict[str, Any], *, suffix: str
) -> bytes:
    if suffix not in {".zip", ".csv"}:
        raise AlphaContractError("HG009 original source type unsupported")
    sha = receipt.get("sha256")
    if (
        not isinstance(sha, str)
        or len(sha) != 64
        or any(c not in "0123456789abcdef" for c in sha)
    ):
        raise AlphaContractError("HG009 source SHA missing or malformed")
    file = root / H021_SOURCE_DIR / "raw" / "sha256" / f"{sha}{suffix}"
    if not file.is_file():
        raise AlphaContractError(f"HG009 original NSE source absent: {file}")
    raw = file.read_bytes()
    if (
        hashlib.sha256(raw).hexdigest() != sha
        or len(raw) != receipt.get("byte_count")
    ):
        raise AlphaContractError(f"HG009 original NSE byte mismatch: {file}")
    return raw
