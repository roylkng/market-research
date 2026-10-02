from __future__ import annotations

import hashlib
import math
import re
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.rm001_d010_r2 import parse_reporting_date
from marketlab.rm001_d013 import (
    FY_ARCHIVES,
    IST,
    IST_MEDIAN_ABS_DELTA_MAX_SECONDS,
    IST_P95_ABS_DELTA_MAX_SECONDS,
    MATCH_DELTA_MAX_SECONDS,
    MATCH_DELTA_MIN_SECONDS,
    MIN_MATCH_FRACTION_EACH_YEAR,
    PUBLIC_SAMPLE_PER_YEAR,
    UTC_MEDIAN_ABS_DELTA_MIN_SECONDS,
    deterministic_public_time_sample,
    parse_brsr_archive,
)

R1_ID = "RM001-D013-R1-v1"
PARENT_D013_RESULT_SHA256 = (
    "1132cd63b0a7da1a8eae96acc5e7ef73d3a9ed9a0846be7a36bb713bb676a5f3"
)
BRSR_PAGE_URL = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-bussiness-sustainabilitiy-reports"
)
SCRIPT_NEIGHBORHOOD_CHARACTERS = 600
MIN_EXPLICIT_PUBLIC_TIME_COVERAGE = 0.95

RELEVANCE_TOKENS = (
    "brsr",
    "business responsibility",
    "sustainability",
    "sustainabilitiy",
)
SYMBOL_KEYS = (
    "symbol",
    "symbsymbol",
    "tckrsymb",
    "symbolname",
)
APP_ID_KEYS = (
    "appid",
    "applicationid",
    "applicationno",
    "applicationnumber",
)
PERIOD_START_KEYS = (
    "currentfinancialyearstartdate",
    "financialyearstartdate",
    "periodstartdate",
    "fromdate",
)
PERIOD_END_KEYS = (
    "currentfinancialyearenddate",
    "financialyearenddate",
    "periodenddate",
    "todate",
)
RESOURCE_KEY_TOKENS = (
    "xbrl",
    "xml",
    "filing",
    "attachment",
    "document",
    "file",
)

