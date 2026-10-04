from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_announcements import normalize_announcement_payload

CENSUS_ID = "SS002-D001-v1"
EXPECTED_SS001_D001_SHA = "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
EXPECTED_SS001_COUNT = 2319
WINDOW_START = date(2026, 4, 1)
WINDOW_END = date(2026, 10, 4)
IST = ZoneInfo("Asia/Kolkata")

CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {
    "BUYBACK": ("buyback", "buy back"),
    "OPEN_OFFER_CONTROL": (
        "open offer",
        "change of control",
        "substantial acquisition of shares",
        "takeover offer",
    ),
    "DELISTING": ("delisting", "delist"),
    "SCHEME_REORGANISATION": (
        "scheme of arrangement",
        "merger",
        "amalgamation",
        "demerger",
        "de-merger",
        "spin off",
        "spin-off",
    ),
    "RIGHTS_ISSUE": ("rights issue", "right issue", "rights entitlement"),
    "PREFERENTIAL_WARRANT": (
        "preferential issue",
        "preferential allotment",
        "preferential basis",
        "warrants",
        "warrant allotment",
    ),
    "ASSET_SALE_DIVESTMENT": (
        "slump sale",
        "divestment",
        "divestiture",
        "sale of undertaking",
        "sale of business",
        "asset sale",
        "disposal of undertaking",
    ),
    "INSOLVENCY_RESOLUTION": (
        "insolvency",
        "cirp",
        "resolution plan",
        "nclt",
        "liquidation",
    ),
    "CAPITAL_REDUCTION": ("reduction of capital", "capital reduction"),
    "OFFER_FOR_SALE": ("offer for sale", "ofs by promoter", "promoter ofs"),
    "TENDER_OFFER": ("tender offer", "tendering of shares"),
}


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def classify_special_situation(row: dict[str, Any]) -> list[str]:
    text = f"{_clean(row.get('desc'))} {_clean(row.get('attchmntText'))}".casefold()
    return sorted(
        category
        for category, tokens in CATEGORY_TOKENS.items()
        if any(token in text for token in tokens)
    )


