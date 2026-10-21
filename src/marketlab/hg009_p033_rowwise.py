"""HG009 P033: independently verify valid cells in official NSE Total Market CSV.

P032 rejected an entire ~750-member index when one bad row was encountered.
This independently registered 21-Oct-2026 successor does NOT modify P032,
relabel 15-Oct entrants, or guess missing company sectors. Only original NSE
symbol+ISIN+EQ+industry cells with unambiguous issuer identity qualify.

This index covers a SUBSET of Indian equities, not 2,319 NSE listings.
"""

from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import io
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p031_industry import frozen_members

PROTOCOL = "HG009-P033-NSE-TOTALMARKET-ROWWISE-PROVENANCE-v1"
SOURCE = "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"
METHOD_DATE = "2026-10-21"
FIRST_POSSIBLE_NEW_COHORT_DATE = "2026-10-22"
BASE = Path("research/hg009/p033-totalmarket-rowwise")
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
REQUIRED_FIELDS = ("Symbol", "ISIN Code", "Industry", "Series")
ISIN = re.compile(r"^IN[A-Z0-9]{10}$")
SYMBOL = re.compile(r"^[A-Z0-9&_.-]{1,35}$")
MIN_TOTAL_SOURCE_ROWS = 650
MAX_TOTAL_SOURCE_ROWS = 800
MIN_VERIFIED_SOURCE_ROWS = 650
MAX_INVALID_SOURCE_ROWS = 20
MIN_NEXT_TRIAL_PER_ARM = 90
MIN_NEXT_TRIAL_TOTAL = 285


def _time(value: str) -> datetime:
    try:
        t = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("P033 invalid original retrieval timestamp") from exc
    if t.tzinfo is None:
        raise AlphaContractError("P033 original retrieval must be timezone-aware")
    utc = t.astimezone(UTC)
    if utc.date().isoformat() < METHOD_DATE:
        raise AlphaContractError("P033 source observation predates method registration")
    return utc


def _nonempty_industry(value: str) -> bool:
    return bool(value and len(value) <= 160 and value.casefold() not in {
        "-", "na", "n/a", "null", "not available", "unknown",
    })


def parse_nse_totalmarket_rows(raw: bytes) -> dict[str, Any]:
    """Return per-row verified evidence, not a fabricated sector taxonomy."""
    if not 10_000 <= len(raw) <= 1_250_000 or b"\x00" in raw:
        raise AlphaContractError("P033 unexpected original NSE CSV source bytes")
    try:
        txt = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(txt, newline=""))
        if reader.fieldnames is None:
            raise AlphaContractError("P033 official CSV header absent")
        header = {h.strip(): h for h in reader.fieldnames if h}
        if not set(REQUIRED_FIELDS).issubset(header):
            raise AlphaContractError("P033 required NSE original CSV fields absent")
        raw_rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise AlphaContractError("P033 original CSV cannot be parsed") from exc
    if not MIN_TOTAL_SOURCE_ROWS <= len(raw_rows) <= MAX_TOTAL_SOURCE_ROWS:
        raise AlphaContractError("P033 original index constituent count outside 650-800")

    found: dict[str, list[tuple[int, dict[str, str]]]] = {}
    rejected: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows, start=2):
        if None in row:
            rejected.append({"row": index, "reason": "EXTRA_UNNAMED_CSV_FIELD"})
            continue
        symbol = (row.get(header["Symbol"]) or "").strip()
        isin = (row.get(header["ISIN Code"]) or "").strip()
        series = (row.get(header["Series"]) or "").strip()
        industry = " ".join((row.get(header["Industry"]) or "").split())
        reason = None
        if not SYMBOL.fullmatch(symbol):
            reason = "INVALID_SYMBOL"
        elif not ISIN.fullmatch(isin):
            reason = "INVALID_ISIN"
        elif series != "EQ":
            reason = "NON_EQ_SERIES"
        elif not _nonempty_industry(industry):
            reason = "INVALID_INDUSTRY"
        if reason is not None:
            rejected.append({
                "row": index,
                "reason": reason,
                "symbol_if_sane": symbol if SYMBOL.fullmatch(symbol) else None,
            })
            continue
        found.setdefault(symbol, []).append((index, {
            "symbol": symbol,
            "isin": isin,
            "industry": industry,
            "series": "EQ",
        }))
    # A second malformed row with the same symbol still makes the entire
    # symbol ambiguous. Never accept a clean-looking EQ row by ignoring its
    # conflicting source sibling.
    all_symbols = Counter(
        (row.get(header["Symbol"]) or "").strip()
        for row in raw_rows if None not in row
    )
    verified = {}
    for symbol, rows in found.items():
        if len(rows) != 1 or all_symbols[symbol] != 1:
            for row_number, _ in rows:
                rejected.append({
                    "row": row_number,
                    "reason": "DUPLICATE_EQ_SYMBOL_AMBIGUOUS",
                    "symbol_if_sane": symbol,
                })
        else:
            verified[symbol] = rows[0][1]
    rejected.sort(key=lambda x: (x["row"], x["reason"]))
    if (
        len(verified) < MIN_VERIFIED_SOURCE_ROWS
        or len(rejected) > MAX_INVALID_SOURCE_ROWS
    ):
        raise AlphaContractError(
            "P033 original NSE source too incomplete for safe partial admission"
        )
    return {
        "total_official_constituent_rows": len(raw_rows),
        "valid_unique_original_EQ_rows": len(verified),
        "invalid_or_ambiguous_rows": len(rejected),
        "rejected_original_row_receipts": rejected,
        "rejected_reason_counts": dict(sorted(Counter(
            x["reason"] for x in rejected
        ).items())),
        "verified": verified,
    }


