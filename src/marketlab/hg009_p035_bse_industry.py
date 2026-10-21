"""HG009 P035: independent cross-exchange BSE all-equity industry feasibility.

A BSE original exchange ISIN/industry may be valid *future* company metadata,
but is NOT a historical Oct 15 NSE feature, full four-tier NSE classification,
free-float capitalisation, current diluted shares or risk-adjusted return.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_p032_totalmarket import _frozen

AUDIT_ID = "HG009-P035-20261021-BSE-FULL-EQUITY-ISIN-INDUSTRY-v1"
SOURCE_URL = (
    "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData_new/w"
    "?Group=&Scripcode=&segment=Equity&status=Active&scripName="
)
CUSTODY = Path("research/hg009/p035-bse-industry")
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
INDUSTRY_KEYS = {
    "industry", "bseindustry", "industryname", "basicindustry",
    "basicindustryname", "sectorindustry",
}
ISIN_KEYS = {"isinnumber", "isin", "isincode", "isinno", "securityisin"}
SOURCE_SYMBOL_KEYS = {"scripid", "symbol", "tradesymbol"}
MARKETCAP_KEYS = {"mktcap", "marketcap", "marketcapitalisation", "marketcapitalization"}


def _norm(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.casefold())


def _unique_column(keys: list[str], allowed: set[str]) -> str | None:
    match = [key for key in keys if _norm(key) in allowed]
    return match[0] if len(match) == 1 else None


def _when(t: str) -> str:
    try:
        dt = datetime.fromisoformat(t)
    except (TypeError, ValueError) as exc:
        raise AlphaContractError("P035 invalid BSE first-observed timestamp") from exc
    if dt.tzinfo is None:
        raise AlphaContractError("P035 BSE timestamp must include UTC offset")
    dt = dt.astimezone(UTC)
    if dt.date().isoformat() < "2026-10-21":
        raise AlphaContractError("P035 cannot predate method registration")
    return dt.isoformat()


def _parse_source(raw: bytes) -> tuple[list[dict[str, str]], list[str], str]:
    if not 100_000 <= len(raw) <= 12_000_000:
        raise AlphaContractError("P035 original BSE source size implausible")
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise AlphaContractError("P035 original response is not valid BSE JSON") from exc
    if isinstance(payload, list):
        items = payload
        root = "LIST"
    elif isinstance(payload, dict):
        choices = [
            (name, value) for name, value in payload.items()
            if isinstance(value, list) and len(value) >= 3000
        ]
        if len(choices) != 1:
            raise AlphaContractError("P035 BSE original equity collection ambiguous")
        root, items = choices[0]
    else:
        raise AlphaContractError("P035 BSE source root is not a collection")
    if not 3000 <= len(items) <= 20000:
        raise AlphaContractError("P035 BSE equity collection is not full exchange")
    if any(not isinstance(row, dict) for row in items):
        raise AlphaContractError("P035 BSE equity source contains nonrecords")
    keys = sorted({key for row in items for key in row})
    if len(keys) > 200 or not keys or any(not isinstance(x, str) for x in keys):
        raise AlphaContractError("P035 BSE field schema implausible")
    normalized = [
        {
            str(k): ("" if v is None else str(v)).strip()
            for k, v in row.items()
        }
        for row in items
    ]
    return normalized, keys, root


def analyze_bse_original(
    *,
    root: Path,
    raw: bytes,
    first_observed_at_utc: str,
) -> dict[str, Any]:
    observed = _when(first_observed_at_utc)
    rows, keys, payload_shape = _parse_source(raw)
    identities = _frozen(root)
    isin_field = _unique_column(keys, ISIN_KEYS)
    industry_field = _unique_column(keys, INDUSTRY_KEYS)
    symbol_field = _unique_column(keys, SOURCE_SYMBOL_KEYS)
    marketcap_field = _unique_column(keys, MARKETCAP_KEYS)
    status_field = _unique_column(keys, {"status", "tradingstatus"})
    segment_field = _unique_column(keys, {"segment", "marketsegment"})
    source_by_isin: dict[str, list[dict[str, str]]] = {}
    if isin_field:
        for row in rows:
            isin = row.get(isin_field, "").upper()
            if len(isin) == 12 and isin[:2] == "IN":
                source_by_isin.setdefault(isin, []).append(row)
    output_rows = []
    matched = Counter()
    industry_found = Counter()
    states = Counter()
    for symbol, member in sorted(identities.items()):
        isin = member["isin"]
        arm = member["arm"]
        candidates = source_by_isin.get(isin, [])
        admissible = [
            row for row in candidates
            if (
                status_field is None or row.get(status_field, "").lower() == "active"
            ) and (
                segment_field is None or row.get(segment_field, "").lower() == "equity"
            )
        ]
        sector = None
        if not isin_field:
            state = "BLOCKED_NO_EXACT_BSE_ISIN_FIELD"
        elif len(admissible) == 1:
            state = "BSE_ISIN_EXACT_EQUITY_SOURCE"
            matched[arm] += 1
            value = admissible[0].get(industry_field, "") if industry_field else ""
            if value and value != "-" and len(value) <= 160:
                sector = value
                industry_found[arm] += 1
        elif len(admissible) > 1:
            state = "BLOCKED_DUPLICATE_OR_AMBIGUOUS_BSE_ISIN"
        elif candidates:
            state = "BLOCKED_BSE_STATUS_OR_EQUITY_SERIES_MISMATCH"
        else:
            state = "NOT_IN_ORIGINAL_BSE_ACTIVE_EQUITY_SOURCE"
        states[state] += 1
        output_rows.append({
            "arm": arm,
            "original_nse_symbol": symbol,
            "original_nse_isin": isin,
            "source_state": state,
            "original_bse_reported_industry_if_exact": sector,
            "bse_industry_usable_as_four_tier_nse_classification": False,
            "market_cap_or_free_float_adjusted": None,
            "confirmed_before_original_oct15_entry": False,
            "current_position_or_buy_recommendation": False,
        })
    if len(output_rows) != 300:
        raise AlphaContractError("P035 lost original NSE selected/control members")
    report = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "official_source": SOURCE_URL,
        "source_first_observed_at_utc": observed,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_byte_count": len(raw),
        "original_source_row_count": len(rows),
        "actual_json_collection_key": payload_shape,
        "source_field_names": keys,
        "source_isin_field": isin_field,
        "source_industry_field": industry_field,
        "source_symbol_field": symbol_field,
        "source_market_cap_field": marketcap_field,
        "source_status_field": status_field,
        "source_segment_field": segment_field,
        "source_valid_unique_isins": len(source_by_isin),
        "exact_frozen_nse_isin_by_arm": {
            arm: {"denominator": 100, "matched": matched[arm],
                  "missing": 100-matched[arm]} for arm in ARMS
        },
        "nonempty_original_bse_industry_by_arm": {
            arm: {"denominator": 100, "source_labeled": industry_found[arm],
                  "unknown": 100-industry_found[arm]} for arm in ARMS
        },
        "source_state_counts": dict(sorted(states.items())),
        "all_300_original_nse_identities": output_rows,
        "underlying_bse_industry_equates_to_nse_four_tier": False,
        "marketcap_column_is_correct_point_in_time_free_float_cap": False,
        "source_from_oct21_is_admissible_for_oct15_preentry_model": False,
        "next_cohort_may_start_without_independent_sector_size_cost_source": False,
        "company_expected_return_calculated": False,
        "corporate_action_adjusted": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def _signed(obj: dict) -> dict:
    unsigned = copy.deepcopy(obj)
    sig = unsigned.pop("report_sha256", None)
    if sig != digest(unsigned):
        raise AlphaContractError("P035 signed BSE original receipt altered")
    return obj


def archive(
    *,
    root: Path, raw: bytes, first_observed_at_utc: str,
) -> dict[str, Any]:
    result = analyze_bse_original(
        root=root, raw=raw, first_observed_at_utc=first_observed_at_utc
    )
    loc = CUSTODY / "originals" / f"{result['source_sha256']}.json.gz"
    destination = root / loc
    destination.parent.mkdir(parents=True, exist_ok=True)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if destination.exists() and destination.read_bytes() != compressed:
        raise AlphaContractError("P035 BSE original raw custody collision")
    destination.write_bytes(compressed)
    result.pop("report_sha256")
    result["original_bse_raw_repo_path"] = str(loc)
    result["report_sha256"] = digest(result)
    stamp = result["source_first_observed_at_utc"].replace(":", "-")
    receipt = root / CUSTODY / "receipts" / f"{stamp}.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if receipt.exists() and receipt.read_text("utf-8") != encoded:
        raise AlphaContractError("P035 cannot rewrite first original BSE receipt")
    receipt.write_text(encoded, encoding="utf-8")
    return result


def replay_originals(root: Path) -> dict[str, Any]:
    receipts = []
    for file in sorted((root / CUSTODY / "receipts").glob("*.json")):
        recorded = _signed(json.loads(file.read_text("utf-8")))
        loc = CUSTODY / "originals" / f"{recorded['source_sha256']}.json.gz"
        if recorded.get("original_bse_raw_repo_path") != str(loc):
            raise AlphaContractError("P035 source path provenance drift")
        try:
            raw = gzip.decompress((root / loc).read_bytes())
        except OSError as exc:
            raise AlphaContractError("P035 original BSE custody corrupted") from exc
        replica = analyze_bse_original(
            root=root, raw=raw,
            first_observed_at_utc=recorded["source_first_observed_at_utc"],
        )
        replica.pop("report_sha256")
        replica["original_bse_raw_repo_path"] = str(loc)
        replica["report_sha256"] = digest(replica)
        if replica != recorded:
            raise AlphaContractError("P035 independently reconstructed BSE source differs")
        receipts.append({
            "sha256": replica["source_sha256"],
            "count": replica["original_source_row_count"],
            "exact_matched": sum(
                x["matched"] for x in replica["exact_frozen_nse_isin_by_arm"].values()
            ),
            "industry_labeled": sum(
                x["source_labeled"]
                for x in replica["nonempty_original_bse_industry_by_arm"].values()
            ),
        })
    return {
        "state": "ORIGINAL_BSE_ISIN_INDUSTRY_REPLAYED" if receipts else "NO_BSE_SOURCE",
        "count": len(receipts),
        "receipts": receipts,
        "retroactive_oct15_alpha": False,
        "live_capital_allowed": False,
    }
