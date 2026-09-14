from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from marketlab.h023_ownership import MF_SHAREHOLDING_CONCEPT, parser_contract

U001_PATH = "research/prospective/universes/FY27-Q2-2026-09-06.json"
EXPECTED_SCHEMA_VERSION = 4
GATES = {
    "master_complete_symbols_min": 95,
    "symbols_with_any_xbrl_min": 95,
    "symbols_with_two_or_more_xbrl_min": 90,
    "symbols_with_adjacent_quarter_pair_min": 95,
    "symbols_with_all_probed_filings_fetched_min": 90,
    "symbols_with_mutual_funds_in_every_probed_filing_min": 80,
    "symbols_with_mutual_fund_percentage_concept_in_every_probed_filing_min": 80,
    "dominant_mutual_fund_percentage_concept_share_min": 0.90,
}

AVAILABILITY_TIMESTAMP_KEY_RE = re.compile(
    r"(?:broadcast|receipt|received|submission|submitted|filing).*?(?:time|timestamp|date)"
    r"|(?:time|timestamp).*?(?:broadcast|receipt|received|submission|submitted|filing)",
    re.IGNORECASE,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _mf_percentage_filings(report: dict[str, Any]) -> tuple[int, Counter[str]]:
    filing_count = 0
    concept_counts: Counter[str] = Counter()
    for symbol in report.get("symbol_reports", []):
        if not isinstance(symbol, dict):
            continue
        for filing in symbol.get("filings", []):
            if not isinstance(filing, dict) or filing.get("status") != "COMPLETE":
                continue
            concepts = filing.get("percentage_concepts", {}).get("MUTUAL_FUNDS", [])
            if not isinstance(concepts, list) or not concepts:
                continue
            filing_count += 1
            concept_counts.update(str(item) for item in set(concepts) if str(item))
    return filing_count, concept_counts


def _historical_availability_evidence(report: dict[str, Any]) -> list[dict[str, str]]:
    metadata = report.get("availability_metadata", {})
    candidates = metadata.get("timestamp_like_candidates", []) if isinstance(metadata, dict) else []
    retained: list[dict[str, str]] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "")
        value = str(row.get("value") or "")
        if AVAILABILITY_TIMESTAMP_KEY_RE.search(key):
            retained.append({"key": key, "value": value})
    return retained[:50]


def assess(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError(
            f"H023 source report schema must equal {EXPECTED_SCHEMA_VERSION}"
        )
    if report.get("member_count") != 100:
        raise ValueError("H023 full-U001 source report must contain frozen 100-name universe")
    if report.get("universe_path") != U001_PATH:
        raise ValueError("H023 source report is not bound to the frozen U001 path")
    if report.get("filings_per_symbol") != 2:
        raise ValueError("H023 source report must probe exactly two adjacent-quarter filings")
    if report.get("parser_contract") != parser_contract():
        raise ValueError("H023 source report parser contract does not match frozen code")
    if report.get("outcome_data_attached") is not False:
        raise ValueError("H023 source gate cannot consume outcome data")
    if report.get("live_capital_allowed") is not False:
        raise ValueError("H023 source gate cannot authorize live capital")
    summary = report.get("summary")
    if not isinstance(summary, dict):
        raise TypeError("H023 full-U001 source report lacks summary")

    checks: list[dict[str, Any]] = []
    for key, threshold in GATES.items():
        if key == "dominant_mutual_fund_percentage_concept_share_min":
            continue
        field = key.removesuffix("_min")
        observed = summary.get(field)
        passed = isinstance(observed, int) and observed >= threshold
        checks.append(
            {
                "gate": field,
                "observed": observed,
                "minimum": threshold,
                "passed": passed,
            }
        )

    mf_filing_count, concept_counts = _mf_percentage_filings(report)
    dominant_concept = None
    dominant_count = 0
    dominant_share = 0.0
    if concept_counts:
        dominant_concept, dominant_count = concept_counts.most_common(1)[0]
        dominant_share = dominant_count / mf_filing_count if mf_filing_count else 0.0
    checks.append(
        {
            "gate": "dominant_mutual_fund_percentage_concept_share",
            "observed": dominant_share,
            "minimum": GATES["dominant_mutual_fund_percentage_concept_share_min"],
            "passed": dominant_share
            >= GATES["dominant_mutual_fund_percentage_concept_share_min"],
        }
    )
    checks.append(
        {
            "gate": "dominant_mutual_fund_percentage_concept_exact",
            "observed": dominant_concept,
            "required": MF_SHAREHOLDING_CONCEPT,
            "passed": dominant_concept == MF_SHAREHOLDING_CONCEPT,
        }
    )

    availability_evidence = _historical_availability_evidence(report)
    historical_availability_proven = bool(availability_evidence)
    source_feasible = all(bool(row["passed"]) for row in checks)
    decision = (
        "PROCEED_PROSPECTIVELY"
        if source_feasible
        else "REJECT_OWNERSHIP_SOURCE_FAMILY"
    )
    if source_feasible and historical_availability_proven:
        decision = (
            "PROCEED_PROSPECTIVELY_HISTORICAL_AVAILABILITY_REQUIRES_SEPARATE_AUDIT"
        )

    return {
        "schema_version": 2,
        "hypothesis_candidate": "H023_MUTUAL_FUND_OWNERSHIP_ACCUMULATION",
        "decision": decision,
        "source_feasible": source_feasible,
        "source_report_schema_version": EXPECTED_SCHEMA_VERSION,
        "universe_path": U001_PATH,
        "parser_contract": parser_contract(),
        "historical_backtest_authorized": False,
        "historical_availability_proven_by_master_probe": historical_availability_proven,
        "historical_availability_candidates": availability_evidence,
        "gates": checks,
        "mutual_fund_percentage_filing_count": mf_filing_count,
        "dominant_mutual_fund_percentage_concept": dominant_concept,
        "dominant_mutual_fund_percentage_concept_count": dominant_count,
        "dominant_mutual_fund_percentage_concept_share": dominant_share,
        "top_mutual_fund_percentage_concepts": [
            {"concept": concept, "count": count}
            for concept, count in concept_counts.most_common(20)
        ],
        "next_step": (
            "Freeze and implement H023 prospective event capture without inspecting returns."
            if source_feasible
            else "Abandon H023 ownership and pivot to hard order-book/backlog information."
        ),
        "outcome_data_attached": False,
        "live_capital_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess H023 ownership source feasibility")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = assess(_load(args.report))
    _write(args.out, result)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0 if result["source_feasible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