_API_LITERAL = re.compile(
    r"""(?P<quote>["'`])(?P<path>/api/[A-Za-z0-9_./?&=%:+-]+)(?P=quote)"""
)


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "script":
            return
        values = {key.casefold(): value for key, value in attrs}
        source = values.get("src")
        if source:
            self.sources.append(source)


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _normalized_identifier(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _is_first_party_nse(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == "nseindia.com" or host.endswith(".nseindia.com")


def extract_first_party_script_urls(
    html_bytes: bytes,
    *,
    page_url: str = BRSR_PAGE_URL,
) -> list[str]:
    text = html_bytes.decode("utf-8", errors="replace")
    parser = _ScriptParser()
    parser.feed(text)
    result = []
    for source in parser.sources:
        resolved = urljoin(page_url, source)
        if _is_first_party_nse(resolved):
            result.append(resolved)
    return sorted(set(result))


def discover_brsr_api_candidates(
    scripts: dict[str, bytes],
) -> list[dict[str, Any]]:
    occurrences: dict[str, list[dict[str, Any]]] = defaultdict(list)
    radius = SCRIPT_NEIGHBORHOOD_CHARACTERS // 2

    for script_url in sorted(scripts):
        raw = scripts[script_url]
        text = raw.decode("utf-8", errors="replace")
        normalized_text = text.replace("\\/", "/")
        for match in _API_LITERAL.finditer(normalized_text):
            literal = match.group("path")
            endpoint = literal.split("?", 1)[0]
            start = max(0, match.start() - radius)
            end = min(len(normalized_text), match.end() + radius)
            neighborhood = normalized_text[start:end]
            folded = neighborhood.casefold()
            tokens = sorted(
                {
                    token
                    for token in RELEVANCE_TOKENS
                    if token in folded
                }
            )
            if not tokens:
                continue
            occurrences[endpoint].append(
                {
                    "script_url": script_url,
                    "script_sha256": hashlib.sha256(raw).hexdigest(),
                    "relevance_tokens": tokens,
                    "neighborhood": neighborhood,
                }
            )

    candidates = []
    for endpoint, rows in occurrences.items():
        all_tokens = sorted(
            {
                token
                for row in rows
                for token in row["relevance_tokens"]
            }
        )
        candidates.append(
            {
                "endpoint_path": endpoint,
                "relevance_token_count": len(all_tokens),
                "relevance_tokens": all_tokens,
                "occurrences": rows,
            }
        )
    candidates.sort(
        key=lambda row: (
            -int(row["relevance_token_count"]),
            str(row["endpoint_path"]),
            min(
                str(item["script_url"])
                for item in row["occurrences"]
            ),
        )
    )
    return candidates


def recursively_discover_row_objects(payload: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value:
                rows.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return rows


def _normalized_items(row: dict[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    result: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for key, value in row.items():
        result[_normalized_key(key)].append((str(key), value))
    return result


def _first_text(
    items: dict[str, list[tuple[str, Any]]],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        for _, value in items.get(key, []):
            text = " ".join(str(value or "").split())
            if text:
                return text
    return None


def _parse_financial_year(value: object) -> tuple[str, str] | None:
    raw = " ".join(str(value or "").strip().split()).upper()
    if not raw:
        return None
    match = re.search(
        r"(?:FY\s*)?(20\d{2})\s*[-/]\s*(\d{2}|20\d{2})",
        raw,
    )
    if not match:
        return None
    start_year = int(match.group(1))
    end_token = match.group(2)
    end_year = (
        int(end_token)
        if len(end_token) == 4
        else (start_year // 100) * 100 + int(end_token)
    )
    if end_year < start_year:
        end_year += 100
    if end_year != start_year + 1:
        return None
    return (
        f"{start_year:04d}-04-01",
        f"{end_year:04d}-03-31",
    )


def _parse_public_timestamp(value: object) -> datetime | None:
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        return None

    iso_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(iso_raw)
    except ValueError:
        parsed = None

    if parsed is None:
        for fmt in (
            "%d-%b-%Y %H:%M:%S",
            "%d-%b-%Y %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%d %b %Y %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)
    return parsed.astimezone(UTC)


def _public_time_priority(normalized_key: str) -> int | None:
    if "dissemination" in normalized_key:
        return 0
    if "broadcast" in normalized_key:
        return 1
    if "received" in normalized_key:
        return 2
    if "published" in normalized_key:
        return 3
    if "exchange" in normalized_key and "time" in normalized_key:
        return 4
    return None


def normalize_dedicated_brsr_row(row: dict[str, Any]) -> dict[str, Any]:
    items = _normalized_items(row)
    symbol = _first_text(items, SYMBOL_KEYS)
    app_id = _first_text(items, APP_ID_KEYS)

    period_start = _first_text(items, PERIOD_START_KEYS)
    period_end = _first_text(items, PERIOD_END_KEYS)
    parsed_start = parse_reporting_date(period_start) if period_start else None
    parsed_end = parse_reporting_date(period_end) if period_end else None

    if parsed_start is None or parsed_end is None:
        for key, pairs in items.items():
            if key not in {"financialyear", "fiscalyear", "reportingyear"}:
                continue
            for _, value in pairs:
                parsed = _parse_financial_year(value)
                if parsed is not None:
                    parsed_start, parsed_end = parsed
                    break
            if parsed_start is not None and parsed_end is not None:
                break

    resources = []
    metadata_keys = []
    public_candidates: list[tuple[int, str, str, datetime]] = []
    for normalized, pairs in items.items():
        if any(token in normalized for token in RESOURCE_KEY_TOKENS):
            metadata_keys.append(normalized)
            for original, value in pairs:
                if isinstance(value, (str, int, float)):
                    text = " ".join(str(value).split())
                    if text:
                        resources.append(
                            {
                                "field": original,
                                "value": text,
                            }
                        )
        priority = _public_time_priority(normalized)
        if priority is None:
            continue
        for original, value in pairs:
            parsed = _parse_public_timestamp(value)
            if parsed is not None:
                public_candidates.append(
                    (priority, original, str(value), parsed)
                )

    public_status = "NO_EXPLICIT_PUBLIC_TIME"
    public_time = None
    public_field = None
    if public_candidates:
        public_candidates.sort(
            key=lambda item: (
                item[0],
                item[3].isoformat(),
                item[1],
            )
        )
        best_priority = public_candidates[0][0]
        best = [
            item
            for item in public_candidates
            if item[0] == best_priority
        ]
        distinct = {item[3].isoformat() for item in best}
        if len(distinct) == 1:
            public_status = "READY"
            public_field = best[0][1]
            public_time = best[0][3].isoformat()
        else:
            public_status = "AMBIGUOUS_SAME_PRIORITY_PUBLIC_TIME"

    normalized_symbol = str(symbol or "").strip().upper()
    normalized_app = _normalized_identifier(app_id)
    structural_metadata = sorted(
        set(metadata_keys)
        | {
            key
            for key in items
            if "brsr" in key
            or "sustain" in key
            or key in APP_ID_KEYS
        }
    )

    return {
        "symbol": normalized_symbol,
        "app_id": normalized_app,
        "reporting_period_start": parsed_start,
        "reporting_period_end": parsed_end,
        "resources": resources,
        "public_time_status": public_status,
        "public_time_field": public_field,
        "public_time_utc": public_time,
        "structural_metadata_keys": structural_metadata,
        "raw_row_sha256": digest(row),
    }


def structurally_eligible_rows(payload: Any) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for raw in recursively_discover_row_objects(payload):
        normalized = normalize_dedicated_brsr_row(raw)
        if not normalized["symbol"]:
            continue
        if not normalized["structural_metadata_keys"]:
            continue
        key = normalized["raw_row_sha256"]
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "normalized": normalized,
                "raw": raw,
            }
        )
    return rows


def _submission_candidates(
    filing: dict[str, Any],
) -> tuple[datetime, datetime]:
    parsed = datetime.fromisoformat(
        str(filing["submission_timestamp_parsed"])
    )
    if parsed.tzinfo is not None:
        aware = parsed.astimezone(UTC)
        return aware, aware
    return (
        parsed.replace(tzinfo=IST).astimezone(UTC),
        parsed.replace(tzinfo=UTC),
    )


def _resource_contains_app_id(
    resources: list[dict[str, str]],
    app_id: str,
) -> bool:
    target = _normalized_identifier(app_id)
    if not target:
        return False
    for item in resources:
        tokens = {
            _normalized_identifier(token)
            for token in re.findall(
                r"[A-Za-z0-9]+",
                str(item.get("value") or ""),
            )
        }
        if target in tokens:
            return True
    return False


def match_filing_to_dedicated_rows(
    *,
    filing: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    symbol = str(filing["symbol"]).strip().upper()
    app_id = _normalized_identifier(filing["app_id"])
    period = (
        str(filing["reporting_period_start"]),
        str(filing["reporting_period_end"]),
    )
    tla_ist, tla_utc = _submission_candidates(filing)

    exact_symbol = [
        row
        for row in rows
        if row["normalized"]["symbol"] == symbol
    ]
    candidates_by_mode: dict[str, list[dict[str, Any]]] = {
        "EXACT_APP_ID": [],
        "RESOURCE_CONTAINS_APP_ID": [],
        "PERIOD_AND_PUBLIC_TIME": [],
    }

    for row in exact_symbol:
        normalized = row["normalized"]
        if normalized["app_id"] and normalized["app_id"] == app_id:
            candidates_by_mode["EXACT_APP_ID"].append(row)
            continue
        if _resource_contains_app_id(normalized["resources"], app_id):
            candidates_by_mode["RESOURCE_CONTAINS_APP_ID"].append(row)
            continue

        row_period = (
            normalized["reporting_period_start"],
            normalized["reporting_period_end"],
        )
        public_text = normalized["public_time_utc"]
        if row_period != period or public_text is None:
            continue
        published = datetime.fromisoformat(public_text).astimezone(UTC)
        if abs((published - tla_ist).total_seconds()) <= 900.0:
            candidates_by_mode["PERIOD_AND_PUBLIC_TIME"].append(row)

    for mode in (
        "EXACT_APP_ID",
        "RESOURCE_CONTAINS_APP_ID",
        "PERIOD_AND_PUBLIC_TIME",
    ):
        candidates = candidates_by_mode[mode]
        if len(candidates) > 1:
            return {
                "status": "AMBIGUOUS_SAME_PRIORITY_MATCH",
                "linkage_mode": mode,
                "candidate_count": len(candidates),
                "candidate_row_sha256": sorted(
                    row["normalized"]["raw_row_sha256"]
                    for row in candidates
                ),
            }
        if len(candidates) == 1:
            row = candidates[0]["normalized"]
            result: dict[str, Any] = {
                "status": "MATCHED",
                "linkage_mode": mode,
                "row_sha256": row["raw_row_sha256"],
                "public_time_status": row["public_time_status"],
                "public_time_field": row["public_time_field"],
                "public_time_utc": row["public_time_utc"],
            }
            if row["public_time_utc"] is not None:
                published = datetime.fromisoformat(
                    str(row["public_time_utc"])
                ).astimezone(UTC)
                result.update(
                    {
                        "ist_abs_delta_seconds": abs(
                            (published - tla_ist).total_seconds()
                        ),
                        "ist_signed_delta_seconds": (
                            published - tla_ist
                        ).total_seconds(),
                        "utc_abs_delta_seconds": abs(
                            (published - tla_utc).total_seconds()
                        ),
                    }
                )
            return result

    return {
        "status": "NO_DEDICATED_BRSR_ROW_MATCH",
        "exact_symbol_row_count": len(exact_symbol),
    }


def _nearest_rank_percentile(
    values: list[float],
    percentile: float,
) -> float:
    if not values:
        raise AlphaContractError("D013-R1 percentile requires observations")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return float(ordered[rank - 1])


def evaluate_endpoint_correspondence(
    *,
    endpoint_path: str,
    sample: list[dict[str, Any]],
    rows_by_sample: dict[str, list[dict[str, Any]]],
    query_metadata_by_sample: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_year_total: dict[str, int] = defaultdict(int)
    by_year_matched: dict[str, int] = defaultdict(int)
    matched_count = 0
    explicit_public_count = 0
    ambiguous_count = 0
    reused: dict[str, list[str]] = defaultdict(list)
    linkage_modes: dict[str, int] = defaultdict(int)
    ist_abs: list[float] = []
    signed: list[float] = []
    utc_abs: list[float] = []
    result_rows = []

    for filing in sample:
        score = filing["sample_score"]
        by_year_total[filing["year"]] += 1
        match = match_filing_to_dedicated_rows(
            filing=filing,
            rows=rows_by_sample.get(score, []),
        )
        if match["status"] == "MATCHED":
            matched_count += 1
            by_year_matched[filing["year"]] += 1
            linkage_modes[str(match["linkage_mode"])] += 1
            reused[str(match["row_sha256"])].append(score)
            if match.get("public_time_utc") is not None:
                explicit_public_count += 1
                ist_abs.append(float(match["ist_abs_delta_seconds"]))
                signed.append(float(match["ist_signed_delta_seconds"]))
                utc_abs.append(float(match["utc_abs_delta_seconds"]))
        elif match["status"] == "AMBIGUOUS_SAME_PRIORITY_MATCH":
            ambiguous_count += 1

        result_rows.append(
            {
                "year": filing["year"],
                "sample_score": score,
                "stable_identity": filing["stable_identity"],
                "symbol": filing["symbol"],
                "app_id": filing["app_id"],
                "reporting_period_start": filing["reporting_period_start"],
                "reporting_period_end": filing["reporting_period_end"],
                "submission_timestamp_raw": filing[
                    "submission_timestamp_raw"
                ],
                "query": query_metadata_by_sample.get(score),
                **match,
            }
        )

    match_fraction_by_year = {
        year: (
            0.0
            if by_year_total[year] == 0
            else by_year_matched[year] / by_year_total[year]
        )
        for year in sorted(FY_ARCHIVES)
    }
    explicit_coverage = (
        0.0
        if matched_count == 0
        else explicit_public_count / matched_count
    )
    reused_rows = {
        row_hash: scores
        for row_hash, scores in reused.items()
        if len(scores) > 1
    }

    median_ist = statistics.median(ist_abs) if ist_abs else None
    p95_ist = (
        _nearest_rank_percentile(ist_abs, 0.95)
        if ist_abs
        else None
    )
    median_utc = statistics.median(utc_abs) if utc_abs else None

    gates = {
        "minimum_match_fraction_each_year": all(
            match_fraction_by_year.get(year, 0.0)
            >= MIN_MATCH_FRACTION_EACH_YEAR
            for year in FY_ARCHIVES
        ),
        "minimum_explicit_public_time_coverage": (
            explicit_coverage >= MIN_EXPLICIT_PUBLIC_TIME_COVERAGE
        ),
        "ist_median_abs_delta_within_60s": (
            median_ist is not None
            and median_ist <= IST_MEDIAN_ABS_DELTA_MAX_SECONDS
        ),
        "ist_p95_abs_delta_within_300s": (
            p95_ist is not None
            and p95_ist <= IST_P95_ABS_DELTA_MAX_SECONDS
        ),
        "all_signed_deltas_within_buffer_contract": (
            bool(signed)
            and min(signed) >= MATCH_DELTA_MIN_SECONDS
            and max(signed) <= MATCH_DELTA_MAX_SECONDS
        ),
        "utc_median_abs_delta_at_least_4h": (
            median_utc is not None
            and median_utc >= UTC_MEDIAN_ABS_DELTA_MIN_SECONDS
        ),
        "zero_row_reuse": not reused_rows,
        "zero_same_priority_ambiguity": ambiguous_count == 0,
    }

    return {
        "endpoint_path": endpoint_path,
        "sample_count": len(sample),
        "matched_count": matched_count,
        "match_fraction_by_year": match_fraction_by_year,
        "linkage_mode_counts": dict(sorted(linkage_modes.items())),
        "explicit_public_time_count": explicit_public_count,
        "explicit_public_time_coverage": explicit_coverage,
        "ambiguous_match_count": ambiguous_count,
        "reused_row_identities": reused_rows,
        "ist_median_abs_delta_seconds": median_ist,
        "ist_p95_abs_delta_seconds": p95_ist,
        "ist_min_signed_delta_seconds": min(signed) if signed else None,
        "ist_max_signed_delta_seconds": max(signed) if signed else None,
        "utc_median_abs_delta_seconds": median_utc,
        "gates": gates,
        "pass": all(gates.values()),
        "rows": result_rows,
        "percentile_method": "NEAREST_RANK",
    }


def build_r1_report(
    *,
    archives: dict[str, bytes],
    page_url: str,
    page_sha256: str,
    script_sources: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    endpoint_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    filings = []
    year_reports = {}
    for year in sorted(FY_ARCHIVES):
        raw = archives.get(year)
        if raw is None:
            raise AlphaContractError(f"D013-R1 missing archive {year}")
        parsed = parse_brsr_archive(year=year, raw=raw)
        year_reports[year] = {
            key: value
            for key, value in parsed.items()
            if key != "filings"
        }
        filings.extend(parsed["filings"])
    sample = deterministic_public_time_sample(
        filings,
        per_year=PUBLIC_SAMPLE_PER_YEAR,
    )

    passing = [
        row["endpoint_path"]
        for row in endpoint_reports
        if row.get("pass") is True
    ]
    source_discovery_pass = bool(candidates)
    unique_endpoint_pass = len(passing) == 1
    passed = source_discovery_pass and unique_endpoint_pass

    report: dict[str, Any] = {
        "schema_version": 1,
        "diagnostic_id": R1_ID,
        "evidence_class": "SOURCE_EVENT_CORRESPONDENCE_NO_RETURN_OUTCOMES",
        "parent_d013_result_sha256": PARENT_D013_RESULT_SHA256,
        "parent_d013_status": "FAIL_PERIOD_PARTITIONED_ASOF_TIMELINE",
        "parent_d013_status_changed": False,
        "page": {
            "url": page_url,
            "raw_sha256": page_sha256,
        },
        "script_sources": script_sources,
        "candidate_endpoints": candidates,
        "sample_count": len(sample),
        "sample_score_sha256": digest(
            [row["sample_score"] for row in sample]
        ),
        "year_reports": year_reports,
        "endpoint_reports": endpoint_reports,
        "passing_endpoint_paths": passing,
        "gates": {
            "dedicated_brsr_api_candidate_discovered": source_discovery_pass,
            "exactly_one_endpoint_passes_correspondence": unique_endpoint_pass,
        },
        "status": (
            "PASS_DEDICATED_BRSR_SOURCE_EVENT_CORRESPONDENCE"
            if passed
            else "FAIL_DEDICATED_BRSR_SOURCE_EVENT_CORRESPONDENCE"
        ),
        "d013_r2_authorized": passed,
        "d013_status_changed": False,
        "d013_multi_nic_failure_resolved": False,
        "return_labels_opened": False,
        "risk_model_fit_performed": False,
        "portfolio_fit_performed": False,
        "live_capital_allowed": False,
    }
    report["result_sha256"] = digest(report)
    return report
