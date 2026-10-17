"""L001 P004: verify the selected 100 against original full-market archives.

Source complete means *four XBRL accounting cells per issuer*, not investor
owner cash, current fully diluted shares, audited intrinsic value or alpha.
All source snapshots predate the October 15 cutoff. Preserve their exact hashes.
"""

from __future__ import annotations

import hashlib
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

from marketlab.alpha import AlphaContractError, digest

PINNED = {
    "cohort": "e904e5d69dc7a6c2a45ea3cf34933544bc2634f80e3666125185d475372864d5",
    "census": "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7",
    "fa001": "cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124",
    "ss001": "ab782411fef19afd80cdde3da1cba402eff70778ce0aaa0bd3e3afd571ee7428",
    "gf001": "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7",
}
ARTIFACT_IDS = {
    "census": 11301695772,
    "fa001": 11306919543,
    "ss001": 11525307261,
    "gf001": 11303742567,
    "fa001_shard_raw": (
        11307293225, 11307437621, 11307367737,
        11306939618, 11306939594, 11307478103,
    ),
}
DECISION_CUTOFF = "2026-10-15T13:00:00Z"


def original_utc(value: object) -> datetime:
    try:
        observed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        observed = None
    if observed is None or observed.utcoffset() != timedelta(0):
        raise AlphaContractError("valid original UTC timestamp required")
    return observed


def check_hash(document: dict, field: str, pin: str) -> None:
    unsigned = {k: v for k, v in document.items() if k != field}
    if document.get(field) != pin or digest(unsigned) != pin:
        raise AlphaContractError("pinned source panel signature mismatch")


def indexed(rows: object, label: str) -> dict[str, dict]:
    if not isinstance(rows, list) or len(rows) != 2319:
        raise AlphaContractError(f"{label}: source census incomplete")
    result: dict[str, dict] = {}
    for row in rows:
        symbol = row.get("symbol") if isinstance(row, dict) else None
        if not isinstance(symbol, str) or not symbol or symbol in result:
            raise AlphaContractError(f"{label}: missing or duplicate issuer")
        result[symbol] = row
    return result


def replay_xbrl_fact(original: ET.Element, parsed: dict, name: str) -> float:
    """Exact concept/context/unit numerical agreement, not independent semantics."""
    item = parsed.get("facts", {}).get(name)
    if not isinstance(item, dict) or item.get("status") != "READY":
        raise AlphaContractError(f"{name}: source fact not ready")
    value = item.get("value")
    if (
        not isinstance(value, (float, int))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or item.get("unit_ref") != "INR"
        or not item.get("selected_concept")
        or not item.get("context_refs")
    ):
        raise AlphaContractError(f"{name}: invalid XBRL quantity")
    matches: list[float] = []
    for element in original.iter():
        if (
            element.tag.rsplit("}", 1)[-1] == item["selected_concept"]
            and element.attrib.get("contextRef") in item["context_refs"]
            and element.attrib.get("unitRef") == "INR"
        ):
            try:
                matches.append(float(element.text))
            except (TypeError, ValueError) as exc:
                raise AlphaContractError(f"{name}: source quantity nonnumeric") from exc
    if not matches or any(found != float(value) for found in matches):
        raise AlphaContractError(f"{name}: original number does not replay")
    return round(float(value) / 10000000, 6)


