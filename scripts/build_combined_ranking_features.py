from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

AS_OF = date(2026, 9, 7)

FINANCIAL_TERMS = (
    "revenue", "growth", "margin", "ebitda", "ebit", "profit", "pat", "sales",
    "cash flow", "free cash flow", "roce", "roe", "asset turn", "market share",
)
EXECUTION_TERMS = (
    "capacity", "commission", "production", "launch", "order", "delivery",
    "stores", "beds", "volume", "utilization", "network", "installation",
)
CAPITAL_TERMS = (
    "debt", "leverage", "capex", "capital expenditure", "cost", "saving",
    "cash", "working capital", "breakeven", "break-even",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    for candidate in (text[:10], text[:7] + "-01" if len(text) >= 7 else text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass
    return None


def source_date(candidate: dict[str, Any]) -> date | None:
    value = candidate.get("exchange_published_at_utc")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def horizon_is_clearly_expired(claim: dict[str, Any], candidate: dict[str, Any]) -> bool:
    deadline = parse_date(claim.get("target_deadline"))
    if deadline is not None:
        return deadline < AS_OF

    horizon = str(claim.get("target_horizon") or "").strip().lower()
    if not horizon:
        return False

    # Explicit Indian fiscal-year references ending before the as-of date.
    if re.search(r"\bfy\s*['’-]?\s*(?:2[45]|25|26)\b", horizon):
        return True
    if re.search(r"\bfiscal\s*(?:year\s*)?['’-]?\s*(?:2024|2025|2026)\b", horizon):
        return True

    years = [int(match) for match in re.findall(r"\b20(\d{2})\b", horizon)]
    explicit_years = [2000 + year for year in years]
    if explicit_years and max(explicit_years) < AS_OF.year:
        return True

    src = source_date(candidate)
    if src is not None and src.year < AS_OF.year:
        if any(
            token in horizon
            for token in (
                "this year",
                "current year",
                "this fiscal",
                "current fiscal",
                "this financial year",
                "current financial year",
            )
        ):
            return True

    return False


def classify_family(claim: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(claim.get(key) or "")
        for key in ("claim_type", "metric", "unit", "normalized_claim")
    ).lower()
    result: set[str] = set()
    if any(term in text for term in FINANCIAL_TERMS):
        result.add("financial_growth")
    if any(term in text for term in EXECUTION_TERMS):
        result.add("execution_capacity")
    if any(term in text for term in CAPITAL_TERMS):
        result.add("capital_discipline")
    return result


def percentile(values: dict[str, float]) -> dict[str, float]:
    symbols = sorted(values)
    result: dict[str, float] = {}
    for symbol in symbols:
        value = values[symbol]
        less = sum(values[other] < value for other in symbols)
        equal = sum(values[other] == value for other in symbols)
        result[symbol] = (less + 0.5 * equal) / len(symbols)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-report", type=Path, required=True)
    parser.add_argument("--compiled-decisions-dir", type=Path, required=True)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()

    report = load_json(args.candidate_report)
    universe = load_json(args.universe)
    members = universe.get("members")
    if not isinstance(members, list) or len(members) != 100:
        raise SystemExit("expected frozen 100-company universe")
    symbols = [str(member["symbol"]).upper() for member in members]
    if len(set(symbols)) != 100:
        raise SystemExit("universe symbols are not unique")

    records = report.get("records")
    if not isinstance(records, list) or len(records) != 794:
        raise SystemExit("candidate report is not the complete 794-source E002 report")

    candidate_by_id: dict[str, dict[str, Any]] = {}
    source_ids_by_symbol: dict[str, set[str]] = defaultdict(set)
    semantic_ids_by_symbol: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit("invalid candidate source record")
        symbol = str(record.get("symbol") or "").upper()
        source_id = str(record.get("source_id") or "")
        candidates = record.get("candidates")
        if not isinstance(candidates, list):
            raise SystemExit("candidate record lacks candidates")
        if candidates:
            source_ids_by_symbol[symbol].add(source_id)
        for candidate in candidates:
            candidate_id = str(candidate.get("candidate_id") or "")
            if not candidate_id or candidate_id in candidate_by_id:
                raise SystemExit(f"invalid/duplicate candidate id: {candidate_id}")
            if str(candidate.get("symbol") or "").upper() != symbol:
                raise SystemExit(f"candidate/source symbol mismatch: {candidate_id}")
            candidate_by_id[candidate_id] = candidate

    if len(candidate_by_id) != int(report.get("candidate_count", -1)):
        raise SystemExit("candidate report flattened count mismatch")

    decisions: dict[str, dict[str, Any]] = {}
    manifest = load_json(args.compiled_decisions_dir / "manifest.json")
    if manifest.get("complete") is not True or int(manifest.get("compiled_candidate_count", -1)) != 2322:
        raise SystemExit("compiled semantic review is not complete")
    for path in sorted(args.compiled_decisions_dir.glob("batch-*.json")):
        items = load_json(path)
        if not isinstance(items, list):
            raise SystemExit(f"compiled decision file must be list: {path}")
        for decision in items:
            candidate_id = str(decision.get("candidate_id") or "")
            if candidate_id in decisions:
                raise SystemExit(f"duplicate compiled decision: {candidate_id}")
            if candidate_id not in candidate_by_id:
                raise SystemExit(f"compiled decision absent from E002 corpus: {candidate_id}")
            decisions[candidate_id] = decision
            semantic_ids_by_symbol[str(candidate_by_id[candidate_id]["symbol"]).upper()].add(candidate_id)
    if len(decisions) != 2322:
        raise SystemExit(f"expected 2322 compiled decisions, found {len(decisions)}")

    rows: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        source_ids = source_ids_by_symbol.get(symbol, set())
        semantic_ids = semantic_ids_by_symbol.get(symbol, set())
        accepted: list[tuple[dict[str, Any], dict[str, Any]]] = []
        open_claims: list[tuple[dict[str, Any], dict[str, Any]]] = []
        accepted_sources: set[str] = set()
        open_sources: set[str] = set()
        open_types: set[str] = set()
        families: set[str] = set()

        for candidate_id in semantic_ids:
            decision = decisions[candidate_id]
            if decision.get("disposition") != "ACCEPTED":
                continue
            candidate = candidate_by_id[candidate_id]
            claim = decision.get("normalized_claim")
            if not isinstance(claim, dict):
                raise SystemExit(f"accepted decision lacks normalized claim: {candidate_id}")
            accepted.append((candidate, claim))
            accepted_sources.add(str(candidate.get("source_id") or ""))
            if not horizon_is_clearly_expired(claim, candidate):
                open_claims.append((candidate, claim))
                open_sources.add(str(candidate.get("source_id") or ""))
                open_types.add(str(claim.get("claim_type") or "UNKNOWN"))
                families.update(classify_family(claim))

        source_count = len(source_ids)
        semantic_count = len(semantic_ids)
        accepted_source_rate = len(accepted_sources) / source_count if source_count else 0.0
        open_source_rate = len(open_sources) / source_count if source_count else 0.0
        open_claim_rate = min(1.0, len(open_claims) / semantic_count) if semantic_count else 0.0
        open_claim_type_diversity = min(8, len(open_types)) / 8.0
        pillar_diversity = len(families) / 3.0

        rows[symbol] = {
            "symbol": symbol,
            "candidate_source_count": source_count,
            "semantic_candidate_count": semantic_count,
            "accepted_claim_count": len(accepted),
            "accepted_source_count": len(accepted_sources),
            "open_or_unresolved_claim_count": len(open_claims),
            "open_source_count": len(open_sources),
            "open_claim_type_count": len(open_types),
            "open_families": sorted(families),
            "accepted_source_rate": accepted_source_rate,
            "open_source_rate": open_source_rate,
            "open_claim_rate": open_claim_rate,
            "open_claim_type_diversity": open_claim_type_diversity,
            "pillar_diversity": pillar_diversity,
        }

    component_names = (
        "accepted_source_rate",
        "open_source_rate",
        "open_claim_rate",
        "open_claim_type_diversity",
        "pillar_diversity",
    )
    percentile_maps = {
        name: percentile({symbol: float(rows[symbol][name]) for symbol in symbols})
        for name in component_names
    }
    for symbol in symbols:
        percentiles = {name: percentile_maps[name][symbol] for name in component_names}
        rows[symbol]["component_percentiles"] = percentiles
        rows[symbol]["h003_forward_evidence_score"] = sum(percentiles.values()) / len(percentiles)

    ranked = sorted(
        rows.values(),
        key=lambda row: (-float(row["h003_forward_evidence_score"]), row["symbol"]),
    )
    for rank, row in enumerate(ranked, start=1):
        row["h003_forward_evidence_rank"] = rank

    payload = {
        "schema_version": 1,
        "as_of_date": AS_OF.isoformat(),
        "universe_count": 100,
        "candidate_count": len(candidate_by_id),
        "semantic_decision_count": len(decisions),
        "live_capital_allowed": False,
        "score_name": "h003_forward_evidence_score",
        "score_components": list(component_names),
        "companies": ranked,
    }
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    flat_fields = [
        "h003_forward_evidence_rank", "symbol", "h003_forward_evidence_score",
        "candidate_source_count", "semantic_candidate_count", "accepted_claim_count",
        "accepted_source_count", "open_or_unresolved_claim_count", "open_source_count",
        "open_claim_type_count", "accepted_source_rate", "open_source_rate",
        "open_claim_rate", "open_claim_type_diversity", "pillar_diversity",
    ]
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=flat_fields)
        writer.writeheader()
        for row in ranked:
            writer.writerow({key: row[key] for key in flat_fields})

    print(json.dumps({
        "top_20": [
            {"rank": row["h003_forward_evidence_rank"], "symbol": row["symbol"], "score": round(row["h003_forward_evidence_score"], 6)}
            for row in ranked[:20]
        ],
        "semantic_decisions": len(decisions),
        "candidate_count": len(candidate_by_id),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
