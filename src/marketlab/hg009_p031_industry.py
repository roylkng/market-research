"""P031: official NSE issuer sector-source evidence for a NEXT cohort.

The 2026-10-15 HG009 trial is already in the past. These retrieval receipts
MUST NOT become features in that original pre-entry prediction or a posthoc
sector-neutral return test. They may qualify as inputs for a distinct *future*
cohort only after source custody, industry, size/beta and model freeze gates.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.hg009_controls import load_hg009_inputs, verify_hg009_controls

P031_ID = "HG009-P031-NEXT-COHORT-OFFICIAL-NSE-INDUSTRY-v1"
ORIGINAL_ENTRY_DATE = "2026-10-15"
METHOD_DATE = "2026-10-21"
ORIGINAL_SOURCE = "https://www.nseindia.com/api/quote-equity"
ARMS = ("SELECTED", "ONE_LANE", "ZERO_LANE")
MIN_PER_ARM = 90
MIN_TOTAL = 285
BASE = Path("research/hg009/p031-industry")
RECEIPTS = BASE / "receipts"
RAW = BASE / "originals"

_SANE_SYMBOL = re.compile(r"^[A-Z0-9&_.-]{1,35}$")


def _aware_timestamp(timestamp: str) -> datetime:
    try:
        value = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError("P031 invalid source observation timestamp") from exc
    if value.tzinfo is None:
        raise AlphaContractError("P031 source observation time lacks offset")
    return value.astimezone(UTC)


def frozen_members(root: Path) -> dict[str, tuple[str, str]]:
    original, selected = load_hg009_inputs(root)
    controls = json.loads(
        (root / "research/hg009/hg009-p001-matched-300-company-controls-v1.json")
        .read_text(encoding="utf-8")
    )
    verify_hg009_controls(controls, source=original, selected=selected)
    arms = {
        "SELECTED": selected["selected"],
        "ONE_LANE": controls["controls"]["ONE_LANE"],
        "ZERO_LANE": controls["controls"]["ZERO_LANE"],
    }
    members: dict[str, tuple[str, str]] = {}
    for arm in ARMS:
        rows = arms[arm]
        if len(rows) != 100:
            raise AlphaContractError("P031 frozen arm size differs from 100")
        for row in rows:
            symbol, isin = row["symbol"], row["isin"]
            if (
                not isinstance(symbol, str)
                or not _SANE_SYMBOL.fullmatch(symbol)
                or not isinstance(isin, str)
                or len(isin) != 12
                or symbol in members
            ):
                raise AlphaContractError("P031 frozen source symbol/ISIN invalid")
            members[symbol] = (isin, arm)
    if len(members) != 300:
        raise AlphaContractError("P031 must retain 300 exact original identities")
    return members


def classify_raw_quote(
    raw: bytes,
    *,
    symbol: str,
    isin: str,
    captured_at_utc: str,
) -> dict[str, Any]:
    """Parse both NSE quote-equity JSON shapes, never substitute a guessed ISIN."""
    if not raw or len(raw) > 500_000:
        raise AlphaContractError("P031 NSE issuer quote raw bytes absent or oversized")
    observed = _aware_timestamp(captured_at_utc)
    if observed.date() < date.fromisoformat(METHOD_DATE):
        raise AlphaContractError("P031 classification captured before method date")
    try:
        obj = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as exc:
        raise AlphaContractError("P031 original NSE response not valid JSON") from exc
    if not isinstance(obj, dict):
        raise AlphaContractError("P031 NSE quote source is not a JSON object")
    if "equityResponse" in obj:
        response = obj["equityResponse"]
        if not isinstance(response, list) or len(response) != 1:
            raise AlphaContractError("P031 modern quote missing unique equity record")
        item = response[0]
        if not isinstance(item, dict):
            raise AlphaContractError("P031 modern quote equity details invalid")
        info, classification = item.get("metaData"), item.get("secInfo")
        if not isinstance(info, dict) or not isinstance(classification, dict):
            raise AlphaContractError("P031 modern NSE issuer source metadata absent")
        sourced_symbol = info.get("symbol")
        sourced_isin = info.get("isinCode")
        series = info.get("series")
        levels = (
            classification.get("macro"),
            classification.get("sector"),
            classification.get("industryInfo"),
            classification.get("basicIndustry"),
        )
        schema = "EQUITY_RESPONSE_SECINFO_V1"
    else:
        info = obj.get("info")
        metadata = obj.get("metadata")
        classification = obj.get("industryInfo")
        if not all(isinstance(x, dict) for x in (info, metadata, classification)):
            raise AlphaContractError("P031 legacy NSE issuer metadata or industry absent")
        sourced_symbol = info.get("symbol")
        sourced_isin = info.get("isin")
        series = metadata.get("series")
        if metadata.get("symbol") not in (None, symbol):
            raise AlphaContractError("P031 NSE metadata symbol conflicts with issuer")
        if metadata.get("isin") not in (None, isin):
            raise AlphaContractError("P031 NSE metadata ISIN conflicts with issuer")
        levels = tuple(
            classification.get(name)
            for name in ("macro", "sector", "industry", "basicIndustry")
        )
        schema = "LEGACY_INDUSTRYINFO_V1"
    if sourced_symbol != symbol or sourced_isin != isin:
        raise AlphaContractError("P031 original NSE quote symbol/ISIN mismatch")
    if series != "EQ":
        raise AlphaContractError("P031 quote is not original NSE EQ security")
    if any(
        not isinstance(label, str)
        or not label.strip()
        or len(label) > 150
        for label in levels
    ):
        raise AlphaContractError("P031 NSE four-tier industry evidence incomplete")
    return {
        "symbol": symbol,
        "isin": isin,
        "original_url": f"{ORIGINAL_SOURCE}?symbol={symbol}",
        "source_schema": schema,
        "captured_at_utc": observed.isoformat(),
        "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
        "source_raw_length": len(raw),
        "original_NSE_four_tier_industry": {
            key: label.strip()
            for key, label in zip(
                ("macro", "sector", "industry", "basicIndustry"), levels,
                strict=True,
            )
        },
        "original_oct15_sector_feature_repaired": False,
        "current_price_or_current_equity_value_used": False,
        "later_industry_membership_is_not_proof_of_earlier_state": True,
        "new_cohort_eligible_only_after_independent_freeze": True,
        "live_capital_allowed": False,
    }


def original_path(*, symbol: str, sha: str) -> Path:
    if not _SANE_SYMBOL.fullmatch(symbol):
        raise AlphaContractError("P031 unsafe original NSE symbol")
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise AlphaContractError("P031 invalid original quote SHA")
    return RAW / symbol / f"{sha}.json.gz"


def record_receipt(root: Path, receipt: dict[str, Any], *, raw: bytes | None) -> Path:
    symbol = receipt["symbol"]
    if not isinstance(symbol, str) or not _SANE_SYMBOL.fullmatch(symbol):
        raise AlphaContractError("P031 unknown or unsafe issuer symbol")
    day = _aware_timestamp(receipt["captured_at_utc"]).date().isoformat()
    attempts = root / RECEIPTS / day
    attempts.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(
        json.dumps(receipt, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    path = attempts / f"{symbol}-{name}.json"
    record = copy.deepcopy(receipt)
    if record.get("state") == "VERIFIED_FOUR_TIER_NSE_EQ":
        if raw is None or hashlib.sha256(raw).hexdigest() != record["source_raw_sha256"]:
            raise AlphaContractError("P031 original source record missing corresponding bytes")
        raw_path = original_path(symbol=symbol, sha=record["source_raw_sha256"])
        target = root / raw_path
        target.parent.mkdir(parents=True, exist_ok=True)
        compressed = gzip.compress(raw, compresslevel=9, mtime=0)
        if target.exists() and target.read_bytes() != compressed:
            raise AlphaContractError("P031 content addressed original file collision")
        target.write_bytes(compressed)
        record["original_raw_repo_path"] = str(raw_path)
    else:
        if raw is not None:
            raise AlphaContractError("P031 unverified original cannot be archived as confirmed")
        record["original_raw_repo_path"] = None
    record["receipt_sha256"] = digest(record)
    content = json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise AlphaContractError("P031 cannot rewrite a previous source receipt")
    path.write_text(content, encoding="utf-8")
    return path


def load_verified_receipts(
    root: Path,
    members: dict[str, tuple[str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, int]]]:
    verified: dict[str, dict[str, Any]] = {}
    failures: dict[str, dict[str, int]] = {}
    for path in sorted((root / RECEIPTS).glob("*/*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        signature = rec.get("receipt_sha256")
        unsigned = dict(rec)
        unsigned.pop("receipt_sha256", None)
        if signature != digest(unsigned):
            raise AlphaContractError(f"P031 recorded receipt was modified: {path}")
        symbol = rec.get("symbol")
        if symbol not in members or rec.get("isin") != members[symbol][0]:
            raise AlphaContractError("P031 recorded identity differs from frozen cohort")
        if rec.get("state") == "VERIFIED_FOUR_TIER_NSE_EQ":
            relative = rec.get("original_raw_repo_path")
            if relative != str(original_path(
                symbol=symbol, sha=rec["source_raw_sha256"]
            )):
                raise AlphaContractError("P031 original NSE source storage path drift")
            target = root / relative
            if not target.is_file():
                raise AlphaContractError("P031 original verified NSE bytes not retained")
            try:
                original = gzip.decompress(target.read_bytes())
            except OSError as exc:
                raise AlphaContractError("P031 NSE original source gzip invalid") from exc
            replay = classify_raw_quote(
                original,
                symbol=symbol,
                isin=rec["isin"],
                captured_at_utc=rec["captured_at_utc"],
            )
            for key, value in replay.items():
                if key not in rec or rec[key] != value:
                    raise AlphaContractError("P031 original NSE bytes do not replay receipt")
            prior = verified.get(symbol)
            if prior is None or rec["captured_at_utc"] < prior["captured_at_utc"]:
                verified[symbol] = rec
        else:
            failures.setdefault(symbol, {})[rec["state"]] = (
                failures.setdefault(symbol, {}).get(rec["state"], 0) + 1
            )
    return verified, failures


def build_coverage_status(root: Path) -> dict[str, Any]:
    members = frozen_members(root)
    verified, failures = load_verified_receipts(root, members)
    per_arm = {
        name: {"denominator": 100, "verified": 0, "missing": 100}
        for name in ARMS
    }
    for symbol in verified:
        arm = members[symbol][1]
        per_arm[arm]["verified"] += 1
        per_arm[arm]["missing"] -= 1
    count = len(verified)
    success_gate = (
        count >= MIN_TOTAL
        and all(per_arm[arm]["verified"] >= MIN_PER_ARM for arm in ARMS)
    )
    result = {
        "schema_version": 1,
        "audit_id": P031_ID,
        "method_registered_date": METHOD_DATE,
        "legacy_HG009_entry_session": ORIGINAL_ENTRY_DATE,
        "all_300_original_identities_preserved": True,
        "source_type": "NSE_ORIGINAL_QUOTE_EQUITY_INDUSTRYINFO_OR_SECINFO",
        "full_market_company_count": 300,
        "verified_original_NSE_issuer_four_tier_count": count,
        "frozen_100_company_arm_coverage": per_arm,
        "unverified_original_issuer_count": 300 - count,
        "blocked_attempt_symbol_count": len(failures),
        "source_first_retrieval_per_symbol": [
            {
                "symbol": symbol,
                "isin": members[symbol][0],
                "arm": members[symbol][1],
                "captured_at_utc": rec["captured_at_utc"],
                "source_sha256": rec["source_raw_sha256"],
                "industry": rec["original_NSE_four_tier_industry"],
                "original_path": rec["original_raw_repo_path"],
            }
            for symbol, rec in sorted(verified.items())
        ],
        "observed_source_coverage_threshold_met": success_gate,
        "historical_Oct15_sector_regression_eligible": False,
        "sector_and_size_beta_cashflow_causal_alpha_ready": False,
        "another_independent_new_cohort_registered": False,
        "no_company_future_return_predictions_calculated": True,
        "no_original_Oct15_H1_alpha_ranking_rewritten": True,
        "live_capital_allowed": False,
    }
    result["report_sha256"] = digest(result)
    return result
