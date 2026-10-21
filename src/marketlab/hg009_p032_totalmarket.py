"""P032: original NSE Total Market constituent CSV, partial industry provenance.

Source is a ~750-company *index subset*, not full Indian listed universe and
not a four-tier industry taxonomy. No retrospective October 15 features.
"""

from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs, verify_hg009_controls

AUDIT_ID = "HG009-P032-20261021-OFFICIAL-NIFTY-TOTAL-MARKET-INDUSTRY-v1"
SOURCE_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"
DOCUMENTATION_URL = "https://www.nseindia.com/static/products-services/indices-nifty-total-market-index"
ROOT = Path("research/hg009/p032-totalmarket")
RAW_PATH = ROOT / "originals"
RECEIPTS_PATH = ROOT / "receipts"
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
FIRST_METHOD_DATE = "2026-10-21"
MIN_ROWS = 650
MAX_ROWS = 800


def _now(value: str) -> str:
    try:
        t = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("P032 invalid observed source UTC timestamp") from exc
    if t.tzinfo is None:
        raise AlphaContractError("P032 observed source has no timezone")
    timestamp = t.astimezone(UTC)
    if timestamp.date().isoformat() < FIRST_METHOD_DATE:
        raise AlphaContractError("P032 attempt precedes registration date")
    return timestamp.isoformat()


def _frozen(root: Path) -> dict[str, dict[str, str]]:
    source, selected = load_hg009_inputs(root)
    controls = json.loads((
        root / "research/hg009/hg009-p001-matched-300-company-controls-v1.json"
    ).read_text(encoding="utf-8"))
    verify_hg009_controls(controls, source=source, selected=selected)
    groups = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    fixed: dict[str, dict[str, str]] = {}
    for arm in ARMS:
        if len(groups[arm]) != 100:
            raise AlphaContractError("P032 source arm not 100")
        for member in groups[arm]:
            symbol, isin = member["symbol"], member["isin"]
            if symbol in fixed:
                raise AlphaContractError("P032 duplicate frozen symbol")
            fixed[symbol] = {"isin": isin, "arm": arm}
    if len(fixed) != 300:
        raise AlphaContractError("P032 missing exact 300 original issuers")
    return fixed


def _read_official_csv(raw: bytes) -> dict[str, dict[str, str]]:
    if not 10000 <= len(raw) <= 1_000_000:
        raise AlphaContractError("P032 invalid original index source size")
    try:
        decoded = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded, newline=""))
        if reader.fieldnames is None:
            raise AlphaContractError("P032 original NSE CSV has no header")
        names = {column.strip(): column for column in reader.fieldnames}
        required = {"Symbol", "ISIN Code", "Industry", "Series"}
        if not required.issubset(names):
            raise AlphaContractError(
                "P032 official NSE Total Market columns absent: "
                + ",".join(sorted(required-set(names)))
            )
        companies = {}
        for row in reader:
            symbol = (row[names["Symbol"]] or "").strip()
            isin = (row[names["ISIN Code"]] or "").strip()
            series = (row[names["Series"]] or "").strip()
            industry = (row[names["Industry"]] or "").strip()
            if (
                not symbol or not isin or len(isin) != 12
                or series != "EQ"
                or not industry or len(industry) > 160
                or symbol in companies
            ):
                raise AlphaContractError("P032 original NSE index issuer/industry invalid")
            companies[symbol] = {"isin": isin, "industry": industry}
    except (UnicodeError, csv.Error, KeyError) as exc:
        raise AlphaContractError("P032 original CSV decoding/rows failed") from exc
    if not MIN_ROWS <= len(companies) <= MAX_ROWS:
        raise AlphaContractError("P032 official Total Market constituent count invalid")
    return companies