def analyze(
    *,
    root: Path,
    raw: bytes,
    first_observed_at_utc: str,
) -> dict[str, Any]:
    observed = _time(first_observed_at_utc)
    parsed = parse_nse_totalmarket_rows(raw)
    frozen = frozen_members(root)
    matching = {}
    members = []
    for symbol, (isin, arm) in sorted(frozen.items()):
        original = parsed["verified"].get(symbol)
        is_match = original is not None and original["isin"] == isin
        if is_match:
            matching[arm] = matching.get(arm, 0) + 1
        members.append({
            "arm": arm,
            "symbol": symbol,
            "original_frozen_isin": isin,
            "classification": (
                "VERIFIED_SOURCE_EQ_EXACT_SYMBOL_ISIN"
                if is_match else "SOURCE_NOT_AVAILABLE_OR_IDENTITY_CONFLICT"
            ),
            "official_industry_if_verified": (
                original["industry"] if is_match else None
            ),
            "source_has_fewer_than_four_industry_levels": True,
            "first_verified_at_utc": (
                observed.isoformat() if is_match else None
            ),
            "was_proven_before_original_oct15_entry": False,
            "investment_signal": None,
        })
    summary = {
        arm: {
            "denominator": 100,
            "verified": matching.get(arm, 0),
            "missing": 100 - matching.get(arm, 0),
            "threshold_met": matching.get(arm, 0) >= MIN_NEXT_TRIAL_PER_ARM,
        }
        for arm in ARMS
    }
    total = sum(matching.values())
    eligible_source_coverage = (
        total >= MIN_NEXT_TRIAL_TOTAL
        and all(x["threshold_met"] for x in summary.values())
    )
    result = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "source_url": SOURCE,
        "source_original_sha256": hashlib.sha256(raw).hexdigest(),
        "original_byte_count": len(raw),
        "source_first_observed_at_utc": observed.isoformat(),
        "original_constituent_rows": parsed["total_official_constituent_rows"],
        "source_unique_valid_EQ_rows": parsed["valid_unique_original_EQ_rows"],
        "source_rejected_rows": parsed["invalid_or_ambiguous_rows"],
        "source_rejected_reason_counts": parsed["rejected_reason_counts"],
        "source_rejected_original_row_receipts": (
            parsed["rejected_original_row_receipts"]
        ),
        "frozen_300_exact_symbol_isin_matches": total,
        "coverage_by_arm": summary,
        "frozen_300_company_industry_rows": members,
        "one_tier_industry_source_coverage_ready": eligible_source_coverage,
        "new_independent_trial_registration_ready": False,
        "remaining_independent_causal_gates": [
            "FOUR_TIER_INDUSTRY_OR_SECTOR_CANONICAL_MAPPING",
            "ASOF_SIZE_FREE_FLOAT_SHARE_CAPITAL_EVIDENCE",
            "ASOF_BETA_RISK_ACCOUNTING_REGIME",
            "PROSPECTIVE_SOURCE_ACTIONS_ENTITLEMENTS_COST_AND_FILL_MODEL",
            "FUTURE_OUTCOME_BLIND_COHORT_AND_MODEL_REGISTRATION",
        ],
        "original_15_oct_H1_and_H5_not_reinterpreted": True,
        "partial_index_subset_not_full_indian_listings": True,
        "unverified_rows_not_assigned_a_sector": True,
        "no_future_return_labels_read": True,
        "investment_recommendations_generated": False,
        "live_capital_allowed": False,
    }
    return result


