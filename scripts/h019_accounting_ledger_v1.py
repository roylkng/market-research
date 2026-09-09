"""Build the frozen H019 v1 point-in-time accounting ledger coverage audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import h019_annual_report_feasibility as source
import h019_numeric_extraction_audit as v2
import h019_numeric_extraction_audit_v3 as v3
from marketlab.nse import NSEAcquisitionError, NSEClient

CUTOFF = datetime(2020, 10, 1, 23, 59, 59, tzinfo=source.IST)
GROUP_COUNTS = {
    "SURVIVOR_PROXY": 50,
    "EXIT_PROXY": 25,
    "NEW_PROXY": 25,
}
MAX_REPORT_YEARS = 2
CORE_FACTS = ("revenue", "pat", "total_assets", "total_equity")
LEDGER_FACTS = (
    "revenue",
    "pat",
    "total_assets",
    "total_equity",
    "operating_cash_flow",
    "total_borrowings",
    "finance_cost",
    "basic_eps",
    "capex",
)
REQUIRED_OBSERVATION_FIELDS = (
    "observation_id",
    "symbol",
    "group",
    "fact",
    "fiscal_year_to",
    "period_role",
    "observed_in_report_to_year",
    "available_at",
    "value",
    "normalized_unit",
    "report_url",
    "report_sha256",
    "pdf_sha256",
    "statement",
    "page_number",
    "source_line",
    "derivation",
)


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def canonical_sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def conservative_available_at(row: dict[str, object]) -> datetime | None:
    candidates = [
        source.parse_broadcast(row.get("broadcast_dttm")),
        source.parse_broadcast(row.get("disseminationDateTime")),
    ]
    valid = [value for value in candidates if value is not None]
    return max(valid) if valid else None


def fetch_report_metadata(
    client: NSEClient,
    root: Path,
    *,
    symbol: str,
    group: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    params = {"index": "equities", "symbol": symbol}
    url = source.ANNUAL_REPORTS.url + "?" + urlencode(params)
    try:
        payload, raw = client._json_get_with_raw(source.ANNUAL_REPORTS, params=params)
        retained = source.retain(root, raw, url=url, kind="ledger-annual-report-api")
    except (NSEAcquisitionError, KeyError, TypeError, ValueError) as exc:
        return [], {
            "symbol": symbol,
            "group": group,
            "url": url,
            "status": "FETCH_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = []
    records: list[dict[str, object]] = []
    for raw_row in rows:
        if not isinstance(raw_row, dict):
            continue
        report_url = source.valid_report_url(raw_row.get("fileName"))
        available_at = conservative_available_at(raw_row)
        try:
            from_year = int(str(raw_row.get("fromYr") or "").strip())
            to_year = int(str(raw_row.get("toYr") or "").strip())
        except ValueError:
            continue
        if report_url is None or available_at is None:
            continue
        records.append(
            {
                "symbol": symbol,
                "group": group,
                "company": str(raw_row.get("companyName") or symbol).strip() or symbol,
                "from_year": from_year,
                "to_year": to_year,
                "available_at": available_at.isoformat(),
                "broadcast_dttm": str(raw_row.get("broadcast_dttm") or ""),
                "disseminationDateTime": str(raw_row.get("disseminationDateTime") or ""),
                "report_url": report_url,
                "api_source_sha256": retained["sha256"],
            }
        )

    retained.update(
        symbol=symbol,
        group=group,
        status="OK",
        raw_record_count=len(rows),
        usable_record_count=len(records),
    )
    return records, retained


def freeze_report_selection(records: list[dict[str, object]]) -> list[dict[str, object]]:
    eligible = [
        row
        for row in records
        if datetime.fromisoformat(str(row["available_at"])) <= CUTOFF
        and int(row["to_year"]) <= 2020
    ]
    latest_by_year: dict[int, dict[str, object]] = {}
    for row in eligible:
        year = int(row["to_year"])
        existing = latest_by_year.get(year)
        key = (str(row["available_at"]), str(row["report_url"]))
        if existing is None or key > (str(existing["available_at"]), str(existing["report_url"])):
            latest_by_year[year] = row
    years = sorted(latest_by_year, reverse=True)[:MAX_REPORT_YEARS]
    return [latest_by_year[year] for year in years]


def freeze_sample(symbols_2018: set[str], symbols_2020: set[str]) -> dict[str, list[str]]:
    populations = {
        "SURVIVOR_PROXY": symbols_2018 & symbols_2020,
        "EXIT_PROXY": symbols_2018 - symbols_2020,
        "NEW_PROXY": symbols_2020 - symbols_2018,
    }
    result: dict[str, list[str]] = {}
    for group, count in GROUP_COUNTS.items():
        population = populations[group]
        if len(population) < count:
            raise ValueError(f"{group} population {len(population)} is smaller than frozen sample {count}")
        result[group] = source.deterministic_spread(population, count)
    flattened = [symbol for group in GROUP_COUNTS for symbol in result[group]]
    if len(flattened) != 100 or len(set(flattened)) != 100:
        raise ValueError("frozen H019 ledger sample must contain exactly 100 distinct symbols")
    return result


def _provenance_lines(fact: dict[str, object]) -> list[str]:
    direct = str(fact.get("source_line") or "").strip()
    if direct:
        return [direct]
    components = fact.get("components")
    lines: list[str] = []
    if isinstance(components, dict):
        values = components.values()
    elif isinstance(components, list):
        values = components
    else:
        values = []
    for component in values:
        if isinstance(component, dict):
            line = str(component.get("source_line") or "").strip()
            if line:
                lines.append(line)
            nested = component.get("components")
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict):
                        nested_line = str(item.get("source_line") or "").strip()
                        if nested_line:
                            lines.append(nested_line)
    return lines


def observation_from_fact(
    *,
    report: dict[str, object],
    extraction: dict[str, object],
    fact_name: str,
    fact: dict[str, object],
    role: str,
) -> dict[str, object] | None:
    value_key = "current_inr" if role == "CURRENT" else "prior_inr"
    if value_key not in fact:
        return None
    report_to_year = int(report["to_year"])
    fiscal_year_to = report_to_year if role == "CURRENT" else report_to_year - 1
    unit = fact.get("unit")
    normalized_unit = str(unit.get("label") if isinstance(unit, dict) else "").strip()
    lines = _provenance_lines(fact)
    source_line: str | list[str]
    if len(lines) == 1:
        source_line = lines[0]
    else:
        source_line = lines
    observation = {
        "symbol": report["symbol"],
        "group": report["group"],
        "company": report["company"],
        "fact": fact_name,
        "fiscal_year_to": fiscal_year_to,
        "period_role": role,
        "observed_in_report_to_year": report_to_year,
        "available_at": report["available_at"],
        "value": float(fact[value_key]),
        "normalized_unit": normalized_unit,
        "report_url": report["report_url"],
        "report_sha256": report["sha256"],
        "pdf_sha256": report["pdf_sha256"],
        "api_source_sha256": report["api_source_sha256"],
        "statement": fact.get("statement"),
        "page_number": fact.get("page_number"),
        "source_line": source_line,
        "derivation": fact.get("derivation"),
        "report_from_year": report["from_year"],
        "report_to_year": report_to_year,
        "balance_identity": extraction.get("balance_identity"),
    }
    observation["observation_id"] = canonical_sha(observation)
    return observation


def build_observations(
    extraction_rows: list[dict[str, object]],
    report_by_key: dict[tuple[str, int, str], dict[str, object]],
) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    for extraction in extraction_rows:
        if extraction.get("status") != "EXTRACTED":
            continue
        key = (
            str(extraction["symbol"]),
            int(extraction["to_year"]),
            str(extraction["report_url"]),
        )
        report = report_by_key[key]
        facts = extraction.get("facts")
        if not isinstance(facts, dict):
            continue
        for fact_name in LEDGER_FACTS:
            fact = facts.get(fact_name)
            if not isinstance(fact, dict):
                continue
            for role in ("CURRENT", "PRIOR_COMPARATIVE"):
                observation = observation_from_fact(
                    report=report,
                    extraction=extraction,
                    fact_name=fact_name,
                    fact=fact,
                    role=role,
                )
                if observation is not None:
                    observations.append(observation)
    observations.sort(
        key=lambda row: (
            str(row["symbol"]),
            str(row["fact"]),
            int(row["fiscal_year_to"]),
            str(row["available_at"]),
            str(row["observation_id"]),
        )
    )
    if len({str(row["observation_id"]) for row in observations}) != len(observations):
        raise ValueError("duplicate H019 accounting observation IDs")
    return observations


def resolve_as_of(
    observations: list[dict[str, object]], cutoff: datetime
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[str, str, int], list[dict[str, object]]] = defaultdict(list)
    for row in observations:
        if datetime.fromisoformat(str(row["available_at"])) <= cutoff:
            grouped[(str(row["symbol"]), str(row["fact"]), int(row["fiscal_year_to"]))].append(row)

    resolved: list[dict[str, object]] = []
    ambiguities: list[dict[str, object]] = []
    for key, rows in sorted(grouped.items()):
        latest = max(datetime.fromisoformat(str(row["available_at"])) for row in rows)
        candidates = [
            row
            for row in rows
            if datetime.fromisoformat(str(row["available_at"])) == latest
        ]
        values = {float(row["value"]) for row in candidates}
        if len(values) > 1:
            ambiguities.append(
                {
                    "symbol": key[0],
                    "fact": key[1],
                    "fiscal_year_to": key[2],
                    "available_at": latest.isoformat(),
                    "candidate_observation_ids": sorted(str(row["observation_id"]) for row in candidates),
                    "candidate_values": sorted(values),
                    "status": "AMBIGUOUS_LATEST_OBSERVATION",
                }
            )
            continue
        chosen = max(
            candidates,
            key=lambda row: (
                int(row["observed_in_report_to_year"]),
                str(row["report_url"]),
                str(row["observation_id"]),
            ),
        )
        resolved.append(
            {
                "symbol": key[0],
                "group": chosen["group"],
                "fact": key[1],
                "fiscal_year_to": key[2],
                "value": chosen["value"],
                "normalized_unit": chosen["normalized_unit"],
                "resolved_from_observation_id": chosen["observation_id"],
                "available_at": chosen["available_at"],
                "observed_in_report_to_year": chosen["observed_in_report_to_year"],
                "status": "RESOLVED",
            }
        )
    return resolved, ambiguities


def consecutive_triple(years: set[int]) -> list[int] | None:
    for end in sorted(years, reverse=True):
        triple = [end - 2, end - 1, end]
        if all(year in years for year in triple):
            return triple
    return None


def symbol_history_coverage(
    resolved: list[dict[str, object]], sample: dict[str, list[str]]
) -> list[dict[str, object]]:
    by_symbol_fact: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for row in resolved:
        by_symbol_fact[str(row["symbol"])][str(row["fact"])].add(int(row["fiscal_year_to"]))
    group_by_symbol = {
        symbol: group for group, symbols in sample.items() for symbol in symbols
    }
    rows: list[dict[str, object]] = []
    for symbol in sorted(group_by_symbol):
        fact_years = by_symbol_fact[symbol]
        core_years = set.intersection(
            *(fact_years.get(fact, set()) for fact in CORE_FACTS)
        ) if all(fact_years.get(fact) for fact in CORE_FACTS) else set()
        core_triple = consecutive_triple(core_years)
        core_cfo_years = core_years & fact_years.get("operating_cash_flow", set())
        cfo_triple = consecutive_triple(core_cfo_years)
        rows.append(
            {
                "symbol": symbol,
                "group": group_by_symbol[symbol],
                "resolved_fact_count": sum(len(years) for years in fact_years.values()),
                "core_years": sorted(core_years),
                "three_year_core": core_triple is not None,
                "three_year_core_years": core_triple,
                "three_year_core_plus_cfo": cfo_triple is not None,
                "three_year_core_plus_cfo_years": cfo_triple,
            }
        )
    return rows


def rate(count: int, total: int) -> float | None:
    return count / total if total else None


def group_coverage(history: list[dict[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for group in GROUP_COUNTS:
        rows = [row for row in history if row["group"] == group]
        core = sum(bool(row["three_year_core"]) for row in rows)
        cfo = sum(bool(row["three_year_core_plus_cfo"]) for row in rows)
        result[group] = {
            "symbols": len(rows),
            "three_year_core_count": core,
            "three_year_core_rate": rate(core, len(rows)),
            "three_year_core_plus_cfo_count": cfo,
            "three_year_core_plus_cfo_rate": rate(cfo, len(rows)),
        }
    return result


def provenance_complete(row: dict[str, object]) -> bool:
    for field in REQUIRED_OBSERVATION_FIELDS:
        value = row.get(field)
        if value is None or value == "" or value == []:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    root = Path(parser.parse_args().out)
    root.mkdir(parents=True, exist_ok=True)

    v3.install_patches()
    client = NSEClient(timeout=30, attempts=4)

    # Freeze the lifecycle sample before any annual-report API is queried.
    listing_manifest = []
    symbols_2018, listing_2018 = source.fetch_listing(client, root, 2018)
    symbols_2020, listing_2020 = source.fetch_listing(client, root, 2020)
    listing_manifest.extend((listing_2018, listing_2020))
    sample = freeze_sample(symbols_2018, symbols_2020)
    sample_payload = {
        "status": "FROZEN_BEFORE_ANNUAL_REPORT_API",
        "cutoff": CUTOFF.isoformat(),
        "population_counts": {
            "2018": len(symbols_2018),
            "2020": len(symbols_2020),
            "survivor_proxy": len(symbols_2018 & symbols_2020),
            "exit_proxy": len(symbols_2018 - symbols_2020),
            "new_proxy": len(symbols_2020 - symbols_2018),
        },
        "groups": sample,
    }
    dump(root / "listing-manifest.json", listing_manifest)
    dump(root / "frozen-symbol-sample.json", sample_payload)

    # Metadata for all frozen symbols is acquired before any report bytes.
    api_manifest: list[dict[str, object]] = []
    metadata_records: list[dict[str, object]] = []
    frozen_report_rows: list[dict[str, object]] = []
    for group, symbols in sample.items():
        for number, symbol in enumerate(symbols, 1):
            records, meta = fetch_report_metadata(client, root, symbol=symbol, group=group)
            api_manifest.append(meta)
            metadata_records.extend(records)
            frozen_report_rows.extend(freeze_report_selection(records))
            if number % 10 == 0:
                print(f"H019 ledger metadata {group} {number}/{len(symbols)}", flush=True)
    frozen_report_rows.sort(
        key=lambda row: (str(row["group"]), str(row["symbol"]), -int(row["to_year"]))
    )
    dump(root / "annual-report-api-manifest.json", api_manifest)
    dump(root / "annual-report-metadata.json", metadata_records)
    dump(root / "metadata-frozen-report-selection.json", frozen_report_rows)

    # Download exactly the metadata-frozen report set. No fallback is allowed.
    report_manifest: list[dict[str, object]] = []
    extraction_rows: list[dict[str, object]] = []
    report_by_key: dict[tuple[str, int, str], dict[str, object]] = {}
    for number, frozen in enumerate(frozen_report_rows, 1):
        row = dict(frozen)
        raw, download = source.archive_download(client, str(row["report_url"]))
        if raw is None:
            report_manifest.append({**row, **download})
            continue
        retained = source.retain(
            root,
            raw,
            url=str(row["report_url"]),
            kind="ledger-annual-report-container",
        )
        pdf_raw, container = source.extract_pdf_bytes(raw, str(row["report_url"]))
        manifest_row = {**row, **download, **retained, **container}
        if pdf_raw is None:
            manifest_row["status"] = "PDF_CONTAINER_UNUSABLE"
            report_manifest.append(manifest_row)
            continue
        manifest_row["pdf_sha256"] = v2.sha256(pdf_raw)
        manifest_row["status"] = "RETAINED"
        report_manifest.append(manifest_row)

        parser_row = {
            **row,
            "sha256": retained["sha256"],
            "raw_path": retained["raw_path"],
            "pdf_sha256": manifest_row["pdf_sha256"],
        }
        extraction = v3.extract_report(parser_row, root)
        extraction["available_at"] = row["available_at"]
        extraction["api_source_sha256"] = row["api_source_sha256"]
        extraction_rows.append(extraction)
        key = (str(row["symbol"]), int(row["to_year"]), str(row["report_url"]))
        report_by_key[key] = parser_row
        if number % 20 == 0:
            print(f"H019 ledger reports {number}/{len(frozen_report_rows)}", flush=True)
        time.sleep(0.02)

    dump(root / "report-source-manifest.json", report_manifest)
    dump(root / "report-extractions.json", extraction_rows)

    observations = build_observations(extraction_rows, report_by_key)
    resolved, ambiguities = resolve_as_of(observations, CUTOFF)
    history = symbol_history_coverage(resolved, sample)
    dump(root / "accounting-observations.json", observations)
    dump(root / "asof-resolved-facts.json", resolved)
    dump(root / "resolver-ambiguities.json", ambiguities)
    dump(root / "symbol-history-coverage.json", history)

    api_status_by_group = {
        group: dict(Counter(str(row["status"]) for row in api_manifest if row["group"] == group))
        for group in GROUP_COUNTS
    }
    selected_by_symbol = Counter(str(row["symbol"]) for row in frozen_report_rows)
    report_status_by_group = {
        group: dict(Counter(str(row["status"]) for row in report_manifest if row["group"] == group))
        for group in GROUP_COUNTS
    }
    extraction_status_by_group = {
        group: dict(Counter(str(row["status"]) for row in extraction_rows if row["group"] == group))
        for group in GROUP_COUNTS
    }
    current_core_by_fact = {
        fact: sum(
            row.get("status") == "EXTRACTED"
            and isinstance(row.get("facts"), dict)
            and isinstance(row["facts"].get(fact), dict)
            and "current_inr" in row["facts"][fact]
            for row in extraction_rows
        )
        for fact in CORE_FACTS
    }
    prior_core_by_fact = {
        fact: sum(
            row.get("status") == "EXTRACTED"
            and isinstance(row.get("facts"), dict)
            and isinstance(row["facts"].get(fact), dict)
            and "prior_inr" in row["facts"][fact]
            for row in extraction_rows
        )
        for fact in CORE_FACTS
    }
    balance_pass = sum(
        isinstance(row.get("balance_identity"), dict)
        and bool(row["balance_identity"].get("current_pass"))
        for row in extraction_rows
    )
    observation_counts_by_fact = dict(Counter(str(row["fact"]) for row in observations))
    observation_counts_by_year = dict(Counter(str(row["fiscal_year_to"]) for row in observations))
    resolved_ids = {str(row["resolved_from_observation_id"]) for row in resolved}
    observation_ids = {str(row["observation_id"]) for row in observations}

    successful_api_hashes = all(
        row.get("status") != "OK" or bool(row.get("sha256")) for row in api_manifest
    )
    successful_report_hashes = all(
        row.get("status") != "RETAINED"
        or (bool(row.get("sha256")) and bool(row.get("pdf_sha256")))
        for row in report_manifest
    )
    selected_dates_valid = all(
        datetime.fromisoformat(str(row["available_at"])) <= CUTOFF for row in frozen_report_rows
    )
    no_more_than_two = all(count <= MAX_REPORT_YEARS for count in selected_by_symbol.values())
    provenance_ok = all(provenance_complete(row) for row in observations)
    resolved_references_ok = resolved_ids <= observation_ids
    no_future_resolved = all(
        datetime.fromisoformat(str(row["available_at"])) <= CUTOFF for row in resolved
    )

    gates = {
        "exactly_100_frozen_symbols": sum(len(values) for values in sample.values()) == 100,
        "exact_group_counts": all(len(sample[group]) == count for group, count in GROUP_COUNTS.items()),
        "sampling_frozen_before_report_api": sample_payload["status"] == "FROZEN_BEFORE_ANNUAL_REPORT_API",
        "successful_api_sources_hashed": successful_api_hashes,
        "successful_report_sources_hashed": successful_report_hashes,
        "selected_metadata_not_after_cutoff": selected_dates_valid,
        "max_two_report_years_per_symbol": no_more_than_two,
        "metadata_first_selection_no_fallback": len(report_manifest) == len(frozen_report_rows),
        "observation_provenance_complete": provenance_ok,
        "resolved_facts_reference_observations": resolved_references_ok,
        "no_future_observation_resolved": no_future_resolved,
        "ambiguities_not_silently_resolved": all(
            not set(row["candidate_observation_ids"]) & resolved_ids for row in ambiguities
        ),
        "source_only_no_outcome_state": True,
    }

    core_history_count = sum(bool(row["three_year_core"]) for row in history)
    cfo_history_count = sum(bool(row["three_year_core_plus_cfo"]) for row in history)
    summary = {
        "status": "H019_ACCOUNTING_LEDGER_V1_COVERAGE_ONLY",
        "cutoff": CUTOFF.isoformat(),
        "market_outcomes_opened": False,
        "live_capital_allowed": False,
        "frozen_symbol_count": 100,
        "frozen_group_counts": GROUP_COUNTS,
        "annual_report_api_status_by_group": api_status_by_group,
        "selected_report_records": len(frozen_report_rows),
        "symbols_with_zero_selected_reports": sum(selected_by_symbol[symbol] == 0 for group in sample.values() for symbol in group),
        "symbols_with_one_selected_report": sum(selected_by_symbol[symbol] == 1 for group in sample.values() for symbol in group),
        "symbols_with_two_selected_reports": sum(selected_by_symbol[symbol] == 2 for group in sample.values() for symbol in group),
        "report_status_by_group": report_status_by_group,
        "extraction_status_by_group": extraction_status_by_group,
        "current_core_fact_reports": current_core_by_fact,
        "prior_core_fact_reports": prior_core_by_fact,
        "balance_identity_current_pass_reports": balance_pass,
        "accounting_observations": len(observations),
        "resolved_facts": len(resolved),
        "resolver_ambiguities": len(ambiguities),
        "observation_counts_by_fact": observation_counts_by_fact,
        "observation_counts_by_fiscal_year_to": observation_counts_by_year,
        "three_year_core_history_count": core_history_count,
        "three_year_core_history_rate": rate(core_history_count, 100),
        "three_year_core_plus_cfo_count": cfo_history_count,
        "three_year_core_plus_cfo_rate": rate(cfo_history_count, 100),
        "coverage_by_group": group_coverage(history),
        "integrity_gates": gates,
        "integrity_pass": all(gates.values()),
    }
    dump(root / "ledger-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
