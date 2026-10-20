"""L001 P018: independently reprice all five Zuari listed stakes on 2026-10-19.

Use original whole-market NSE UDiFF ZIP bytes, not the 300-name HG009 subset
(which lacks some underlying securities). Keep June issuer holding units,
March debt and March basic share count explicitly STALE. This is NOT an
investable parent-equity NAV or prospective Oct15/Oct19 trading signal.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from marketlab.alpha import AlphaContractError, digest
from marketlab.alpha_market import parse_udiff_eq_panel
from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.h021_daily_prices import (
    official_market_transport_ready,
    validate_daily_source_observation,
)
from marketlab.hg009_daily_io import original_source_bytes
from marketlab.l001_p012_zuari_reprice import (
    ISSUER_JUNE_DECK_SHA,
    JUNE_REPORTED_TOTAL_CR,
    MARCH_CASH_CR,
    MARCH_GROSS_BORROWINGS_CR,
    ORIGINAL_JUNE_HOLDINGS,
)

RESEARCH_ID = "L001-P018-20261020-DATED-FIVE-STAKE-VALUATION-REDTEAM-v1"
DATES = ("2026-10-15", "2026-10-19")
PINS = {
    "2026-10-15": {
        "udiff": "3d1c7039e2c70868cc44b51d1f9e4b0f942afc0575fe8c4a524aed9e01eac3e8",
        "h021": "6bee8067e331ab43830f0ae5a944c9c167a5a7f55137c403c4ebd6a43df83da0",
    },
    "2026-10-19": {
        "udiff": "f0a2e9bf7cb185bb112704355772d2954d662abee3d7295414aabc26d6ecfbde",
        "h021": "1914521cd4ced4d361d2e65453196501bb3f327469f8abad598b4c18cd3c9cf6",
    },
}
CALENDAR = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)
CAL_SHA = "2c3c3fb92f118b1343316879d2935fda41ae8cf12da7843109a3168260c766ce"
H021_ROOT = Path("research/prospective/h021/daily-prices")
HISTORICAL_PARENT_SHARES = 29781184
P012_OCT15_STAKE_MARK_CR = 3820.124826
ZUARI_PARENT_ISIN = "INE217A01012"


def _utc(timestamp: str, *, label: str) -> datetime:
    try:
        t = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError) as exc:
        raise AlphaContractError(f"P018 invalid UTC source time for {label}") from exc
    if t.tzinfo is None:
        raise AlphaContractError(f"P018 source time without zone: {label}")
    return t.astimezone(UTC)


def _positive(value: Any, *, label: str) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
        raise AlphaContractError(f"P018 original NSE close not finite positive: {label}")
    return float(value)


def _prices_from_zip(raw_zip: bytes, *, session: str) -> dict[tuple[str, str], float]:
    bars = parse_udiff_eq_panel(raw_zip, session_date=date.fromisoformat(session))
    needed = [
        (holding.symbol, holding.isin) for holding in ORIGINAL_JUNE_HOLDINGS
    ] + [("ZUARIIND", ZUARI_PARENT_ISIN)]
    result: dict[tuple[str, str], float] = {}
    for symbol, isin in needed:
        all_symbol = [x for x in bars if x.symbol == symbol]
        correct = [x for x in all_symbol if x.isin == isin]
        if len(all_symbol) != 1 or len(correct) != 1:
            raise AlphaContractError(
                f"P018 original NSE EQ symbol/ISIN missing or ambiguous: {symbol}"
            )
        result[(symbol, isin)] = _positive(
            correct[0].close_price, label=symbol
        )
    if len(result) != 6:
        raise AlphaContractError("P018 all 5 investments plus Zuari parent required")
    return result


def _mark(
    price_map: dict[tuple[str, str], float],
) -> tuple[float, list[dict[str, Any]]]:
    exact_holdings = {(h.symbol, h.isin) for h in ORIGINAL_JUNE_HOLDINGS}
    if not exact_holdings.issubset(price_map):
        raise AlphaContractError("P018 all five original listed stakes required")
    rounded_june = sum(h.june_mark_cr for h in ORIGINAL_JUNE_HOLDINGS)
    if rounded_june != 4224 or JUNE_REPORTED_TOTAL_CR != 4223.0:
        raise AlphaContractError("P018 June issuer 4223 vs 4224 rounding changed")
    scale = JUNE_REPORTED_TOTAL_CR / rounded_june
    rows = []
    for h in ORIGINAL_JUNE_HOLDINGS:
        price = _positive(price_map[(h.symbol, h.isin)], label=h.symbol)
        implied = h.june_mark_cr * price / h.june_reference_price_inr * scale
        rows.append({
            "symbol": h.symbol,
            "original_isin": h.isin,
            "issuer_rounded_June_portfolio_mark_cr": h.june_mark_cr,
            "issuer_original_June_reference_price_inr": h.june_reference_price_inr,
            "NSE_original_close_inr": price,
            "unchanged_June_quantity_hypothesis_mark_cr": round(implied, 6),
        })
    total = sum(
        h.june_mark_cr * price_map[(h.symbol, h.isin)]
        / h.june_reference_price_inr * scale
        for h in ORIGINAL_JUNE_HOLDINGS
    )
    if abs(total - sum(x["unchanged_June_quantity_hypothesis_mark_cr"] for x in rows)) > 0.00001:
        raise AlphaContractError("P018 repriced source marks do not reconcile")
    return total, rows


def load_original_sources(root: Path) -> tuple[dict[str, Any], dict[str, dict]]:
    calendar = load_calendar_snapshot(root / CALENDAR)
    if calendar.sha256 != CAL_SHA:
        raise AlphaContractError("P018 original frozen calendar version changed")
    actual_sessions = {s.session_date: s for s in calendar.sessions}
    if (
        any(session not in actual_sessions for session in DATES)
        or "2026-10-20" in actual_sessions
        or ISSUER_JUNE_DECK_SHA
        != "6ebec1ef99aba350000aab28b1e9f1b6c6a39471458df488ece9c7f8ea4fb25b"
    ):
        raise AlphaContractError("P018 original exchange dates or issuer deck drift")
    prices = {}
    receipts = {}
    for session in DATES:
        packet = json.loads((root / H021_ROOT / f"{session}-v1.json").read_text("utf-8"))
        validate_daily_source_observation(packet)
        if (
            packet.get("session_date_ist") != session
            or packet.get("packet_sha256") != PINS[session]["h021"]
            or packet.get("stock_source", {}).get("sha256") != PINS[session]["udiff"]
            or not official_market_transport_ready(packet)
        ):
            raise AlphaContractError(f"P018 source original H021 receipts changed: {session}")
        for name in ("stock_source", "index_source"):
            captured = _utc(packet[name]["captured_at_utc"], label=name)
            official_close = _utc(
                actual_sessions[session].close_timestamp_utc, label="NSE close"
            )
            if captured < official_close:
                raise AlphaContractError("P018 source first observed before NSE close")
        raw = original_source_bytes(root, packet["stock_source"], suffix=".zip")
        # Preserve original independent index source receipt as well. The
        # quoted-investment mark itself requires only official cash EQ closes.
        index = original_source_bytes(root, packet["index_source"], suffix=".csv")
        if not index:
            raise AlphaContractError("P018 missing original Nifty500 report bytes")
        prices[session] = _prices_from_zip(raw, session=session)
        receipts[session] = {
            "H021_signed_original_packet_sha256": packet["packet_sha256"],
            "official_raw_udiff_sha256": hashlib.sha256(raw).hexdigest(),
            "official_original_index_sha256": hashlib.sha256(index).hexdigest(),
            "NSE_stock_source_url": packet["stock_source"]["url"],
            "NSE_stock_actual_captured_at_utc": packet["stock_source"]["captured_at_utc"],
            "NSE_index_actual_captured_at_utc": packet["index_source"]["captured_at_utc"],
            "source_is_trade_fill": False,
        }
    return prices, receipts


def build_l001_p018(
    source_prices: dict[str, dict[tuple[str, str], float]],
    receipts: dict[str, dict],
) -> dict:
    if set(source_prices) != set(DATES) or set(receipts) != set(DATES):
        raise AlphaContractError("P018 requires both exact original NSE dates")
    marks, details = {}, {}
    for day in DATES:
        marks[day], details[day] = _mark(source_prices[day])
    if abs(marks["2026-10-15"] - P012_OCT15_STAKE_MARK_CR) > 0.000001:
        raise AlphaContractError("P018 old signed P012 Oct15 asset-mark drift")
    current_parent = source_prices["2026-10-19"][("ZUARIIND", ZUARI_PARENT_ISIN)]
    old_parent = source_prices["2026-10-15"][("ZUARIIND", ZUARI_PARENT_ISIN)]
    if abs(old_parent - 267.55) > 1e-8 or abs(current_parent - 259.1) > 1e-8:
        raise AlphaContractError("P018 prior issuer Oct15/19 source quote drift")
    old_march_net_debt = MARCH_GROSS_BORROWINGS_CR - MARCH_CASH_CR
    hist_cap_oct19 = current_parent * HISTORICAL_PARENT_SHARES / 1e7
    old_debt_residual_oct19 = marks["2026-10-19"] - old_march_net_debt
    additional_haircut = (
        old_debt_residual_oct19 - hist_cap_oct19
    ) / marks["2026-10-19"]
    company_rows = []
    first = {x["symbol"]: x for x in details["2026-10-15"]}
    second = {x["symbol"]: x for x in details["2026-10-19"]}
    for h in ORIGINAL_JUNE_HOLDINGS:
        f = first[h.symbol]
        s = second[h.symbol]
        company_rows.append({
            "symbol": h.symbol,
            "original_isin": h.isin,
            "issuer_reported_June_rounded_stake_mark_cr": h.june_mark_cr,
            "NSE_Oct15_EQ_close_inr": f["NSE_original_close_inr"],
            "NSE_Oct19_EQ_close_inr": s["NSE_original_close_inr"],
            "Oct15_pro_forma_stake_mark_cr": f["unchanged_June_quantity_hypothesis_mark_cr"],
            "Oct19_pro_forma_stake_mark_cr": s["unchanged_June_quantity_hypothesis_mark_cr"],
            "listed_share_count_still_unchanged_since_June_verified": False,
            "pledge_release_and_parent_repatriation_verified": False,
            "date_to_date_close_is_economic_total_return": False,
        })
    stresses = [
        {
            "additional_holding_portfolio_markdown_fraction_not_forecast": haircut,
            "Oct19_hypothetical_stake_mark_cr": round(
                marks["2026-10-19"] * (1 - haircut), 4
            ),
            "less_stale_March_net_borrowings_cr": round(old_march_net_debt, 4),
            "hypothetical_residual_after_old_March_net_debt_cr": round(
                marks["2026-10-19"] * (1 - haircut) - old_march_net_debt, 4
            ),
            "hypothetical_gap_to_Oct19_old_basic_equity_cap_cr": round(
                marks["2026-10-19"] * (1 - haircut)
                - old_march_net_debt - hist_cap_oct19, 4
            ),
        }
        for haircut in (0.0, 0.1, 0.2, 0.3)
    ]
    report = {
        "schema_version": 1,
        "research_id": RESEARCH_ID,
        "as_of_research_date": "2026-10-20",
        "classification": "RETROSPECTIVE_SAME_SESSION_FIVE_STAKE_MARK_NOT_FAIR_VALUE",
        "original_source_receipts": receipts,
        "original_june_deck_sha256_previous_original_audit": ISSUER_JUNE_DECK_SHA,
        "june_deck_pdf_independently_reaudited_in_this_run": False,
        "original_issuer_june_reported_portfolio_mark_cr": JUNE_REPORTED_TOTAL_CR,
        "source_rounded_five_stakes_total_cr": 4224,
        "original_june_holdings_verified_unchanged_by_oct19": False,
        "stake_marks_by_date_cr": {
            day: round(marks[day], 6) for day in DATES
        },
        "oct15_to_oct19_portfolio_mark_change_cr_not_shareholder_profit": round(
            marks["2026-10-19"] - marks["2026-10-15"], 6
        ),
        "five_source_repriced_listed_holdings": company_rows,
        "parent_listed_symbol": "ZUARIIND",
        "parent_listed_isin": ZUARI_PARENT_ISIN,
        "parent_Oct15_official_EQ_close_inr": old_parent,
        "parent_Oct19_official_EQ_close_inr": current_parent,
        "parent_original_share_count_historical_not_current": HISTORICAL_PARENT_SHARES,
        "parent_Oct19_cap_from_old_basic_shares_cr_not_current_fd_cap": round(
            hist_cap_oct19, 4
        ),
        "net_borrowings_as_of_2026_03_31_cr_not_current": round(
            old_march_net_debt, 4
        ),
        "Oct19_stakes_less_stale_March_net_debt_cr_not_equity_fair_value": round(
            old_debt_residual_oct19, 4
        ),
        "Oct19_gross_hypothetical_residual_to_old_cap_cr": round(
            old_debt_residual_oct19 - hist_cap_oct19, 4
        ),
        "Oct19_further_markdown_erasing_apparent_gap_fraction": round(
            additional_haircut, 8
        ),
        "additional_markdown_sensitivities": stresses,
        "October20_is_official_NSE_Dussehra_holiday": True,
        "current_oct19_entity_stake_units_verified": False,
        "March_to_Oct19_realized_cash_and_current_debt_verified": False,
        "pledged_asset_obligations_double_subtracted": False,
        "actual_parent_lender_waterfall_or_liquidation_tax_verified": False,
        "source_prices_tradable_at_close_verified": False,
        "after_tax_liquidation_or_owner_equity_NAV_verified": False,
        "fresh_issuer_buy_signal_from_posthoc_original_close": False,
        "forecast_next_year_shareholder_return": None,
        "portfolio_eligible": False,
        "live_capital_allowed": False,
    }
    report["report_sha256"] = digest(report)
    return report


def materialize_l001_p018(root: Path) -> dict:
    prices, receipts = load_original_sources(root)
    return build_l001_p018(prices, receipts)


def validate_l001_p018(packet: dict, *, root: Path) -> None:
    unsigned = copy.deepcopy(packet)
    stored = unsigned.pop("report_sha256", None)
    if stored != digest(unsigned):
        raise AlphaContractError("P018 original source report hash changed")
    if packet != materialize_l001_p018(root):
        raise AlphaContractError("P018 report not reproducible from raw NSE originals")