def _validate_market_census(census: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if census.get("census_id") != "SS001-D001-v1":
        raise AlphaContractError("SS002 D001 requires frozen SS001-D001 census")
    if census.get("census_sha256") != EXPECTED_SS001_D001_SHA:
        raise AlphaContractError("SS002 D001 SS001 census SHA mismatch")
    if census.get("eq_identity_count") != EXPECTED_SS001_COUNT:
        raise AlphaContractError("SS002 D001 SS001 identity count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if census.get(field) is not False:
            raise AlphaContractError(f"SS002 D001 requires SS001 {field}=false")
    rows = census.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SS001_COUNT:
        raise AlphaContractError("SS002 D001 SS001 rows unavailable")
    by_symbol: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _clean(row.get("symbol")).upper()
        if not symbol or symbol in by_symbol:
            raise AlphaContractError("SS002 D001 SS001 symbols must be unique")
        by_symbol[symbol] = row
    return by_symbol


def _expected_day_keys() -> list[str]:
    count = (WINDOW_END - WINDOW_START).days + 1
    return [
        date.fromordinal(WINDOW_START.toordinal() + offset).isoformat()
        for offset in range(count)
    ]


def build_special_situation_census(
    *,
    ss001_census: dict[str, Any],
    daily_payloads: dict[str, object],
    daily_raw_sha256: dict[str, str],
    generated_at_utc: str,
) -> dict[str, Any]:
    market_by_symbol = _validate_market_census(ss001_census)
    expected_days = _expected_day_keys()
    if sorted(daily_payloads) != expected_days:
        raise AlphaContractError("SS002 D001 daily payload coverage is incomplete")
    if sorted(daily_raw_sha256) != expected_days:
        raise AlphaContractError("SS002 D001 daily raw hash coverage is incomplete")

    all_ids: set[str] = set()
    candidate_events = []
    daily_counts: dict[str, int] = {}
    daily_candidate_counts: dict[str, int] = {}
    category_counts = Counter()
    mapped_count = 0
    mapped_symbols: set[str] = set()
    unmapped_symbols: set[str] = set()

    for day_text in expected_days:
        day = date.fromisoformat(day_text)
        rows = normalize_announcement_payload(
            daily_payloads[day_text],
            requested_start=day,
            requested_end=day,
        )
        daily_counts[day_text] = len(rows)
        day_candidates = 0
        for row in rows:
            announcement_id = str(row["announcement_id"])
            if announcement_id in all_ids:
                raise AlphaContractError(
                    f"SS002 D001 announcement repeated across daily sources: {announcement_id}"
                )
            all_ids.add(announcement_id)

            categories = classify_special_situation(row)
            if not categories:
                continue
            day_candidates += 1
            for category in categories:
                category_counts[category] += 1

            symbol = str(row["symbol"]).upper()
            market = market_by_symbol.get(symbol)
            if market is None:
                mapping_state = "CURRENT_IDENTITY_UNMAPPED"
                current_context = None
                unmapped_symbols.add(symbol)
            else:
                mapping_state = "CURRENT_IDENTITY_MAPPED"
                mapped_count += 1
                mapped_symbols.add(symbol)
                market_context = market.get("market")
                if not isinstance(market_context, dict):
                    raise AlphaContractError(
                        f"SS002 D001 mapped market context unavailable: {symbol}"
                    )
                current_context = {
                    "isin": market.get("isin"),
                    "listing_date": market.get("listing_date"),
                    "listing_age_days_at_2026_10_01": market.get(
                        "listing_age_days_at_2026_10_01"
                    ),
                    "median_daily_turnover_inr": market_context.get(
                        "median_daily_turnover_inr"
                    ),
                    "observed_session_count": market_context.get(
                        "observed_session_count"
                    ),
                    "in_existing_u001": bool(market.get("in_existing_u001")),
                }

            candidate_events.append(
                {
                    **row,
                    "special_situation_categories": categories,
                    "mapping_state": mapping_state,
                    "current_context": current_context,
                    "source_day": day_text,
                    "source_raw_sha256": daily_raw_sha256[day_text],
                    "return_outcomes_opened": False,
                    "portfolio_eligibility_allowed": False,
                    "live_capital_allowed": False,
                }
            )
        daily_candidate_counts[day_text] = day_candidates

    total_candidates = len(candidate_events)
    mapped_ratio = mapped_count / total_candidates if total_candidates else 1.0
    threshold_passes = {
        "complete_daily_source_coverage": True,
        "canonical_identity_unique_across_days": True,
        "exact_current_symbol_mapping_only": True,
        "minimum_current_identity_mapping_ratio": mapped_ratio >= 0.90,
    }

    generated = datetime.fromisoformat(generated_at_utc)
    if generated.tzinfo is None:
        raise AlphaContractError("SS002 D001 generated_at_utc must include timezone")

    output = {
        "schema_version": 1,
        "census_id": CENSUS_ID,
        "classification": "CURRENT_SPECIAL_SITUATION_EVENT_CENSUS_NOT_ALPHA",
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "source_audit": {
            "audit_id": "AE001-D003-v1",
            "report_sha256": (
                "7f402beecaf90f054c93ca2ceeaa01f38fcc5cd8f7f8f6391f60791768f8a91f"
            ),
        },
        "source_window": {
            "start": WINDOW_START.isoformat(),
            "end": WINDOW_END.isoformat(),
            "calendar_day_count": len(expected_days),
        },
        "input_ss001_census_sha256": EXPECTED_SS001_D001_SHA,
        "source_row_count": len(all_ids),
        "candidate_event_count": total_candidates,
        "distinct_candidate_symbol_count": len(
            {str(row["symbol"]) for row in candidate_events}
        ),
        "mapped_candidate_event_count": mapped_count,
        "mapped_candidate_event_ratio": mapped_ratio,
        "mapped_candidate_symbol_count": len(mapped_symbols),
        "unmapped_candidate_symbol_count": len(unmapped_symbols),
        "unmapped_candidate_symbols": sorted(unmapped_symbols),
        "category_counts": dict(sorted(category_counts.items())),
        "daily_source_row_counts": daily_counts,
        "daily_candidate_counts": daily_candidate_counts,
        "daily_raw_sha256": dict(sorted(daily_raw_sha256.items())),
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_attachment_acquisition": all(threshold_passes.values()),
        "events": sorted(
            candidate_events,
            key=lambda row: (
                str(row["exchange_published_at_utc"]),
                str(row["symbol"]),
                str(row["seq_id"]),
            ),
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["census_sha256"] = digest(output)
    return output
