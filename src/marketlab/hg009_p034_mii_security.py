"""HG009 P034: source-feasibility of the official all-listed NSE CM security master.

MII securities file is NOT assumed to include industry, public float, current
diluted shares, bid-ask order depth or a verified corporate-action adjustment.
This experiment only inspects actual original CSV headers and exact identities.
"""

from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import io
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs, verify_hg009_controls

PROTOCOL = "HG009-P034-20261021-NSE-CM-MII-SECURITY-MASTER-SCHEMA-v1"
PUBLICATION_DATE = "2026-10-21"
URL_BASE = "https://nsearchives.nseindia.com/content/cm/"
FILE_NAME = "NSE_CM_security_21102026.csv.gz"
SOURCE_URL = URL_BASE + FILE_NAME
ORIGINAL_DIR = Path("research/hg009/p034-mii-security/originals/sha256")
RECEIPT_DIR = Path("research/hg009/p034-mii-security/receipts")
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
COLUMN_ALIASES = {
    "symbol": {"symbol", "tckrsymb", "securitysymbol", "sctysymb"},
    "isin": {"isin", "isinno", "isincode", "sctyisin", "isinnumber"},
    "series": {"series", "sctysrs", "securityseries", "securitysrs"},
}
SECTOR_COLUMNS = {
    "industry", "basicindustry", "sector", "macroeconomicsector",
    "nseindustry", "industryname", "sectorname", "basicindustryname",
    "macrosector",
}
FLOAT_COLUMNS = {
    "freefloat", "freefloatshares", "publicfloat", "ffmc",
    "freefloatmarketcap", "floatshares", "investibleweightfactor", "iwf",
}
EXCHANGE_STATUS_COLUMNS = {
    "securitystatus", "securitystatusinnormalmkt", "tradingstatus",
    "prtdtotrad", "permittedtotrade", "ticksize", "issuedcapital",
    "securitytype", "instrumenttype",
}


def _canonical_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.strip().lower())


def _column(headers: list[str], kind: str) -> str | None:
    matches = [
        head for head in headers
        if _canonical_header(head) in COLUMN_ALIASES[kind]
    ]
    return matches[0] if len(matches) == 1 else None


def _utc(value: str) -> str:
    try:
        t = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("P034 source capture timestamp invalid") from exc
    if t.tzinfo is None:
        raise AlphaContractError("P034 source clock missing UTC offset")
    t = t.astimezone(UTC)
    if t.date().isoformat() < PUBLICATION_DATE:
        raise AlphaContractError("P034 source captured before protocol registration")
    return t.isoformat()


def _frozen(root: Path) -> dict[str, dict[str, str]]:
    router, selected = load_hg009_inputs(root)
    import json

    controls = json.loads(
        (root / "research/hg009/hg009-p001-matched-300-company-controls-v1.json")
        .read_text(encoding="utf-8")
    )
    verify_hg009_controls(controls, source=router, selected=selected)
    rows: dict[str, dict[str, str]] = {}
    groups = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    for arm in ARMS:
        for item in groups[arm]:
            sym = item["symbol"]
            if sym in rows:
                raise AlphaContractError("P034 duplicate original group symbol")
            rows[sym] = {"isin": item["isin"], "arm": arm}
    if len(rows) != 300:
        raise AlphaContractError("P034 original 300 identities changed")
    return rows


