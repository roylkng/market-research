"""Outcome-blind H019 numeric extraction audit v3.

v3 preserves the frozen v2 corpus and gates while correcting only preregistered
accounting-source mechanics. It deliberately imports the immutable v2 engine and
patches the four versioned mechanics rather than rewriting v2 evidence code.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from scripts import h019_numeric_extraction_audit as v2
except ModuleNotFoundError:  # direct execution: python scripts/<file>.py
    import h019_numeric_extraction_audit as v2


V3_STATUS = "H019_NUMERIC_EXTRACTION_AUDIT_V3_ONLY"
_CURRENT_REPORT: tuple[str, str] | None = None
_SELECTION_LOG: dict[tuple[str, str], dict[str, object]] = {}
_STRUCTURED_DIAGNOSTICS: dict[str, dict[str, object]] = {}

_ORIGINAL_EXTRACT_LINE_FACT = v2.extract_line_fact
_ORIGINAL_EXTRACT_REPORT = v2.extract_report


def compact(text: str) -> str:
    """Normalize PDF heading spacing without changing numeric content."""
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def statement_evidence(text: str, kind: str, page_number: int) -> tuple[int, dict[str, object]]:
    normalized = v2.collapse(text)
    head = normalized[:1800]
    compact_head = compact(text[:5000])
    score = 0
    evidence: dict[str, object] = {
        "page_number": page_number + 1,
        "kind": kind,
        "compact_heading_match": False,
        "notes_penalty": False,
        "consolidated_penalty": False,
        "auditor_penalty": False,
    }

    if kind == "balance":
        heading = "balancesheet" in compact_head or "statementoffinancialposition" in compact_head
        evidence["compact_heading_match"] = heading
        score += 3 * int(heading)
        score += 2 * int("total assets" in normalized)
        score += 2 * int("equity" in normalized and "liabilit" in normalized)
    elif kind == "profit_loss":
        heading = (
            "statementofprofitandloss" in compact_head
            or "profitandlossaccount" in compact_head
        )
        evidence["compact_heading_match"] = heading
        score += 3 * int(heading)
        score += 2 * int("revenue" in normalized)
        score += 2 * int("profit" in normalized)
    elif kind == "cash_flow":
        heading = "cashflowstatement" in compact_head or "statementofcashflows" in compact_head
        evidence["compact_heading_match"] = heading
        score += 3 * int(heading or "cash flow" in normalized)
        score += 3 * int("operating activities" in normalized)
    else:
        raise ValueError(f"unknown statement kind: {kind}")

    if "consolidated" in head:
        score -= 4
        evidence["consolidated_penalty"] = True
    if "independent auditor" in normalized[:900]:
        score -= 4
        evidence["auditor_penalty"] = True
    if (
        "notestofinancialstatements" in compact_head[:2200]
        or "notestoindasfinancialstatements" in compact_head[:2200]
        or "notesaccompanyingthefinancialstatements" in compact_head[:2200]
        or "significantaccountingpoliciesandnotestofinancialstatements" in compact_head[:2200]
    ):
        score -= 5
        evidence["notes_penalty"] = True

    evidence["score"] = score
    return score, evidence


def statement_score(text: str, kind: str, page_number: int) -> tuple[int, int]:
    score, _ = statement_evidence(text, kind, page_number)
    return score, -page_number


def choose_statement_page(pages: list[str], kind: str) -> tuple[int, str] | None:
    candidates: list[tuple[int, int, int, str, dict[str, object]]] = []
    threshold = 5 if kind != "cash_flow" else 6
    for index, text in enumerate(pages):
        score, evidence = statement_evidence(text, kind, index)
        if score >= threshold:
            candidates.append((score, -index, index, text, evidence))

    key = _CURRENT_REPORT
    if not candidates:
        if key is not None:
            _SELECTION_LOG.setdefault(key, {})[kind] = {
                "status": "NO_STATEMENT_PAGE",
                "threshold": threshold,
                "candidate_count": 0,
            }
        return None

    score, _, index, text, evidence = max(candidates)
    if key is not None:
        _SELECTION_LOG.setdefault(key, {})[kind] = {
            "status": "SELECTED",
            "threshold": threshold,
            "candidate_count": len(candidates),
            "selected_page": index + 1,
            "selected_score": score,
            "evidence": evidence,
        }
    return index, text


def _explicit_unit_match(text: str) -> tuple[str, str] | None:
    normalized = v2.collapse(text[:8000])
    simplified = re.sub(r"[()`₹,.:;\[\]]+", " ", normalized)
    simplified = v2.collapse(simplified)

    lakh_patterns = (
        r"\b(?:all\s+)?amounts?(?:\s+are)?\s+in\s+(?:rs|inr|rupees?)?\s*(?:lakhs?|lacs?)\b",
        r"\b(?:rs|inr|rupees?)?\s*in\s+(?:lakhs?|lacs?)\b",
        r"\bin\s+(?:lakhs?|lacs?)\b",
    )
    crore_patterns = (
        r"\b(?:all\s+)?amounts?(?:\s+are)?\s+in\s+(?:rs|inr|rupees?)?\s*crores?\b",
        r"\b(?:rs|inr|rupees?)?\s*in\s+crores?\b",
        r"\bin\s+crores?\b",
    )
    for pattern in lakh_patterns:
        match = re.search(pattern, simplified)
        if match:
            return "LAKH", match.group(0)
    for pattern in crore_patterns:
        match = re.search(pattern, simplified)
        if match:
            return "CRORE", match.group(0)

    inr_match = re.search(
        r"\b(?:all\s+)?amounts?(?:\s+are)?\s+in\s+(?:rs|inr|rupees?)\b",
        simplified,
    )
    if inr_match:
        return "INR", inr_match.group(0)
    return None


def unit_scale(text: str) -> dict[str, object] | None:
    matched = _explicit_unit_match(text)
    if matched is None:
        return None
    label, evidence = matched
    scale = {"INR": 1.0, "LAKH": 100000.0, "CRORE": 10000000.0}[label]
    return {"label": label, "scale_to_inr": scale, "source_evidence": evidence}


def _line_label_without_numbers(line: str) -> str:
    without_numbers = v2.NUMBER_RE.sub(" ", line)
    without_punctuation = re.sub(r"[^A-Za-z]+", " ", without_numbers)
    return v2.collapse(without_punctuation)


def _explicit_section_total(page_text: str, *, after_assets: bool) -> dict[str, object] | None:
    lines = page_text.splitlines()
    asset_headings = [
        index
        for index, line in enumerate(lines)
        if _line_label_without_numbers(line) == "assets"
    ]
    if not asset_headings:
        return None
    assets_index = asset_headings[0]

    candidates: list[tuple[int, str, dict[str, object], dict[str, object]]] = []
    for index, line in enumerate(lines):
        if _line_label_without_numbers(line) != "total":
            continue
        if after_assets and index <= assets_index:
            continue
        if not after_assets and index >= assets_index:
            continue
        pair = v2.numeric_pair(line)
        if pair is None:
            continue
        candidates.append((index, line.rstrip(), pair[0], pair[1]))
    if not candidates:
        return None

    index, line, current, prior = max(candidates, key=lambda item: item[0])
    return {
        "source_line": line,
        "current_token": current["token"],
        "prior_token": prior["token"],
        "current": float(current["value"]),
        "prior": float(prior["value"]),
        "derivation": (
            "EXPLICIT_FINAL_TOTAL_IN_ASSETS_SECTION"
            if after_assets
            else "EXPLICIT_FINAL_TOTAL_BEFORE_ASSETS_SECTION"
        ),
        "source_line_index": index,
    }


def extract_line_fact(
    page_text: str,
    patterns: tuple[str, ...],
    *,
    exclusions: tuple[str, ...] = (),
) -> dict[str, object] | None:
    direct = _ORIGINAL_EXTRACT_LINE_FACT(page_text, patterns, exclusions=exclusions)
    if direct is not None:
        return direct
    if patterns == v2.FACT_PATTERNS["assets"]:
        return _explicit_section_total(page_text, after_assets=True)
    if patterns == v2.FACT_PATTERNS["equity_and_liabilities"]:
        return _explicit_section_total(page_text, after_assets=False)
    return None


def extract_report(row: dict[str, object], corpus_root: Path) -> dict[str, object]:
    global _CURRENT_REPORT
    key = (str(row["group"]), str(row["symbol"]))
    _CURRENT_REPORT = key
    try:
        result = _ORIGINAL_EXTRACT_REPORT(row, corpus_root)
    finally:
        _CURRENT_REPORT = None
    result["statement_page_classification"] = _SELECTION_LOG.get(key, {})
    result["protocol_version"] = "v3"
    return result


def _iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def structured_facts(raw: bytes) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {name: [] for name in v2.XBRL_PATTERNS}
    digest = v2.sha256(raw)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        _STRUCTURED_DIAGNOSTICS[digest] = {"status": "XML_PARSE_FAILED"}
        return result

    meta_names = {
        "dateofstartoffinancialyear": "financial_year_start",
        "dateofendoffinancialyear": "financial_year_end",
        "dateofstartofreportingperiod": "reporting_period_start",
        "dateofendofreportingperiod": "reporting_period_end",
        "whetherresultsareauditedorunaudited": "audit_status",
        "natureofreportstandaloneconsolidated": "report_nature",
    }
    context_meta: dict[str, dict[str, str]] = {}
    fy_starts: set[str] = set()
    fy_ends: set[str] = set()

    for node in root.iter():
        if not isinstance(node.tag, str) or node.text is None:
            continue
        name = v2.normalized_local_name(node.tag)
        key = meta_names.get(name)
        if key is None:
            continue
        value = node.text.strip()
        context_ref = node.attrib.get("contextRef")
        if context_ref:
            context_meta.setdefault(context_ref, {})[key] = value
        if key == "financial_year_start":
            fy_starts.add(value)
        elif key == "financial_year_end":
            fy_ends.add(value)

    fy_start = _iso_date(next(iter(fy_starts))) if len(fy_starts) == 1 else None
    fy_end = _iso_date(next(iter(fy_ends))) if len(fy_ends) == 1 else None
    eligible_contexts: set[str] = set()
    context_diagnostics: dict[str, dict[str, object]] = {}

    for context_ref, meta in sorted(context_meta.items()):
        reporting_start = _iso_date(meta.get("reporting_period_start"))
        reporting_end = _iso_date(meta.get("reporting_period_end"))
        nature = meta.get("report_nature", "").strip().casefold()
        audit_status = meta.get("audit_status", "").strip().casefold()
        eligible = (
            fy_start is not None
            and fy_end is not None
            and reporting_start == fy_start
            and reporting_end == fy_end
            and nature == "standalone"
            and (not audit_status or audit_status == "audited")
        )
        if eligible:
            eligible_contexts.add(context_ref)
        context_diagnostics[context_ref] = {
            **meta,
            "eligible_full_year_standalone": eligible,
        }

    raw_candidates: dict[str, list[dict[str, object]]] = {
        name: [] for name in v2.XBRL_PATTERNS
    }
    for node in root.iter():
        if not isinstance(node.tag, str) or node.text is None:
            continue
        context_ref = node.attrib.get("contextRef")
        if context_ref not in eligible_contexts:
            continue
        name = v2.normalized_local_name(node.tag)
        text = node.text.strip().replace(",", "")
        try:
            value = float(text)
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        for family, patterns in v2.XBRL_PATTERNS.items():
            if name in patterns:
                raw_candidates[family].append(
                    {
                        "concept": name,
                        "value": value,
                        "unit_ref": node.attrib.get("unitRef"),
                        "context_ref": context_ref,
                        "concept_priority": patterns.index(name),
                    }
                )

    fact_status: dict[str, str] = {}
    ambiguous: dict[str, list[dict[str, object]]] = {}
    for family, candidates in raw_candidates.items():
        if not eligible_contexts:
            fact_status[family] = "NO_COMPARABLE_FULL_YEAR_CONTEXT"
            continue
        if not candidates:
            fact_status[family] = "NO_COMPARABLE_STRUCTURED_CONCEPT"
            continue

        best_priority = min(int(item["concept_priority"]) for item in candidates)
        preferred = [item for item in candidates if int(item["concept_priority"]) == best_priority]
        values = {float(item["value"]) for item in preferred}
        contexts = {str(item["context_ref"]) for item in preferred}
        if len(values) > 1:
            fact_status[family] = "AMBIGUOUS_STRUCTURED_FACT"
            ambiguous[family] = preferred
            continue
        chosen = min(
            preferred,
            key=lambda item: (str(item["context_ref"]), str(item["concept"])),
        )
        result[family] = [chosen]
        fact_status[family] = "ELIGIBLE"
        if len(contexts) > 1:
            fact_status[family] = "ELIGIBLE_IDENTICAL_MULTIPLE_CONTEXTS"

    _STRUCTURED_DIAGNOSTICS[digest] = {
        "status": "EVALUATED",
        "financial_year_start": fy_start.isoformat() if fy_start else None,
        "financial_year_end": fy_end.isoformat() if fy_end else None,
        "financial_year_metadata_unique": fy_start is not None and fy_end is not None,
        "contexts": context_diagnostics,
        "eligible_full_year_contexts": sorted(eligible_contexts),
        "fact_status": fact_status,
        "ambiguous_fact_candidates": ambiguous,
    }
    return result


def compare_fact(
    pdf_fact: dict[str, object] | None,
    candidates: list[dict[str, object]],
    *,
    eps: bool = False,
) -> dict[str, object] | None:
    if pdf_fact is None or not candidates or "current_inr" not in pdf_fact:
        return None
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    target = float(pdf_fact["current_inr"])
    value = float(candidate["value"])
    absolute = abs(value - target)
    relative = absolute / max(abs(target), 1.0)
    passed = relative <= v2.XBRL_REL_TOLERANCE
    if eps:
        passed = passed or absolute <= v2.EPS_ABS_TOLERANCE
    return {
        "pdf_value": target,
        "structured_value": value,
        "structured_concept": candidate["concept"],
        "structured_context_ref": candidate.get("context_ref"),
        "relative_difference": relative,
        "absolute_difference": absolute,
        "pass": passed,
        "selection_method": "FULL_YEAR_CONTEXT_THEN_CONCEPT_PRIORITY",
    }


def _postprocess(out: Path) -> None:
    extraction_path = out / "pdf-numeric-extractions.json"
    summary_path = out / "numeric-extraction-summary.json"
    crosscheck_path = out / "structured-crosschecks.json"

    extracted = json.loads(extraction_path.read_text())
    by_key = {
        (str(row["symbol"]), int(row["to_year"])): row
        for row in extracted
        if isinstance(row, dict)
    }
    crosschecks = json.loads(crosscheck_path.read_text())
    pdf_name = {"revenue": "revenue", "pat": "pat", "eps": "basic_eps"}

    for row in crosschecks:
        if not isinstance(row, dict) or row.get("status") != "EVALUATED":
            continue
        digest = str(row.get("source_sha256") or "")
        diagnostics = _STRUCTURED_DIAGNOSTICS.get(digest, {})
        row["structured_period_diagnostics"] = diagnostics
        comparisons = row.get("comparisons")
        if not isinstance(comparisons, dict):
            continue
        report = by_key.get((str(row["symbol"]), int(row["to_year"])), {})
        facts = report.get("facts") if isinstance(report.get("facts"), dict) else {}
        fact_status = diagnostics.get("fact_status") if isinstance(diagnostics, dict) else {}
        for family, fact_name in pdf_name.items():
            if comparisons.get(family) is not None:
                continue
            pdf_fact = facts.get(fact_name) if isinstance(facts, dict) else None
            if not isinstance(pdf_fact, dict) or "current_inr" not in pdf_fact:
                continue
            status = (
                fact_status.get(family, "NO_COMPARABLE_FULL_YEAR_CONTEXT")
                if isinstance(fact_status, dict)
                else "NO_COMPARABLE_FULL_YEAR_CONTEXT"
            )
            comparisons[family] = {"status": status}

    crosscheck_path.write_text(
        json.dumps(crosschecks, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )

    summary = json.loads(summary_path.read_text())
    summary["status"] = V3_STATUS
    summary["protocol_version"] = "v3"
    summary["v2_result_preserved"] = True
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps(summary, indent=2), flush=True)


def install_patches() -> None:
    v2.statement_score = statement_score
    v2.choose_statement_page = choose_statement_page
    v2.unit_scale = unit_scale
    v2.extract_line_fact = extract_line_fact
    v2.extract_report = extract_report
    v2.structured_facts = structured_facts
    v2.compare_fact = compare_fact


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--out", required=True)
    known, _ = parser.parse_known_args()
    install_patches()
    v2.main()
    _postprocess(Path(known.out))


if __name__ == "__main__":
    main()
