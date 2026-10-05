from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

CONTEXT_ID = "HG005-D001-v1"
EXPECTED_SYMBOLS = {
    "ANANTRAJ",
    "DEVX",
    "INOXGREEN",
    "NPST",
    "SAMBHV",
}
EXPECTED_HG004_L002_SHA = (
    "6bd1a43d29460fc18389dfdcb7241c95d1de0acb80b769a728946ef81c031683"
)
EXPECTED_HG004_L001_SHA = (
    "a402b39a8890cd2fac3218bb94673f8b9c00b1f325315f9ec93863c22d9a1d12"
)
EXPECTED_SS001_SHA = (
    "0cfdc8658873a09f0cfa547467108888523eee88951050acfd2df8bd131829b7"
)
EXPECTED_GF001_SHA = (
    "dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7"
)
EXPECTED_FA001_SHA = (
    "cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124"
)
FROZEN_PRICE_SESSION = "2026-10-01"

DEVX_PREF_EQUITY = 4_444_440
DEVX_WARRANTS = 3_333_330
SAMBHV_PENDING_WARRANTS = 8_695_400


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _finite_positive(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AlphaContractError(f"{label} must be numeric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise AlphaContractError(f"{label} must be finite and positive")
    return parsed


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    parsed = float(value)
    return parsed if math.isfinite(parsed) else None


def _require_false(payload: dict[str, Any], field: str, label: str) -> None:
    if payload.get(field) is not False:
        raise AlphaContractError(f"{label} requires {field}=false")


def _validate_sources(
    *,
    hg004_l002: dict[str, Any],
    hg004_l001: dict[str, Any],
    ss001: dict[str, Any],
    gf001: dict[str, Any],
    fa001: dict[str, Any],
) -> None:
    if hg004_l002.get("synthesis_id") != "HG004-L002-v1":
        raise AlphaContractError("HG005 requires frozen HG004-L002")
    if hg004_l002.get("synthesis_sha256") != EXPECTED_HG004_L002_SHA:
        raise AlphaContractError("HG005 HG004-L002 SHA mismatch")
    if hg004_l001.get("run_id") != "HG004-L001-GPT56SOL-NATIVE-v1":
        raise AlphaContractError("HG005 requires frozen HG004-L001")
    if hg004_l001.get("run_sha256") != EXPECTED_HG004_L001_SHA:
        raise AlphaContractError("HG005 HG004-L001 SHA mismatch")
    if ss001.get("census_id") != "SS001-D001-v1":
        raise AlphaContractError("HG005 requires frozen SS001-D001")
    if ss001.get("census_sha256") != EXPECTED_SS001_SHA:
        raise AlphaContractError("HG005 SS001 SHA mismatch")
    if gf001.get("panel_id") != "GF001-D002-v1":
        raise AlphaContractError("HG005 requires frozen GF001-D002")
    if gf001.get("panel_sha256") != EXPECTED_GF001_SHA:
        raise AlphaContractError("HG005 GF001 SHA mismatch")
    if fa001.get("panel_id") != "FA001-D002-v1":
        raise AlphaContractError("HG005 requires frozen FA001-D002")
    if fa001.get("panel_sha256") != EXPECTED_FA001_SHA:
        raise AlphaContractError("HG005 FA001 SHA mismatch")

    for label, payload in (
        ("HG004-L002", hg004_l002),
        ("HG004-L001", hg004_l001),
        ("SS001-D001", ss001),
        ("GF001-D002", gf001),
        ("FA001-D002", fa001),
    ):
        for field in ("return_outcomes_opened", "portfolio_eligibility_allowed", "live_capital_allowed"):
            _require_false(payload, field, label)


def parse_shareholding_counts(raw: bytes, *, symbol: str) -> dict[str, int]:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise AlphaContractError(f"{symbol}: shareholding XBRL is invalid") from exc

    symbol_values = {
        (element.text or "").strip().upper()
        for element in root.iter()
        if _local_name(element.tag) == "Symbol" and (element.text or "").strip()
    }
    if symbol_values != {symbol.upper()}:
        raise AlphaContractError(
            f"{symbol}: shareholding XBRL symbol mismatch {sorted(symbol_values)}"
        )

    wanted = {
        "fully_paid_shares": "NumberOfFullyPaidUpEquityShares",
        "fully_diluted_shares": (
            "NumberOfSharesOnFullyDilutedBasisIncludingWarrantsESOPAndConvertibleSecurities"
        ),
    }
    out: dict[str, int] = {}
    for field, concept in wanted.items():
        values: set[int] = set()
        for element in root.iter():
            if _local_name(element.tag) != concept:
                continue
            if element.attrib.get("contextRef") != "ShareholdingPattern_ContextI":
                continue
            if element.attrib.get("unitRef") != "shares":
                raise AlphaContractError(f"{symbol}: {concept} unitRef must equal shares")
            text = (element.text or "").strip().replace(",", "")
            try:
                value = int(text)
            except ValueError as exc:
                raise AlphaContractError(f"{symbol}: {concept} is not an integer") from exc
            if value <= 0:
                raise AlphaContractError(f"{symbol}: {concept} must be positive")
            values.add(value)
        if len(values) != 1:
            raise AlphaContractError(
                f"{symbol}: {concept} must have one aggregate value, got {sorted(values)}"
            )
        out[field] = next(iter(values))

    if out["fully_diluted_shares"] < out["fully_paid_shares"]:
        raise AlphaContractError(f"{symbol}: fully diluted shares below fully paid shares")
    return out


def _index_rows(payload: dict[str, Any], *, field: str = "symbol") -> dict[str, dict[str, Any]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise AlphaContractError("HG005 source rows unavailable")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG005 source row must be an object")
        symbol = str(row.get(field) or "").upper()
        if symbol:
            if symbol in result:
                raise AlphaContractError(f"HG005 duplicate source symbol: {symbol}")
            result[symbol] = row
    return result


def _l001_by_symbol(run: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = run.get("rows")
    if not isinstance(rows, list) or len(rows) != 19:
        raise AlphaContractError("HG005 requires 19 HG004-L001 rows")
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        symbols = row.get("symbols")
        if not isinstance(symbols, list) or len(symbols) != 1:
            raise AlphaContractError("HG005 L001 row must bind one symbol")
        result[str(symbols[0]).upper()].append(row)
    return result


def _fact_value(fa_row: dict[str, Any], section: str, field: str, unit: str) -> float | None:
    block = fa_row.get(section)
    if not isinstance(block, dict) or block.get("status") != "READY":
        return None
    parsed = block.get("parsed")
    if not isinstance(parsed, dict):
        return None
    facts = parsed.get("facts")
    if not isinstance(facts, dict):
        return None
    fact = facts.get(field)
    if not isinstance(fact, dict) or fact.get("status") != "READY":
        return None
    if fact.get("unit_ref") != unit:
        return None
    return _finite(fact.get("value"))


def _current_market(ss_row: dict[str, Any]) -> tuple[float, float | None]:
    market = ss_row.get("market")
    if not isinstance(market, dict):
        raise AlphaContractError("HG005 SS001 market context unavailable")
    if market.get("last_observed_session") != FROZEN_PRICE_SESSION:
        raise AlphaContractError("HG005 current price session mismatch")
    close = _finite_positive(market.get("last_close"), label="current close")
    turnover = _finite(market.get("median_daily_turnover_inr"))
    return close, turnover


def _latest_governance(gf_row: dict[str, Any]) -> dict[str, Any]:
    latest = gf_row.get("latest")
    if not isinstance(latest, dict) or latest.get("parser_status") != "CORE_READY":
        raise AlphaContractError(f"{gf_row.get('symbol')}: latest governance is not CORE_READY")
    ownership_delta = gf_row.get("ownership_delta_pp")
    promoter_delta = (
        ownership_delta.get("promoter_percentage_points")
        if isinstance(ownership_delta, dict)
        else None
    )
    enc = latest.get("promoter_encumbrance")
    if not isinstance(enc, dict):
        raise AlphaContractError("HG005 governance encumbrance unavailable")
    return {
        "report_date": latest.get("report_date"),
        "promoter_percentage": latest.get("promoter_percentage"),
        "promoter_delta_pp": promoter_delta,
        "promoter_pledge": enc.get("pledge"),
        "promoter_ndu": enc.get("non_disposal_undertaking"),
        "promoter_other_encumbrance": enc.get("other_encumbrance"),
    }


def _explicit_l001(
    rows: list[dict[str, Any]],
    *,
    family: str,
    field: str,
) -> list[dict[str, Any]]:
    results = []
    for row in rows:
        extraction = row.get("validated_extraction")
        if not isinstance(extraction, dict):
            continue
        fact = (
            extraction.get("facts", {})
            .get(family, {})
            .get(field, {})
        )
        if isinstance(fact, dict) and fact.get("status") == "EXPLICIT":
            results.append(
                {
                    "document_id": row.get("document_id"),
                    "value": fact.get("value"),
                    "unit": fact.get("unit"),
                    "transaction_stage": extraction.get("transaction_stage"),
                }
            )
    return results


def _market_and_financial_context(
    *,
    symbol: str,
    close: float,
    turnover: float | None,
    share_counts: dict[str, int],
    fa_row: dict[str, Any],
) -> dict[str, Any]:
    paid = share_counts["fully_paid_shares"]
    diluted = share_counts["fully_diluted_shares"]
    basic_cap = close * paid
    fd_cap = close * diluted

    eps = _fact_value(fa_row, "annual", "basic_eps", "INRPerShare")
    trailing_pe = close / eps if eps is not None and eps > 0 else None

    cash = _fact_value(fa_row, "annual", "cash", "INR")
    cur_inv = _fact_value(fa_row, "annual", "current_investments", "INR")
    noncur_inv = _fact_value(fa_row, "annual", "noncurrent_investments", "INR")
    cur_debt = _fact_value(fa_row, "annual", "borrowings_current", "INR")
    noncur_debt = _fact_value(fa_row, "annual", "borrowings_noncurrent", "INR")
    net_financial_assets = None
    if None not in (cash, cur_inv, noncur_inv, cur_debt, noncur_debt):
        net_financial_assets = cash + cur_inv + noncur_inv - cur_debt - noncur_debt

    return {
        "price_session": FROZEN_PRICE_SESSION,
        "close_price_inr": close,
        "median_daily_turnover_inr": turnover,
        "fully_paid_shares": paid,
        "reported_fully_diluted_shares": diluted,
        "basic_market_cap_inr": basic_cap,
        "basic_market_cap_inr_crore": basic_cap / 10_000_000.0,
        "reported_fd_market_cap_inr": fd_cap,
        "reported_fd_market_cap_inr_crore": fd_cap / 10_000_000.0,
        "fy26_basic_eps_inr": eps,
        "current_trailing_pe": trailing_pe,
        "net_financial_assets_inr": net_financial_assets,
        "net_financial_assets_to_reported_fd_market_cap": (
            net_financial_assets / fd_cap
            if net_financial_assets is not None and fd_cap > 0
            else None
        ),
        "annual_total_equity_inr": _fact_value(fa_row, "annual", "total_equity", "INR"),
        "annual_investment_property_inr": _fact_value(
            fa_row, "annual", "investment_property", "INR"
        ),
        "annual_cwip_inr": _fact_value(
            fa_row, "annual", "capital_work_in_progress", "INR"
        ),
        "annual_ppe_inr": _fact_value(fa_row, "annual", "ppe", "INR"),
        "q1_fy27_revenue_inr": _fact_value(fa_row, "quarter", "revenue", "INR"),
        "q1_fy27_pat_inr": _fact_value(fa_row, "quarter", "pat", "INR"),
        "q1_fy27_basic_eps_inr": _fact_value(
            fa_row, "quarter", "basic_eps", "INRPerShare"
        ),
    }


def _lane_after_d001(
    *,
    symbol: str,
    lane: dict[str, Any],
    market: dict[str, Any],
    latest_counts: dict[str, int],
    prior_counts: dict[str, int] | None,
    l001_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    family = str(lane["economic_family"])
    terms = lane.get("explicit_terms")
    if not isinstance(terms, dict):
        raise AlphaContractError(f"{symbol}: HG004 lane explicit terms unavailable")

    result: dict[str, Any] = {
        "economic_family": family,
        "hg004_readiness_state": lane.get("readiness_state"),
        "evidence_document_ids": lane.get("evidence_document_ids"),
        "mechanical_metrics": {},
        "remaining_source_inputs": [
            value
            for value in lane.get("missing_inputs", [])
            if value
            not in {
                "CURRENT_MARKET_PRICE",
                "CURRENT_MARKET_CAP",
                "CURRENT_FULLY_DILUTED_SHARE_COUNT",
            }
        ],
    }
    metrics = result["mechanical_metrics"]
    fd_cap = float(market["reported_fd_market_cap_inr"])
    total_equity = market.get("annual_total_equity_inr")

    if family == "DILUTION_FINANCING":
        issue_price = _finite_positive(
            terms.get("issue_price_per_security"), label=f"{symbol} issue price"
        )
        if symbol == "DEVX":
            if prior_counts is None:
                raise AlphaContractError("DEVX prior share counts are required")
            if latest_counts["fully_paid_shares"] - prior_counts["fully_paid_shares"] != DEVX_PREF_EQUITY:
                raise AlphaContractError("DEVX paid-share reconciliation failed")
            if latest_counts["fully_diluted_shares"] - latest_counts["fully_paid_shares"] != DEVX_WARRANTS:
                raise AlphaContractError("DEVX warrant reconciliation failed")
            event_count = DEVX_PREF_EQUITY + DEVX_WARRANTS
            base_fd = prior_counts["fully_diluted_shares"]
            event_adjusted_fd = latest_counts["fully_diluted_shares"]
            adjustment_state = "ALREADY_REFLECTED_IN_LATEST_SHAREHOLDING"
        elif symbol == "SAMBHV":
            stages = {
                row["transaction_stage"]
                for row in _explicit_l001(
                    l001_rows,
                    family="security_economics",
                    field="number_of_securities",
                )
            }
            board_dates = {
                row["value"]
                for row in _explicit_l001(
                    l001_rows, family="dates", field="board_approval_date"
                )
            }
            if "BOARD_APPROVED" not in stages or "2026-07-15" not in board_dates:
                raise AlphaContractError("SAMBHV frozen post-quarter approval evidence mismatch")
            event_count = SAMBHV_PENDING_WARRANTS
            base_fd = latest_counts["fully_diluted_shares"]
            event_adjusted_fd = base_fd + event_count
            adjustment_state = "PRO_FORMA_PENDING_POST_REPORT_APPROVAL"
        else:
            raise AlphaContractError(f"{symbol}: unregistered dilution lane")

        gross_consideration = issue_price * event_count
        metrics.update(
            {
                "issue_price_per_security_inr": issue_price,
                "event_security_count": event_count,
                "event_security_count_to_base_fd_shares": event_count / base_fd,
                "issue_price_to_current_price_minus_one": (
                    issue_price / market["close_price_inr"] - 1.0
                ),
                "event_adjusted_fd_shares": event_adjusted_fd,
                "event_adjusted_fd_market_cap_inr": (
                    event_adjusted_fd * market["close_price_inr"]
                ),
                "gross_issue_consideration_inr": gross_consideration,
                "gross_issue_consideration_to_reported_fd_market_cap": (
                    gross_consideration / fd_cap
                ),
                "share_adjustment_state": adjustment_state,
            }
        )
        result["post_d001_state"] = "DENOMINATOR_READY"

    elif family == "ACQUISITION_ECONOMICS":
        consideration = _finite_positive(
            terms.get("stated_total_consideration"),
            label=f"{symbol} stated acquisition consideration",
        )
        support = _explicit_l001(
            l001_rows, family="consideration", field="total_consideration"
        )
        matched = [
            row
            for row in support
            if row["value"] == consideration
            and row["unit"] == "INR_CRORE_MAXIMUM"
        ]
        if not matched:
            raise AlphaContractError("INOXGREEN acquisition consideration unit unavailable")
        consideration_inr = consideration * 10_000_000.0
        metrics.update(
            {
                "stated_consideration_inr": consideration_inr,
                "stated_consideration_inr_crore": consideration,
                "stated_consideration_is_maximum": True,
                "consideration_to_reported_fd_market_cap": consideration_inr / fd_cap,
                "consideration_to_annual_total_equity": (
                    consideration_inr / total_equity
                    if isinstance(total_equity, (int, float)) and total_equity > 0
                    else None
                ),
                "target_operating_metric_text": terms.get("operating_metric"),
            }
        )
        result["post_d001_state"] = "VALUATION_INPUT_REQUIRED"

    elif family == "DEMERGER_ENTITLEMENT":
        metrics.update(
            {
                "exchange_ratio_text": terms.get("exchange_ratio_text"),
                "separated_business_description": terms.get(
                    "asset_or_business_description"
                ),
                "separated_business_operating_metric": terms.get("operating_metric"),
            }
        )
        result["post_d001_state"] = "VALUATION_INPUT_REQUIRED"

    elif family == "CAPITAL_DEPLOYMENT_MONITOR":
        stated = _finite(terms.get("stated_raise_or_consideration"))
        metrics.update(
            {
                "stated_raise_inr_crore": stated,
                "stated_raise_to_reported_fd_market_cap": (
                    stated * 10_000_000.0 / fd_cap if stated is not None else None
                ),
                "stated_use_of_proceeds": terms.get("stated_use_of_proceeds"),
                "deployment_or_operating_metric": terms.get(
                    "deployment_or_operating_metric"
                ),
            }
        )
        result["post_d001_state"] = "VALUATION_INPUT_REQUIRED"

    else:
        raise AlphaContractError(f"{symbol}: HG005 unregistered lane family {family}")

    return result


def build_hg005_context(
    *,
    hg004_l002: dict[str, Any],
    hg004_l001: dict[str, Any],
    ss001: dict[str, Any],
    gf001: dict[str, Any],
    fa001: dict[str, Any],
    latest_shareholding_raw: dict[str, bytes],
    prior_shareholding_raw: dict[str, bytes],
) -> dict[str, Any]:
    _validate_sources(
        hg004_l002=hg004_l002,
        hg004_l001=hg004_l001,
        ss001=ss001,
        gf001=gf001,
        fa001=fa001,
    )

    hg_rows = _index_rows(hg004_l002)
    ss_rows = _index_rows(ss001)
    gf_rows = _index_rows(gf001)
    fa_rows = _index_rows(fa001)
    l001_rows = _l001_by_symbol(hg004_l001)

    ready = set(hg004_l002.get("payoff_model_ready_symbols") or [])
    if ready != EXPECTED_SYMBOLS:
        raise AlphaContractError(f"HG005 frozen ready-symbol mismatch: {sorted(ready)}")
    if set(latest_shareholding_raw) != EXPECTED_SYMBOLS:
        raise AlphaContractError("HG005 latest shareholding raw coverage mismatch")

    rows = []
    lane_state_counts: dict[str, int] = defaultdict(int)
    for symbol in sorted(EXPECTED_SYMBOLS):
        for source_name, source_rows in (
            ("SS001", ss_rows),
            ("GF001", gf_rows),
            ("FA001", fa_rows),
            ("HG004", hg_rows),
        ):
            if symbol not in source_rows:
                raise AlphaContractError(f"{symbol}: missing {source_name} source row")

        gf_row = gf_rows[symbol]
        latest = gf_row.get("latest")
        if not isinstance(latest, dict):
            raise AlphaContractError(f"{symbol}: GF001 latest source unavailable")
        latest_counts = parse_shareholding_counts(
            latest_shareholding_raw[symbol], symbol=symbol
        )

        prior_counts = None
        if symbol in prior_shareholding_raw:
            prior_counts = parse_shareholding_counts(
                prior_shareholding_raw[symbol], symbol=symbol
            )

        close, turnover = _current_market(ss_rows[symbol])
        market = _market_and_financial_context(
            symbol=symbol,
            close=close,
            turnover=turnover,
            share_counts=latest_counts,
            fa_row=fa_rows[symbol],
        )
        governance = _latest_governance(gf_row)

        lanes = []
        hg_lanes = hg_rows[symbol].get("payoff_model_lanes")
        if not isinstance(hg_lanes, list):
            raise AlphaContractError(f"{symbol}: HG004 lanes unavailable")
        for lane in hg_lanes:
            state = str(lane.get("readiness_state") or "")
            if not state.startswith("READY_"):
                continue
            enriched = _lane_after_d001(
                symbol=symbol,
                lane=lane,
                market=market,
                latest_counts=latest_counts,
                prior_counts=prior_counts,
                l001_rows=l001_rows.get(symbol, []),
            )
            lanes.append(enriched)
            lane_state_counts[enriched["post_d001_state"]] += 1

        if not lanes:
            raise AlphaContractError(f"{symbol}: no payoff-ready HG005 lane")

        rows.append(
            {
                "symbol": symbol,
                "market_and_financial_context": market,
                "shareholding_context": {
                    "latest_report_date": latest.get("report_date"),
                    "fully_paid_shares": latest_counts["fully_paid_shares"],
                    "reported_fully_diluted_shares": latest_counts[
                        "fully_diluted_shares"
                    ],
                    "prior_report_date": (
                        gf_row.get("prior", {}).get("report_date")
                        if isinstance(gf_row.get("prior"), dict)
                        else None
                    ),
                    "prior_fully_paid_shares": (
                        prior_counts["fully_paid_shares"]
                        if prior_counts is not None
                        else None
                    ),
                    "prior_fully_diluted_shares": (
                        prior_counts["fully_diluted_shares"]
                        if prior_counts is not None
                        else None
                    ),
                },
                "governance_context": governance,
                "payoff_lanes": lanes,
                "return_outcomes_opened": False,
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    output = {
        "schema_version": 1,
        "context_id": CONTEXT_ID,
        "classification": "MECHANICAL_MARKET_DENOMINATOR_AND_PAYOFF_CONTEXT_NOT_ALPHA",
        "price_session": FROZEN_PRICE_SESSION,
        "symbol_count": len(rows),
        "symbols": [row["symbol"] for row in rows],
        "lane_state_counts": dict(sorted(lane_state_counts.items())),
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["context_sha256"] = digest(output)
    return output