def analyze(
    *,
    root: Path,
    original_csv: bytes,
    first_retrieved_at_utc: str,
) -> dict[str, Any]:
    captured = _now(first_retrieved_at_utc)
    source = _read_official_csv(original_csv)
    frozen = _frozen(root)
    details = []
    observed = {arm: 0 for arm in ARMS}
    for symbol, identity in sorted(frozen.items()):
        source_row = source.get(symbol)
        correct = source_row is not None and source_row["isin"] == identity["isin"]
        if correct:
            observed[identity["arm"]] += 1
        details.append({
            "symbol": symbol,
            "frozen_isin": identity["isin"],
            "arm": identity["arm"],
            "source_join": (
                "EXACT_SYMBOL_ISIN_INDEX_MEMBER"
                if correct else "OUTSIDE_INDEX_OR_CHANGED_IDENTITY"
            ),
            "original_NSE_index_industry_if_exact": (
                source_row["industry"] if correct else None
            ),
            "four_tier_issuer_industry_verified": False,
            "known_before_2026_10_15_open": False,
            "investment_signal": None,
            "investment_eligibility": False,
        })
    return {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "source_url": SOURCE_URL,
        "official_index_documentation_url": DOCUMENTATION_URL,
        "first_retrieved_at_utc": captured,
        "source_sha256": hashlib.sha256(original_csv).hexdigest(),
        "source_byte_count": len(original_csv),
        "index_original_EQ_company_count": len(source),
        "frozen_300_company_count": 300,
        "exact_symbol_isin_matches": sum(observed.values()),
        "per_arm": {
            a: {"denominator": 100, "exact_matched": observed[a],
                "missing": 100-observed[a]}
            for a in ARMS
        },
        "details": details,
        "source_is_only_NIFTY_TOTAL_MARKET_750_NOT_ALL_LISTINGS": True,
        "source_industry_is_single_level_not_four_level": True,
        "source_retrieval_is_not_legacy_preentry_proof": True,
        "no_retroactive_oct15_sector_alpha": True,
        "no_2026_10_15_return_labels_read": True,
        "no_company_value_or_expected_return_computed": True,
        "new_trial_requires_independent_registration": True,
        "live_capital_allowed": False,
    }


def original_raw_name(sha: str) -> Path:
    if len(sha) != 64 or not all(c in "0123456789abcdef" for c in sha):
        raise AlphaContractError("P032 invalid original source hash")
    return RAW_PATH / f"{sha}.csv.gz"


def archive(
    *, root: Path, raw: bytes, first_retrieved_at_utc: str,
) -> dict[str, Any]:
    report = analyze(
        root=root, original_csv=raw,
        first_retrieved_at_utc=first_retrieved_at_utc,
    )
    destination = root / original_raw_name(report["source_sha256"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = gzip.compress(raw, mtime=0, compresslevel=9)
    if destination.exists() and destination.read_bytes() != encoded:
        raise AlphaContractError("P032 original source immutable collision")
    destination.write_bytes(encoded)
    report["original_raw_repo_path"] = str(original_raw_name(report["source_sha256"]))
    report["report_sha256"] = digest(report)
    receipt = root / RECEIPTS_PATH / (
        report["first_retrieved_at_utc"].replace(":", "-") + ".json"
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if receipt.exists() and receipt.read_text("utf-8") != content:
        raise AlphaContractError("P032 source receipt cannot be revised")
    receipt.write_text(content, encoding="utf-8")
    return report


def replay_all(root: Path) -> dict[str, Any]:
    reports = []
    for f in sorted((root / RECEIPTS_PATH).glob("*.json")):
        recorded = json.loads(f.read_text(encoding="utf-8"))
        unsigned = copy.deepcopy(recorded)
        sig = unsigned.pop("report_sha256", None)
        if digest(unsigned) != sig:
            raise AlphaContractError("P032 signed receipt modified")
        source_name = original_raw_name(recorded["source_sha256"])
        if recorded["original_raw_repo_path"] != str(source_name):
            raise AlphaContractError("P032 source path differs")
        target = root / source_name
        if not target.is_file():
            raise AlphaContractError("P032 original NSE bytes missing")
        try:
            raw = gzip.decompress(target.read_bytes())
        except OSError as exc:
            raise AlphaContractError("P032 original NSE CSV invalid gzip") from exc
        rebuilt = analyze(
            root=root, original_csv=raw,
            first_retrieved_at_utc=recorded["first_retrieved_at_utc"],
        )
        rebuilt["original_raw_repo_path"] = str(source_name)
        rebuilt["report_sha256"] = digest(rebuilt)
        if rebuilt != recorded:
            raise AlphaContractError("P032 issuer data not reproducible")
        reports.append({
            "sha256": rebuilt["source_sha256"],
            "retrieved": rebuilt["first_retrieved_at_utc"],
            "exact_frozen_matches": rebuilt["exact_symbol_isin_matches"],
        })
    return {
        "state": "REPLAYABLE_INDEX_INDUSTRY_OBSERVATIONS" if reports else "NO_ORIGINAL_CSV_YET",
        "original_evidence_count": len(reports),
        "source_evidence": reports,
        "new_independent_cohort_released": False,
        "live_capital_allowed": False,
    }