def _raw_csv(original_gzip: bytes) -> tuple[list[str], list[dict[str, str]], bytes, str]:
    if not 300_000 <= len(original_gzip) <= 5_000_000:
        raise AlphaContractError("P034 original NSE MII gzip implausible size")
    try:
        raw_csv = gzip.decompress(original_gzip)
    except (OSError, EOFError) as exc:
        raise AlphaContractError("P034 source is not valid original gzip") from exc
    if not 1_000_000 <= len(raw_csv) <= 45_000_000:
        raise AlphaContractError("P034 NSE CSV decompressed length invalid")
    try:
        text = raw_csv.decode("utf-8-sig")
    except UnicodeError as exc:
        raise AlphaContractError("P034 original NSE CSV encoding unexpected") from exc
    # Do not guess mislabeled files into issuer classifications.
    header = text.splitlines()[0] if text.splitlines() else ""
    delimiter = "|" if header.count("|") > header.count(",") else ","
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)
        headers = list(reader.fieldnames or [])
        if not headers or len(headers) < 4 or len(headers) > 250:
            raise AlphaContractError("P034 source header is not an instrument CSV")
        rows = []
        for row in reader:
            if None in row:
                raise AlphaContractError("P034 inconsistent original security CSV width")
            rows.append({
                key: (str(row.get(key) or "")).strip()
                for key in headers
            })
    except (csv.Error, UnicodeError, KeyError, ValueError) as exc:
        raise AlphaContractError("P034 original security CSV cannot be parsed") from exc
    if not 1800 <= len(rows) <= 100_000:
        raise AlphaContractError("P034 NSE instrument population count implausible")
    return headers, rows, raw_csv, delimiter