def replay_frozen_100(
    cohort: dict,
    census: dict,
    financial: dict,
    shares: dict,
    governance: dict,
    original_xml_by_sha: dict[str, bytes],
    *,
    decision_cutoff_utc: str = DECISION_CUTOFF,
) -> dict:
    """Verify all selected exact identities and 300 original issuer files."""
    cutoff = original_utc(decision_cutoff_utc)
    for source, field, pin in (
        (cohort, "cohort_sha256", PINNED["cohort"]),
        (census, "census_sha256", PINNED["census"]),
        (financial, "panel_sha256", PINNED["fa001"]),
        (shares, "panel_sha256", PINNED["ss001"]),
        (governance, "panel_sha256", PINNED["gf001"]),
    ):
        check_hash(source, field, pin)
    if census.get("as_of_completed_session") != "2026-10-01":
        raise AlphaContractError("census observation time changed")
    for panel in (financial, shares, governance):
        if original_utc(panel.get("captured_at_utc")) > cutoff:
            raise AlphaContractError("panel capture not known by decision cutoff")
    members = cohort.get("selected")
    if not isinstance(members, list) or len(members) != 100:
        raise AlphaContractError("100-member cohort incomplete")
    if sorted(m["symbol"] for m in members) != cohort.get("selected_symbols_sorted"):
        raise AlphaContractError("frozen HG009 symbols do not match")
    c = indexed(census.get("rows"), "census")
    f = indexed(financial.get("rows"), "FA001")
    s = indexed(shares.get("rows"), "SS001")
    g = indexed(governance.get("rows"), "GF001")
    results: list[dict[str, Any]] = []
    audited_documents = 0
    audited_values = 0
    for member in members:
        symbol, isin = member["symbol"], member["isin"]
        if any(symbol not in x for x in (c, f, s, g)):
            raise AlphaContractError("missing selected company in source panel")
        if c[symbol].get("isin") != isin or f[symbol].get("isin") != isin:
            raise AlphaContractError("ISIN identity mismatch")
        if c[symbol].get("series") != "EQ":
            raise AlphaContractError("selected company no longer exact EQ identity")
        share, gov = s[symbol], g[symbol]["latest"]
        if (
            share.get("raw_sha256") != gov.get("raw_sha256")
            or share.get("source_url") != gov.get("source_url")
            or share.get("report_date") != gov.get("report_date")
        ):
            raise AlphaContractError("share and governance original source misaligned")
        share_sha = share.get("raw_sha256")
        share_raw = original_xml_by_sha.get(share_sha)
        if (
            not isinstance(share_raw, bytes)
            or hashlib.sha256(share_raw).hexdigest() != share_sha
        ):
            raise AlphaContractError("original issuer shareholding XBRL missing or changed")
        audited_documents += 1

        facts: dict[str, float] = {}
        sources: dict[str, dict[str, str]] = {}
        for period, names in (
            ("annual", ("operating_cash_flow", "purchase_ppe")),
            ("quarter", ("revenue", "pat")),
        ):
            record = f[symbol][period]
            if record.get("status") != "READY" or not isinstance(record.get("parsed"), dict):
                raise AlphaContractError("original financial filing not ready")
            parsed, meta = record["parsed"], record["candidate"]
            expected_period = "2026-03-31" if period == "annual" else "2026-06-30"
            if (
                meta.get("symbol") != symbol
                or parsed.get("symbol") != symbol
                or meta.get("period_end") != expected_period
                or meta.get("accounting_basis") != parsed.get("accounting_basis")
                or meta.get("source_url") != parsed.get("source_url")
                or meta.get("exchange_published_at_utc") != parsed.get("exchange_published_at_utc")
                or original_utc(meta.get("exchange_published_at_utc")) > cutoff
            ):
                raise AlphaContractError("original filing identity or publication drift")
            sha = parsed.get("raw_sha256")
            raw = original_xml_by_sha.get(sha)
            if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != sha:
                raise AlphaContractError("original financial XBRL hash or bytes missing")
            try:
                root = ET.fromstring(raw)
            except ET.ParseError as exc:
                raise AlphaContractError("original XBRL XML invalid") from exc
            audited_documents += 1
            for name in names:
                facts[f"{period}_{name}_cr"] = replay_xbrl_fact(root, parsed, name)
                audited_values += 1
            sources[period] = {
                "raw_sha256": sha,
                "original_url": meta["source_url"],
                "accounting_basis": meta["accounting_basis"],
                "period_end": meta["period_end"],
                "exchange_published_at_utc": meta["exchange_published_at_utc"],
            }
        basic = share.get("reported_share_count")
        basic_ready = share.get("status") == "SHARE_COUNT_READY" and (
            type(basic) is int and basic > 0
        )
        if not basic_ready:
            raise AlphaContractError("selected original issued share count not ready")
        cfo, ppe = facts["annual_operating_cash_flow_cr"], facts["annual_purchase_ppe_cr"]
        results.append({
            "symbol": symbol,
            "isin": isin,
            "financial_sources": sources,
            "share_source_raw_sha256": share_sha,
            "share_report_date": share.get("report_date"),
            "reported_issued_shares_not_fully_diluted": basic,
            "capitalization_source_eligible": share.get("capitalization_source_eligible") is True,
            "q1fy27_revenue_cr": facts["quarter_revenue_cr"],
            "q1fy27_pat_cr": facts["quarter_pat_cr"],
            "fy26_operating_cfo_cr": cfo,
            "fy26_ppe_purchase_cr": ppe,
            "fy26_cfo_less_ppe_cr_not_owner_cash": round(cfo - abs(ppe), 6),
            "classification_source_pending": True,
            "fully_diluted_share_count_ready": False,
            "economic_owner_cash_reconciled": False,
            "valuation_ready": False,
            "expected_return": None,
            "capital_authorized": False,
        })
    results.sort(key=lambda x: (x["symbol"], x["isin"]))
    report = {
        "schema_version": 1,
        "report_id": "L001-P004-FROZEN-HG009-ALL100-ORIGINAL-REPLAY-v1",
        "decision_cutoff_utc": decision_cutoff_utc,
        "original_panel_hashes": PINNED,
        "pinned_workflow_artifact_ids": ARTIFACT_IDS,
        "company_count": len(results),
        "original_xml_sha256_checked": audited_documents,
        "original_numeric_xbrl_values_replayed": audited_values,
        "issued_share_count_ready": len(results),
        "share_count_cap_source_eligible": sum(r["capitalization_source_eligible"] for r in results),
        "cfo_ppe_source_ready_count": len(results),
        "quarter_revenue_pat_source_ready_count": len(results),
        "sector_specific_valuation_ready_count": 0,
        "prospective_252_504_756_sessions_mature": False,
        "shareholding_numerical_count_formula_independently_replayed": False,
        "accounting_numeric_replay_is_not_owner_cash": True,
        "original_selection_preserved": True,
        "source_results": results,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report