def _original_path(sha: str) -> Path:
    if len(sha) != 64 or any(x not in "0123456789abcdef" for x in sha):
        raise AlphaContractError("P033 original NSE raw path hash invalid")
    return BASE / "originals" / "sha256" / f"{sha}.csv.gz"


def archive(root: Path, *, raw: bytes, first_observed_at_utc: str) -> dict[str, Any]:
    result = analyze(root=root, raw=raw, first_observed_at_utc=first_observed_at_utc)
    raw_path = root / _original_path(result["source_original_sha256"])
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = gzip.compress(raw, mtime=0, compresslevel=9)
    if raw_path.exists() and raw_path.read_bytes() != encoded:
        raise AlphaContractError("P033 original NSE static source bytes changed under hash")
    raw_path.write_bytes(encoded)
    result["original_source_repo_path"] = str(raw_path.relative_to(root))
    result["report_sha256"] = digest(result)
    receipt = root / BASE / "receipts" / (
        result["source_first_observed_at_utc"].replace(":", "-") + ".json"
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if receipt.exists() and receipt.read_text("utf-8") != serialized:
        raise AlphaContractError("P033 original NSE receipt cannot be overwritten")
    receipt.write_text(serialized, encoding="utf-8")
    return result


def replay_all(root: Path) -> dict[str, Any]:
    status = []
    for receipt in sorted((root / BASE / "receipts").glob("*.json")):
        original = json.loads(receipt.read_text("utf-8"))
        expected_sha = original.get("report_sha256")
        unsigned = copy.deepcopy(original)
        unsigned.pop("report_sha256", None)
        if expected_sha != digest(unsigned):
            raise AlphaContractError("P033 signed industry receipt was modified")
        raw_path = root / _original_path(original["source_original_sha256"])
        if original["original_source_repo_path"] != str(
            raw_path.relative_to(root)
        ) or not raw_path.exists():
            raise AlphaContractError("P033 original NSE industry raw bytes missing")
        raw = gzip.decompress(raw_path.read_bytes())
        reproduced = analyze(
            root=root,
            raw=raw,
            first_observed_at_utc=original["source_first_observed_at_utc"],
        )
        reproduced["original_source_repo_path"] = original["original_source_repo_path"]
        reproduced["report_sha256"] = digest(reproduced)
        if original != reproduced:
            raise AlphaContractError("P033 NSE industry raw replay differs")
        status.append({
            "observed": original["source_first_observed_at_utc"],
            "sha256": original["source_original_sha256"],
            "source_valid_rows": original["source_unique_valid_EQ_rows"],
            "matched_300": original["frozen_300_exact_symbol_isin_matches"],
            "new_cohort_ready": original["new_independent_trial_registration_ready"],
        })
    return {
        "protocol": PROTOCOL,
        "source_replays_verified": len(status),
        "receipts": status,
        "new_cohort_activated": False,
        "live_capital_allowed": False,
    }