def analyze_original(
    *,
    root: Path,
    original_gzip: bytes,
    first_observed_at_utc: str,
) -> dict[str, Any]:
    observed = _utc(first_observed_at_utc)
    headers, rows, csv_bytes, delimiter = _raw_csv(original_gzip)
    names = [_canonical_header(h) for h in headers]
    columns = {kind: _column(headers, kind) for kind in COLUMN_ALIASES}
    possible_sectors = [
        h for h in headers if _canonical_header(h) in SECTOR_COLUMNS
    ]
    possible_float = [
        h for h in headers if _canonical_header(h) in FLOAT_COLUMNS
    ]
    trade_fields = [
        h for h in headers if _canonical_header(h) in EXCHANGE_STATUS_COLUMNS
    ]
    frozen = _frozen(root)
    matches: dict[str, list[tuple[str, str, str]]] = {}
    if columns["symbol"] and columns["isin"]:
        for row in rows:
            symbol = row[columns["symbol"]]
            isin = row[columns["isin"]]
            series = row.get(columns["series"], "") if columns["series"] else ""
            if symbol in frozen:
                matches.setdefault(symbol, []).append((isin, series, symbol))
    identity_rows = []
    verified_by_arm = Counter()
    for symbol, source in sorted(frozen.items()):
        candidates = matches.get(symbol, [])
        exact = [
            item for item in candidates
            if item[0] == source["isin"] and (
                columns["series"] is None or item[1] == "EQ"
            )
        ]
        if not columns["symbol"] or not columns["isin"]:
            state = "BLOCKED_MISSING_EXACT_IDENTITY_COLUMNS"
        elif len(exact) == 1:
            state = "ORIGINAL_NSE_MII_SYMBOL_ISIN_EXACT"
            verified_by_arm[source["arm"]] += 1
        elif len(exact) > 1:
            state = "BLOCKED_DUPLICATE_EXACT_INSTRUMENT"
        elif candidates:
            state = "BLOCKED_ORIGINAL_SOURCE_ISIN_OR_SERIES_DIFFER"
        else:
            state = "NOT_FOUND_IN_THIS_ORIGINAL_MASTER"
        identity_rows.append({
            "arm": source["arm"],
            "symbol": symbol,
            "frozen_isin": source["isin"],
            "state": state,
            "verified_sector": None,
            "verified_free_float_cap": None,
            "corporate_action_adjusted_return": None,
            "tradable_price_or_order_depth": None,
            "expected_alpha": None,
        })
    result = {
        "schema_version": 1,
        "protocol": PROTOCOL,
        "official_source_url": SOURCE_URL,
        "official_report_session": PUBLICATION_DATE,
        "actual_first_retrieved_at_utc": observed,
        "original_gzip_sha256": hashlib.sha256(original_gzip).hexdigest(),
        "decompressed_original_csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "original_compressed_byte_count": len(original_gzip),
        "original_decompressed_byte_count": len(csv_bytes),
        "original_instrument_row_count": len(rows),
        "original_column_names_in_order": headers,
        "original_csv_delimiter": delimiter,
        "strict_recognized_identity_columns": columns,
        "published_column_names_that_look_like_sector": possible_sectors,
        "published_column_names_that_look_like_float": possible_float,
        "published_column_names_that_look_like_trading_status": trade_fields,
        "original_source_company_states": identity_rows,
        "exact_symbol_isin_count": sum(verified_by_arm.values()),
        "exact_identity_coverage_by_arm": {
            arm: {
                "denominator": 100,
                "exact_source_matches": verified_by_arm[arm],
                "missing_or_ambiguous": 100 - verified_by_arm[arm],
            }
            for arm in ARMS
        },
        "legacy_Oct15_industry_features_admitted_from_Oct21_source": False,
        "NSE_master_sector_header_is_full_four_tier_industry_proof": False,
        "NSE_master_issued_capital_is_current_fully_diluted_float": False,
        "NSE_master_status_is_order_book_depth_or_executable_ticket": False,
        "new_prospective_industry_model_authorized": False,
        "original_future_price_labels_opened": False,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result


def archive(
    *,
    root: Path,
    original_gzip: bytes,
    first_observed_at_utc: str,
) -> dict[str, Any]:
    result = analyze_original(
        root=root,
        original_gzip=original_gzip,
        first_observed_at_utc=first_observed_at_utc,
    )
    source_path = ORIGINAL_DIR / f"{result['original_gzip_sha256']}.csv.gz"
    dest = root / source_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_bytes() != original_gzip:
        raise AlphaContractError("P034 original source path collision")
    dest.write_bytes(original_gzip)
    result["original_repo_path"] = str(source_path)
    result["report_sha256"] = digest({
        k: v for k, v in result.items() if k != "report_sha256"
    })
    p = root / RECEIPT_DIR / (
        result["actual_first_retrieved_at_utc"].replace(":", "-") + ".json"
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    import json

    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if p.exists() and p.read_text("utf-8") != encoded:
        raise AlphaContractError("P034 existing original receipt rewritten")
    p.write_text(encoded, encoding="utf-8")
    return result


def replay_originals(root: Path) -> dict[str, Any]:
    import json

    verified = []
    for file in sorted((root / RECEIPT_DIR).glob("*.json")):
        saved = json.loads(file.read_text(encoding="utf-8"))
        unsigned = copy.deepcopy(saved)
        sig = unsigned.pop("report_sha256", None)
        if sig != digest(unsigned):
            raise AlphaContractError("P034 signed receipt tampered")
        expected_path = ORIGINAL_DIR / f"{saved['original_gzip_sha256']}.csv.gz"
        if saved.get("original_repo_path") != str(expected_path):
            raise AlphaContractError("P034 original receipt path differs")
        raw = (root / expected_path).read_bytes()
        rebuilt = analyze_original(
            root=root,
            original_gzip=raw,
            first_observed_at_utc=saved["actual_first_retrieved_at_utc"],
        )
        rebuilt["original_repo_path"] = str(expected_path)
        rebuilt["report_sha256"] = digest({
            k: v for k, v in rebuilt.items() if k != "report_sha256"
        })
        if rebuilt != saved:
            raise AlphaContractError("P034 source replay changed issuer identity")
        verified.append({
            "sha256": rebuilt["original_gzip_sha256"],
            "exact_300_identity_matches": rebuilt["exact_symbol_isin_count"],
        })
    return {
        "state": "VERIFIED_MII_ORIGINAL_REPLAY" if verified else "NO_MII_SOURCE_YET",
        "original_source_count": len(verified),
        "original_sources": verified,
        "sector_coverage_eligible_for_next_cohort": False,
        "live_capital_allowed": False,
    }
